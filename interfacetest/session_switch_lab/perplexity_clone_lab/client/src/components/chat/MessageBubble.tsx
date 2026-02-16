import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { SourcesGrid } from './SourceCard';
import { cn } from '@/lib/utils';
import { Sparkles, Copy, ThumbsUp, ThumbsDown, Search, Brain, ChevronDown, ChevronUp, Check } from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/components/ui/button';

type StreamPhase = 'idle' | 'searching' | 'thinking' | 'answering' | 'done' | 'error';

interface MessageBubbleProps {
  role: 'user' | 'assistant';
  content: string;
  sources?: any[];
  isStreaming?: boolean;
  thinking?: string;
  phase?: StreamPhase;
  statusText?: string;
}

function ThinkingBlock({ thinking, isActive }: { thinking: string; isActive: boolean }) {
  const [expanded, setExpanded] = useState(false);

  if (!thinking && !isActive) return null;

  return (
    <div className="mb-4 animate-in fade-in slide-in-from-bottom-2 duration-300">
      <button
        data-testid="button-toggle-thinking"
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-xs font-medium text-muted-foreground/80 transition-colors active:opacity-70 group min-h-[36px]"
      >
        <div className={cn(
          "w-5 h-5 rounded-full flex items-center justify-center transition-colors flex-shrink-0",
          isActive ? "bg-amber-100 text-amber-600" : "bg-muted/50 text-muted-foreground"
        )}>
          <Brain className="w-3 h-3" />
        </div>
        <span>{isActive ? "Thinking..." : "Thought process"}</span>
        {isActive && (
          <span className="flex gap-0.5">
            <span className="w-1 h-1 rounded-full bg-amber-500 animate-bounce" style={{ animationDelay: '0ms' }} />
            <span className="w-1 h-1 rounded-full bg-amber-500 animate-bounce" style={{ animationDelay: '150ms' }} />
            <span className="w-1 h-1 rounded-full bg-amber-500 animate-bounce" style={{ animationDelay: '300ms' }} />
          </span>
        )}
        {!isActive && (
          expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />
        )}
      </button>

      {(expanded || isActive) && thinking && (
        <div className={cn(
          "mt-2 ml-7 pl-3 border-l-2 text-xs text-muted-foreground/70 leading-relaxed whitespace-pre-wrap max-h-60 overflow-y-auto",
          isActive ? "border-amber-300" : "border-border/50"
        )} style={{ WebkitOverflowScrolling: 'touch' }}>
          {thinking}
          {isActive && (
            <span className="inline-block w-1.5 h-3 ml-0.5 align-middle bg-amber-500 animate-pulse rounded-sm" />
          )}
        </div>
      )}
    </div>
  );
}

function SearchingIndicator({ text }: { text?: string }) {
  return (
    <div className="flex items-center gap-3 mb-5 sm:mb-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
      <div className="relative w-7 h-7 sm:w-8 sm:h-8 flex items-center justify-center flex-shrink-0">
        <div className="absolute inset-0 rounded-full border-2 border-primary/20 border-t-primary animate-spin" />
        <Search className="w-3 h-3 sm:w-3.5 sm:h-3.5 text-primary" />
      </div>
      <div>
        <span className="text-sm font-medium text-foreground">{text || "Searching the web..."}</span>
        <span className="flex gap-0.5 mt-1">
          <span className="w-1 h-1 rounded-full bg-primary animate-bounce" style={{ animationDelay: '0ms' }} />
          <span className="w-1 h-1 rounded-full bg-primary animate-bounce" style={{ animationDelay: '150ms' }} />
          <span className="w-1 h-1 rounded-full bg-primary animate-bounce" style={{ animationDelay: '300ms' }} />
        </span>
      </div>
    </div>
  );
}

export function MessageBubble({ role, content, sources, isStreaming, thinking, phase, statusText }: MessageBubbleProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (role === 'user') {
    return (
      <div data-testid="message-user" className="group relative mb-6 sm:mb-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
        <h2 className="text-xl sm:text-2xl md:text-3xl font-serif font-medium text-foreground tracking-tight mb-3 sm:mb-4 leading-tight">
          {content}
        </h2>
      </div>
    );
  }

  const isSearching = phase === 'searching';
  const isThinking = phase === 'thinking';
  const isAnswering = phase === 'answering';
  const isDone = phase === 'done' || (!isStreaming && !phase);
  const showContent = content && content.length > 0;

  return (
    <div data-testid="message-assistant" className="group relative mb-8 sm:mb-12 animate-in fade-in slide-in-from-bottom-4 duration-500">
      {isSearching && <SearchingIndicator text={statusText} />}

      {(thinking || isThinking) && (
        <ThinkingBlock thinking={thinking || ''} isActive={isThinking} />
      )}

      {sources && sources.length > 0 && (
        <SourcesGrid sources={sources} />
      )}

      {(showContent || isAnswering) && (
        <>
          <div className="flex items-center gap-2 mb-2.5 sm:mb-3">
            <div className="w-5 h-5 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
              <Sparkles className="w-3 h-3 text-primary" />
            </div>
            <span className="text-[10px] sm:text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Answer
            </span>
          </div>

          <div className="prose-custom max-w-none">
            {(statusText && (isThinking || isAnswering)) && (
              <p className="text-xs text-muted-foreground/80 mb-2">{statusText}</p>
            )}
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {content}
            </ReactMarkdown>
            {isStreaming && isAnswering && (
              <span className="inline-block w-2 h-4 ml-1 align-middle bg-primary animate-pulse rounded-full" />
            )}
          </div>
        </>
      )}

      {isDone && content && (
        <div className="flex items-center gap-2 mt-4 sm:mt-6 pt-3 sm:pt-4 border-t border-border/40">
          <Button
            variant="ghost"
            size="sm"
            data-testid="button-copy"
            onClick={handleCopy}
            className="text-muted-foreground text-xs gap-1.5"
          >
            {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
            {copied ? "Copied" : "Copy"}
          </Button>
          <div className="flex items-center gap-0.5">
            <Button size="icon" variant="ghost" data-testid="button-thumbs-up" className="text-muted-foreground">
              <ThumbsUp className="w-3.5 h-3.5" />
            </Button>
            <Button size="icon" variant="ghost" data-testid="button-thumbs-down" className="text-muted-foreground">
              <ThumbsDown className="w-3.5 h-3.5" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
