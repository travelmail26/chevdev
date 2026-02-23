import { useEffect, useRef, useState } from 'react';
import { useRoute } from 'wouter';
import { useThread } from '@/hooks/use-threads';
import { useChatStream } from '@/hooks/use-chat-stream';
import { ChatInput, type ChatInputHandle, type PerplexityModel } from '@/components/chat/ChatInput';
import { MessageBubble } from '@/components/chat/MessageBubble';
import { Square } from 'lucide-react';
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { SidebarTrigger } from '@/components/ui/sidebar';

export default function Thread() {
  const [match, params] = useRoute('/thread/:id');
  const threadId = params ? parseInt(params.id) : null;

  const { data: thread, isLoading: isThreadLoading } = useThread(threadId);
  const {
    content: streamContent,
    thinking: streamThinking,
    sources: streamSources,
    phase,
    statusText,
    threadId: streamThreadId,
    submit,
    stop,
    reset,
    isLoading,
  } = useChatStream();

  const bottomRef = useRef<HTMLDivElement>(null);
  const chatInputRef = useRef<ChatInputHandle>(null);
  const initialized = useRef(false);

  const [selectedModel, setSelectedModel] = useState<PerplexityModel>(() => {
    return (localStorage.getItem('perplexity_model') as PerplexityModel) || 'sonar';
  });

  const handleModelChange = (model: PerplexityModel) => {
    setSelectedModel(model);
    localStorage.setItem('perplexity_model', model);
  };

  useEffect(() => {
    if (threadId && !initialized.current) {
      const pendingMessage = sessionStorage.getItem(`pending_message_${threadId}`);
      const pendingModel = sessionStorage.getItem(`pending_model_${threadId}`);
      if (pendingMessage) {
        sessionStorage.removeItem(`pending_message_${threadId}`);
        sessionStorage.removeItem(`pending_model_${threadId}`);
        const modelToUse = (pendingModel as PerplexityModel) || selectedModel;
        submit(pendingMessage, threadId, modelToUse);
        initialized.current = true;
      }
    }
  }, [threadId, submit, selectedModel]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [streamContent, streamThinking, thread?.messages, phase]);

  useEffect(() => {
    // Before: streamed answer bubble stayed visible after the same answer was saved in thread history.
    // After: once persisted assistant content is present, clear transient stream state to avoid duplicate bubbles.
    if (phase !== 'done' || !streamContent.trim() || !thread?.messages?.length) return;
    const persisted = thread.messages.some((msg: any) => {
      if (msg.role !== 'assistant') return false;
      return String(msg.content || '').trim() === streamContent.trim();
    });
    if (persisted) {
      reset();
    }
  }, [phase, streamContent, thread?.messages, reset]);

  const handleSend = (message: string) => {
    if (threadId) {
      submit(message, threadId, selectedModel);
    }
  };

  const isStreaming = isLoading;
  const showStreamingBubble = phase !== 'idle' && phase !== 'done' && phase !== 'error';

  return (
    <div className="flex flex-col h-full relative">
      <div className="flex items-center p-2 md:hidden">
        <SidebarTrigger data-testid="button-sidebar-toggle-thread" />
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-6 md:px-12 md:py-8 scroll-smooth overscroll-contain" style={{ WebkitOverflowScrolling: 'touch' }}>
        <div className="max-w-3xl mx-auto min-h-full pb-40 sm:pb-36">
          {isThreadLoading ? (
            <div className="space-y-8 mt-12">
              <Skeleton className="h-8 w-3/4 rounded-lg" />
              <Skeleton className="h-40 w-full rounded-lg" />
              <Skeleton className="h-8 w-1/2 rounded-lg" />
            </div>
          ) : (
            <>
              {thread?.messages.map((msg: any) => (
                <MessageBubble
                  key={msg.id}
                  role={msg.role as 'user' | 'assistant'}
                  content={msg.content}
                  sources={msg.sources as any[]}
                />
              ))}

              {showStreamingBubble && (
                <>
                  {streamContent || streamThinking || streamSources.length > 0 || phase === 'searching' || phase === 'thinking' ? (
                    <MessageBubble
                      role="assistant"
                      content={streamContent}
                      thinking={streamThinking}
                      sources={streamSources}
                      isStreaming={isStreaming}
                      phase={phase}
                      statusText={statusText}
                    />
                  ) : null}
                </>
              )}

              {phase === 'error' && (
                <div data-testid="text-error" className="text-sm text-destructive bg-destructive/5 border border-destructive/20 rounded-lg p-4 mb-8">
                  {statusText || "Something went wrong. Please try again."}
                </div>
              )}

              <div ref={bottomRef} />
            </>
          )}
        </div>
      </div>

      <div className="absolute bottom-0 left-0 right-0 p-3 sm:p-4 bg-gradient-to-t from-background via-background to-transparent" style={{ paddingBottom: 'max(env(safe-area-inset-bottom, 0px), 0.75rem)' }}>
        <div className="max-w-3xl mx-auto flex gap-3 items-end">
          <ChatInput
            ref={chatInputRef}
            onSend={handleSend}
            isLoading={isStreaming}
            placeholder="Ask follow-up..."
            className="flex-1"
            selectedModel={selectedModel}
            onModelChange={handleModelChange}
          />
          {isStreaming && (
            <Button
              size="icon"
              variant="secondary"
              data-testid="button-stop"
              onClick={() => {
                chatInputRef.current?.stopListening();
                stop();
              }}
              title="Stop generating"
              className="mb-3 rounded-full"
            >
              <Square className="w-5 h-5 fill-current" />
            </Button>
          )}
        </div>
        <div className="text-center mt-1.5 text-[10px] text-muted-foreground/50">
          Perplexity can make mistakes. Consider checking important information.
        </div>
      </div>
    </div>
  );
}
