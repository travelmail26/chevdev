import { useState } from 'react';
import { useLocation } from 'wouter';
import { ChatInput, type PerplexityModel } from '@/components/chat/ChatInput';
import { useCreateThread } from '@/hooks/use-threads';
import { SidebarTrigger } from '@/components/ui/sidebar';

export default function Home() {
  const [_, setLocation] = useLocation();
  const createThread = useCreateThread();
  const [isCreating, setIsCreating] = useState(false);
  const [selectedModel, setSelectedModel] = useState<PerplexityModel>(() => {
    return (localStorage.getItem('perplexity_model') as PerplexityModel) || 'sonar';
  });

  const handleModelChange = (model: PerplexityModel) => {
    setSelectedModel(model);
    localStorage.setItem('perplexity_model', model);
  };

  const handleSend = async (message: string) => {
    setIsCreating(true);
    try {
      const thread = await createThread.mutateAsync(message.slice(0, 50) + (message.length > 50 ? "..." : ""));
      sessionStorage.setItem(`pending_message_${thread.id}`, message);
      sessionStorage.setItem(`pending_model_${thread.id}`, selectedModel);
      setLocation(`/thread/${thread.id}`);
    } catch (error) {
      console.error(error);
      setIsCreating(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center p-2 md:hidden">
        <SidebarTrigger data-testid="button-sidebar-toggle-home" />
      </div>

      <div className="flex-1 flex flex-col items-center justify-center p-4 md:p-8 relative">
        <div className="w-full max-w-2xl flex flex-col items-center animate-in fade-in zoom-in-95 duration-500 px-2">
          <h1 className="font-serif text-3xl sm:text-4xl md:text-5xl font-medium text-primary mb-6 sm:mb-8 text-center tracking-tight">
            Where knowledge begins
          </h1>

          <ChatInput
            onSend={handleSend}
            variant="center"
            isLoading={isCreating}
            className="mb-8"
            selectedModel={selectedModel}
            onModelChange={handleModelChange}
          />
        </div>

        <div className="absolute bottom-4 sm:bottom-6 text-xs text-muted-foreground/60">
          Powered by Perplexity API
        </div>
      </div>
    </div>
  );
}
