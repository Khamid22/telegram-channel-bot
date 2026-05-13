import { Outlet, createRootRouteWithContext, Link } from "@tanstack/react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, useEffect } from "react";
import { Loader2 } from "lucide-react";
import { Toaster } from "sonner";
import { AppSidebar } from "@/components/app-sidebar";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { api, type User } from "@/lib/api";
import { AuthContext } from "@/lib/auth-context";
import LoginView from "@/components/login-view";

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  component: RootComponent,
  notFoundComponent: NotFoundComponent,
  errorComponent: ErrorComponent,
});

function NotFoundComponent() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-7xl font-bold text-foreground">404</h1>
        <h2 className="mt-4 text-xl font-semibold text-foreground">
          Page not found
        </h2>
        <p className="mt-2 text-sm text-muted-foreground">
          The page you&apos;re looking for doesn&apos;t exist.
        </p>
        <div className="mt-6">
          <Link
            to="/"
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Go home
          </Link>
        </div>
      </div>
    </div>
  );
}

function ErrorComponent({
  error,
  reset,
}: {
  error: Error;
  reset: () => void;
}) {
  console.error(error);
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-xl font-semibold tracking-tight text-foreground">
          Something went wrong
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">{error.message}</p>
        <div className="mt-6">
          <button
            onClick={reset}
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Try again
          </button>
        </div>
      </div>
    </div>
  );
}

function RootComponent() {
  const { queryClient } = Route.useRouteContext();
  const [user, setUser] = useState<User | null | undefined>(undefined);

  useEffect(() => {
    api
      .me()
      .then((data) => setUser(data.user))
      .catch(() => setUser(null));
  }, []);

  if (user === undefined) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (user === null) {
    return <LoginView onLogin={setUser} />;
  }

  return (
    <AuthContext.Provider value={{ user, onLogout: () => setUser(null) }}>
      <QueryClientProvider client={queryClient}>
        <Toaster richColors position="top-right" />
        <SidebarProvider>
          <div className="flex min-h-screen w-full bg-background text-foreground">
            <AppSidebar />
            <main className="flex-1 min-w-0 flex flex-col">
              <header className="h-14 flex items-center gap-2 border-b border-border px-4 md:px-6 sticky top-0 bg-background/80 backdrop-blur z-10">
                <SidebarTrigger />
              </header>
              <div className="flex-1 mx-auto w-full max-w-6xl px-4 md:px-10 py-8 md:py-10">
                <Outlet />
              </div>
            </main>
          </div>
        </SidebarProvider>
      </QueryClientProvider>
    </AuthContext.Provider>
  );
}
