import { Link, useLocation } from "wouter";
import { useThreads } from "@/hooks/use-threads";
import { cn } from "@/lib/utils";
import { Plus, Search, Library, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import logo from "@assets/logo.svg";

export function Sidebar({ className }: { className?: string }) {
  const [location] = useLocation();
  const { data: threads, isLoading } = useThreads();

  return (
    <div className={cn("flex flex-col h-full bg-background border-r border-border/40 w-[260px] flex-shrink-0", className)}>
      <div className="p-4 sm:p-6">
        <Link href="/">
          <div className="flex items-center gap-3 cursor-pointer group">
            <img src={logo} alt="Logo" className="w-7 h-7 sm:w-8 sm:h-8 transition-transform group-hover:scale-110" />
            <span className="font-serif font-bold text-lg sm:text-xl text-primary tracking-tight">Perplexity</span>
          </div>
        </Link>
      </div>

      <div className="px-3 sm:px-4 mb-4 sm:mb-6">
        <Link href="/">
          <Button variant="outline" className="w-full gap-2 rounded-full justify-start" data-testid="button-new-thread">
            <Plus className="w-4 h-4" />
            <span className="font-medium text-sm">New Thread</span>
          </Button>
        </Link>
      </div>

      <nav className="px-2 space-y-0.5">
        <NavItem href="/" icon={Search} label="Home" active={location === "/"} />
        <NavItem href="/discover" icon={Library} label="Discover" active={location === "/discover"} />
      </nav>

      <div className="mt-6 sm:mt-8 px-3 sm:px-4 flex-1 min-h-0">
        <h3 className="text-[10px] sm:text-xs font-bold text-muted-foreground uppercase tracking-wider mb-2 sm:mb-3 px-2">Library</h3>
        <div className="space-y-0.5 overflow-y-auto max-h-full scrollbar-hide" style={{ WebkitOverflowScrolling: 'touch' }}>
          {isLoading ? (
            <div className="space-y-2 px-2">
              <div className="h-4 w-3/4 bg-muted animate-pulse rounded" />
              <div className="h-4 w-1/2 bg-muted animate-pulse rounded" />
            </div>
          ) : threads && threads.length > 0 ? (
            <>
              {threads.map((thread) => (
                <Link key={thread.id} href={`/thread/${thread.id}`}>
                  <div className={cn(
                    "px-3 py-2.5 text-sm rounded-lg cursor-pointer transition-colors truncate flex items-center justify-between group min-h-[40px]",
                    location === `/thread/${thread.id}` 
                      ? "bg-muted text-primary font-medium" 
                      : "text-muted-foreground hover-elevate"
                  )}>
                    <span className="truncate">{thread.title || "Untitled Thread"}</span>
                    {location === `/thread/${thread.id}` && (
                      <ChevronRight className="w-3 h-3 opacity-50 flex-shrink-0" />
                    )}
                  </div>
                </Link>
              ))}
            </>
          ) : (
            <div className="px-3 py-2 text-sm text-muted-foreground/60 italic">
              No history yet
            </div>
          )}
        </div>
      </div>
      
      <div className="p-3 sm:p-4 border-t border-border/40">
        <div className="flex items-center gap-3 text-sm text-muted-foreground p-2 rounded-lg min-h-[44px]">
            <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-primary font-serif font-bold flex-shrink-0">
                U
            </div>
            <div className="flex-1 min-w-0">
                <p className="font-medium text-primary truncate">User</p>
                <p className="text-xs opacity-70">Free Plan</p>
            </div>
        </div>
      </div>
    </div>
  );
}

function NavItem({ href, icon: Icon, label, active }: { href: string; icon: any; label: string; active: boolean }) {
  return (
    <Link href={href}>
      <div className={cn(
        "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all cursor-pointer min-h-[44px]",
        active 
          ? "bg-muted text-primary" 
          : "text-muted-foreground hover-elevate"
      )}>
        <Icon className={cn("w-5 h-5 flex-shrink-0", active ? "text-primary" : "text-muted-foreground")} />
        {label}
      </div>
    </Link>
  );
}
