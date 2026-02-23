import { useRef, useState, useEffect, useCallback, useImperativeHandle, forwardRef } from 'react';
import { cn } from '@/lib/utils';
import { ArrowUp, Paperclip, Mic, Square, ChevronDown, Zap, Brain, Sparkles, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
  DropdownMenuLabel,
} from '@/components/ui/dropdown-menu';

export type PerplexityModel = 'sonar' | 'sonar-pro' | 'sonar-reasoning' | 'sonar-reasoning-pro';

interface ModelOption {
  id: PerplexityModel;
  label: string;
  description: string;
  icon: typeof Zap;
  category: 'search' | 'reasoning';
}

const MODEL_OPTIONS: ModelOption[] = [
  { id: 'sonar', label: 'Sonar', description: 'Fast & affordable', icon: Zap, category: 'search' },
  { id: 'sonar-pro', label: 'Sonar Pro', description: 'Advanced search', icon: Search, category: 'search' },
  { id: 'sonar-reasoning', label: 'Reasoning', description: 'Step-by-step thinking', icon: Brain, category: 'reasoning' },
  { id: 'sonar-reasoning-pro', label: 'Reasoning Pro', description: 'Deep analysis', icon: Sparkles, category: 'reasoning' },
];

interface ChatInputProps {
  onSend: (message: string) => void;
  isLoading?: boolean;
  variant?: 'center' | 'bottom';
  className?: string;
  placeholder?: string;
  selectedModel?: PerplexityModel;
  onModelChange?: (model: PerplexityModel) => void;
}

export interface ChatInputHandle {
  stopListening: () => void;
}

export const ChatInput = forwardRef<ChatInputHandle, ChatInputProps>(({ 
  onSend, 
  isLoading, 
  variant = 'bottom',
  className,
  placeholder = "Ask anything...",
  selectedModel = 'sonar',
  onModelChange,
}, ref) => {
  const [input, setInput] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const recognitionRef = useRef<any>(null);

  const currentModel = MODEL_OPTIONS.find(m => m.id === selectedModel) || MODEL_OPTIONS[0];

  useEffect(() => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    setSpeechSupported(!!SpeechRecognition);
  }, []);

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
      recognitionRef.current = null;
    }
    setIsListening(false);
  }, []);

  useImperativeHandle(ref, () => ({
    stopListening,
  }), [stopListening]);

  const startListening = useCallback(() => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) return;

    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    let finalTranscript = '';

    recognition.onresult = (event: any) => {
      let interim = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript += transcript + ' ';
        } else {
          interim = transcript;
        }
      }
      setInput(prev => {
        const base = prev.replace(/\u200B.*$/, '').trimEnd();
        const spoken = (finalTranscript + interim).trim();
        if (!spoken) return base;
        return base ? `${base} ${spoken}` : spoken;
      });
    };

    recognition.onerror = (event: any) => {
      console.error('Speech recognition error:', event.error);
      if (event.error !== 'aborted') {
        setIsListening(false);
      }
    };

    recognition.onend = () => {
      setIsListening(false);
      recognitionRef.current = null;
    };

    recognitionRef.current = recognition;
    recognition.start();
    setIsListening(true);
  }, []);

  const toggleListening = useCallback(() => {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  }, [isListening, stopListening, startListening]);

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (isListening) {
      stopListening();
    }
    if (!input.trim() || isLoading) return;
    onSend(input.trim());
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
    }
  }, [input]);

  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
    };
  }, []);

  const CurrentIcon = currentModel.icon;
  const searchModels = MODEL_OPTIONS.filter(m => m.category === 'search');
  const reasoningModels = MODEL_OPTIONS.filter(m => m.category === 'reasoning');

  return (
    <div className={cn(
      "relative w-full transition-all duration-300",
      variant === 'center' ? "max-w-2xl" : "max-w-3xl mx-auto",
      className
    )}>
      <div className={cn(
        "relative flex flex-col bg-card border shadow-sm transition-all duration-200 focus-within:shadow-md focus-within:border-primary/20 overflow-visible",
        isListening ? "border-red-400 shadow-red-100" : "border-border/60",
        variant === 'center' ? "rounded-2xl" : "rounded-2xl"
      )}>
        {isListening && (
          <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-red-400 via-red-500 to-red-400 animate-pulse rounded-t-2xl" />
        )}

        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={isListening ? "Listening..." : placeholder}
          rows={1}
          data-testid="input-chat"
          className={cn(
            "w-full px-4 py-3.5 text-base bg-transparent border-none resize-none focus:ring-0 focus:outline-none placeholder:text-muted-foreground/60 min-h-[52px] max-h-[200px]",
            isListening && "placeholder:text-red-400 placeholder:animate-pulse"
          )}
          disabled={isLoading}
        />
        
        <div className="flex items-center justify-between px-2.5 pb-2.5 pt-0.5 gap-2">
          <div className="flex items-center gap-1 flex-wrap">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  data-testid="button-model-selector"
                  className="text-muted-foreground text-xs font-medium gap-1.5 rounded-full"
                >
                  <CurrentIcon className="w-3.5 h-3.5" />
                  <span className="hidden xs:inline">{currentModel.label}</span>
                  <ChevronDown className="w-3 h-3 opacity-60" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="w-56">
                <DropdownMenuLabel className="text-[10px] uppercase tracking-wider text-muted-foreground/60">Search Models</DropdownMenuLabel>
                {searchModels.map((model) => {
                  const Icon = model.icon;
                  return (
                    <DropdownMenuItem
                      key={model.id}
                      data-testid={`menu-item-model-${model.id}`}
                      onClick={() => onModelChange?.(model.id)}
                      className={cn(
                        "gap-3 cursor-pointer",
                        selectedModel === model.id && "bg-accent"
                      )}
                    >
                      <Icon className="w-4 h-4 flex-shrink-0" />
                      <div className="flex flex-col">
                        <span className="text-sm font-medium">{model.label}</span>
                        <span className="text-[10px] text-muted-foreground">{model.description}</span>
                      </div>
                    </DropdownMenuItem>
                  );
                })}
                <DropdownMenuSeparator />
                <DropdownMenuLabel className="text-[10px] uppercase tracking-wider text-muted-foreground/60">Reasoning Models</DropdownMenuLabel>
                {reasoningModels.map((model) => {
                  const Icon = model.icon;
                  return (
                    <DropdownMenuItem
                      key={model.id}
                      data-testid={`menu-item-model-${model.id}`}
                      onClick={() => onModelChange?.(model.id)}
                      className={cn(
                        "gap-3 cursor-pointer",
                        selectedModel === model.id && "bg-accent"
                      )}
                    >
                      <Icon className="w-4 h-4 flex-shrink-0" />
                      <div className="flex flex-col">
                        <span className="text-sm font-medium">{model.label}</span>
                        <span className="text-[10px] text-muted-foreground">{model.description}</span>
                      </div>
                    </DropdownMenuItem>
                  );
                })}
              </DropdownMenuContent>
            </DropdownMenu>

            <Button
              variant="ghost"
              size="sm"
              data-testid="button-attach"
              className="text-muted-foreground text-xs font-medium gap-1.5 rounded-full"
            >
              <Paperclip className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Attach</span>
            </Button>
          </div>
          
          <div className="flex items-center gap-1.5">
            {speechSupported && (
              <div className="relative">
                {isListening && (
                  <span className="absolute inset-0 rounded-full bg-red-400 animate-ping opacity-30 pointer-events-none" />
                )}
                <Button
                  size="icon"
                  variant={isListening ? "destructive" : "ghost"}
                  onClick={toggleListening}
                  data-testid="button-microphone"
                  className="rounded-full relative z-10"
                  title={isListening ? "Stop listening" : "Start voice input"}
                >
                  {isListening ? (
                    <Square className="w-4 h-4" />
                  ) : (
                    <Mic className="w-4.5 h-4.5" />
                  )}
                </Button>
              </div>
            )}

            <Button
              size="icon"
              onClick={() => handleSubmit()}
              disabled={!input.trim() || isLoading}
              data-testid="button-send"
              className={cn(
                "rounded-full",
                !(input.trim() && !isLoading) && "bg-muted text-muted-foreground"
              )}
            >
              <ArrowUp className="w-5 h-5" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
});

ChatInput.displayName = 'ChatInput';
