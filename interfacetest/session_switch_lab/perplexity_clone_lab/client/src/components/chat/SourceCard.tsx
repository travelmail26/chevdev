import { ExternalLink } from "lucide-react";

interface Source {
  title: string;
  url: string;
  snippet?: string;
}

export function SourceCard({ source, index }: { source: Source; index: number }) {
  const getDomain = (url: string) => {
    try {
      return new URL(url).hostname.replace('www.', '');
    } catch {
      return url;
    }
  };

  const getFavicon = (url: string) => {
    try {
      const domain = new URL(url).origin;
      return `https://www.google.com/s2/favicons?domain=${domain}&sz=16`;
    } catch {
      return null;
    }
  };

  const favicon = getFavicon(source.url);

  return (
    <a
      href={source.url}
      target="_blank"
      rel="noopener noreferrer"
      data-testid={`link-source-${index}`}
      className="flex-shrink-0 w-44 sm:w-52 p-2.5 sm:p-3 bg-card border border-border/60 rounded-lg hover:border-primary/30 hover:shadow-sm transition-all duration-200 group flex flex-col gap-1.5 h-[80px] sm:h-[88px] active:scale-[0.98]"
    >
      <h4 className="text-[11px] sm:text-xs font-medium text-foreground line-clamp-2 group-hover:text-primary transition-colors leading-tight">
        {source.title}
      </h4>
      <div className="mt-auto flex items-center gap-1.5 text-[10px] text-muted-foreground">
        <div className="flex items-center gap-1.5">
          {favicon ? (
            <img src={favicon} alt="" className="w-3.5 h-3.5 rounded-sm" />
          ) : (
            <div className="w-4 h-4 rounded-full bg-muted flex items-center justify-center text-[8px] font-bold">
              {index + 1}
            </div>
          )}
          <span className="truncate max-w-[100px] sm:max-w-[120px]">{getDomain(source.url)}</span>
        </div>
        <ExternalLink className="w-2.5 h-2.5 opacity-0 group-hover:opacity-100 transition-opacity ml-auto" />
      </div>
    </a>
  );
}

export function SourcesGrid({ sources }: { sources: Source[] }) {
  if (!sources || sources.length === 0) return null;

  return (
    <div data-testid="sources-grid" className="mb-5 sm:mb-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
      <div className="flex items-center gap-2 mb-2.5 sm:mb-3">
        <span className="text-[10px] sm:text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
          <span className="w-1 h-1 rounded-full bg-current" />
          Sources
        </span>
        <span className="text-[10px] text-muted-foreground/50">{sources.length} results</span>
      </div>
      <div className="flex gap-2 sm:gap-2.5 overflow-x-auto pb-2 scrollbar-hide touch-scroll -mx-4 px-4">
        {sources.map((source, i) => (
          <SourceCard key={i} source={source} index={i} />
        ))}
      </div>
    </div>
  );
}
