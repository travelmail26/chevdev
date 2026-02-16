import { Switch, Route } from "wouter";
import { queryClient } from "./lib/queryClient";
import { QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { SidebarProvider } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/app-sidebar";
import NotFound from "@/pages/not-found";
import Home from "@/pages/Home";
import Thread from "@/pages/Thread";

function Router() {
  return (
    <Switch>
      <Route path="/" component={Home} />
      <Route path="/thread/:id" component={Thread} />
      <Route path="/discover" component={Home} />
      <Route component={NotFound} />
    </Switch>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <SidebarProvider style={{ "--sidebar-width": "16rem" } as React.CSSProperties}>
          <div className="flex h-[100dvh] w-full">
            <AppSidebar />
            <main className="flex-1 flex flex-col min-w-0">
              <Router />
            </main>
          </div>
        </SidebarProvider>
        <Toaster />
      </TooltipProvider>
    </QueryClientProvider>
  );
}

export default App;
