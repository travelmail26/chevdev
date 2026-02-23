import { Link, useLocation } from "wouter";
import { useThreads } from "@/hooks/use-threads";
import { Plus, Search, Library } from "lucide-react";
import { Button } from "@/components/ui/button";
import logo from "@assets/logo.svg";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";

export function AppSidebar() {
  const [location] = useLocation();
  const { data: threads, isLoading } = useThreads();

  return (
    <Sidebar>
      <SidebarHeader className="p-4">
        <Link href="/">
          <div className="flex items-center gap-3 cursor-pointer" data-testid="link-logo">
            <img src={logo} alt="Logo" className="w-7 h-7" />
            <span className="font-serif font-bold text-lg text-primary tracking-tight">Perplexity</span>
          </div>
        </Link>
        <div className="mt-3">
          <Link href="/">
            <Button variant="outline" className="w-full gap-2 rounded-full justify-start" data-testid="button-new-thread">
              <Plus className="w-4 h-4" />
              <span className="font-medium text-sm">New Thread</span>
            </Button>
          </Link>
        </div>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton asChild isActive={location === "/"} className="hover-elevate" data-testid="link-home">
                  <Link href="/">
                    <Search />
                    <span>Home</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton asChild isActive={location === "/discover"} className="hover-elevate" data-testid="link-discover">
                  <Link href="/discover">
                    <Library />
                    <span>Discover</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup className="flex-1 min-h-0">
          <SidebarGroupLabel className="uppercase tracking-wider text-[10px] font-bold">Library</SidebarGroupLabel>
          <SidebarGroupContent className="overflow-y-auto">
            <SidebarMenu>
              {isLoading ? (
                <>
                  <SidebarMenuItem>
                    <div className="h-4 w-3/4 bg-muted animate-pulse rounded mx-2 my-2" />
                  </SidebarMenuItem>
                  <SidebarMenuItem>
                    <div className="h-4 w-1/2 bg-muted animate-pulse rounded mx-2 my-2" />
                  </SidebarMenuItem>
                </>
              ) : threads && threads.length > 0 ? (
                threads.map((thread) => (
                  <SidebarMenuItem key={thread.id}>
                    <SidebarMenuButton
                      asChild
                      isActive={location === `/thread/${thread.id}`}
                      className="hover-elevate"
                      data-testid={`link-thread-${thread.id}`}
                    >
                      <Link href={`/thread/${thread.id}`}>
                        <span className="truncate">{thread.title || "Untitled Thread"}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))
              ) : (
                <SidebarMenuItem>
                  <div className="px-2 py-2 text-sm text-muted-foreground/60 italic">
                    No history yet
                  </div>
                </SidebarMenuItem>
              )}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="border-t border-border/40">
        <div className="flex items-center gap-3 text-sm text-muted-foreground p-2" data-testid="sidebar-user-info">
          <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-primary font-serif font-bold flex-shrink-0">
            U
          </div>
          <div className="flex-1 min-w-0">
            <p className="font-medium text-primary truncate">User</p>
            <p className="text-xs opacity-70">Free Plan</p>
          </div>
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}
