import { useState, useRef, useCallback } from 'react';
import { api } from '@shared/routes';
import { useQueryClient } from '@tanstack/react-query';
import { getCanonicalUserHeader } from '@/lib/canonical-user';

type StreamPhase = 'idle' | 'searching' | 'thinking' | 'answering' | 'done' | 'error';

interface Source {
  title: string;
  url: string;
  snippet?: string;
}

interface ChatStreamState {
  content: string;
  thinking: string;
  sources: Source[];
  phase: StreamPhase;
  statusText: string;
  threadId: number | null;
}

export function useChatStream() {
  const [state, setState] = useState<ChatStreamState>({
    content: '',
    thinking: '',
    sources: [],
    phase: 'idle',
    statusText: '',
    threadId: null,
  });

  const abortControllerRef = useRef<AbortController | null>(null);
  const queryClient = useQueryClient();

  const reset = useCallback(() => {
    setState({
      content: '',
      thinking: '',
      sources: [],
      phase: 'idle',
      statusText: '',
      threadId: null,
    });
  }, []);

  const stop = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setState(prev => ({ ...prev, phase: 'done' }));
    }
  }, []);

  const submit = useCallback(async (message: string, threadId?: number, model?: string) => {
    setState({
      content: '',
      thinking: '',
      sources: [],
      phase: 'searching',
      statusText: 'Searching the web...',
      threadId: threadId || null,
    });

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    try {
      const res = await fetch(api.chat.sendMessage.path, {
        method: api.chat.sendMessage.method,
        headers: {
          'Content-Type': 'application/json',
          ...getCanonicalUserHeader(),
        },
        body: JSON.stringify({ message, threadId, model }),
        signal: abortControllerRef.current.signal,
      });

      if (!res.ok) throw new Error('Failed to send message');
      if (!res.body) throw new Error('No response body');

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        const events = parseSSE(buffer);
        buffer = events.remaining;

        for (const event of events.parsed) {
          handleEvent(event.type, event.data, setState, queryClient);
        }
      }

      setState(prev => {
        if (prev.phase !== 'done' && prev.phase !== 'error') {
          return { ...prev, phase: 'done' };
        }
        return prev;
      });

    } catch (error: any) {
      if (error.name === 'AbortError') return;
      console.error('Streaming error:', error);
      setState(prev => ({ ...prev, phase: 'error', statusText: error.message }));
    } finally {
      abortControllerRef.current = null;
    }
  }, [queryClient]);

  return {
    ...state,
    submit,
    stop,
    reset,
    isLoading: state.phase !== 'idle' && state.phase !== 'done' && state.phase !== 'error',
  };
}

interface ParsedEvent {
  type: string;
  data: any;
}

function parseSSE(buffer: string): { parsed: ParsedEvent[]; remaining: string } {
  const parsed: ParsedEvent[] = [];
  const blocks = buffer.split('\n\n');
  const remaining = blocks.pop() || '';

  for (const block of blocks) {
    if (!block.trim()) continue;

    let eventType = '';
    let dataStr = '';

    const lines = block.split('\n');
    for (const line of lines) {
      if (line.startsWith('event: ')) {
        eventType = line.slice(7).trim();
      } else if (line.startsWith('data: ')) {
        dataStr = line.slice(6);
      }
    }

    if (dataStr) {
      try {
        const data = JSON.parse(dataStr);
        parsed.push({ type: eventType || inferType(data), data });
      } catch {
        // skip malformed
      }
    }
  }

  return { parsed, remaining };
}

function inferType(data: any): string {
  if (data.phase) return 'status';
  if (data.sources) return 'sources';
  if (data.content !== undefined && data.text === undefined) return 'thinking';
  if (data.text !== undefined) return 'content';
  if (data.threadId !== undefined && Object.keys(data).length <= 1) return 'meta';
  if (data.message) return 'error';
  return 'unknown';
}

function handleEvent(
  type: string,
  data: any,
  setState: React.Dispatch<React.SetStateAction<ChatStreamState>>,
  queryClient: any
) {
  switch (type) {
    case 'meta':
      setState(prev => ({ ...prev, threadId: data.threadId }));
      break;
    case 'status':
      setState(prev => ({
        ...prev,
        phase: data.phase as StreamPhase,
        statusText: data.text || '',
      }));
      break;
    case 'sources':
      setState(prev => ({ ...prev, sources: data.sources }));
      break;
    case 'thinking':
      setState(prev => ({
        ...prev,
        phase: 'thinking',
        thinking: prev.thinking + (data.content || ''),
      }));
      break;
    case 'content':
      setState(prev => ({
        ...prev,
        phase: 'answering',
        content: prev.content + (data.text || ''),
      }));
      break;
    case 'done':
      setState(prev => ({ ...prev, phase: 'done', threadId: data.threadId }));
      if (data.threadId) {
        queryClient.invalidateQueries({ queryKey: [api.threads.get.path, data.threadId] });
        queryClient.invalidateQueries({ queryKey: [api.threads.list.path] });
      }
      break;
    case 'error':
      setState(prev => ({
        ...prev,
        phase: 'error',
        statusText: data.message || 'Something went wrong',
      }));
      break;
  }
}
