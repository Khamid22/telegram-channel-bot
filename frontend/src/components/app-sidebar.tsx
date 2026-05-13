import { Link, useLocation } from "@tanstack/react-router";
import {
  LayoutDashboard,
  Sparkles,
  Timer,
  ListTodo,
  CalendarDays,
  LayoutTemplate,
  AlertTriangle,
  LogOut,
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth-context";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

const nav = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/generator", label: "Generator", icon: Sparkles },
  { to: "/scheduler", label: "Scheduler", icon: Timer },
  { to: "/queue", label: "Queue", icon: ListTodo },
  { to: "/calendar", label: "Calendar", icon: CalendarDays },
  { to: "/templates", label: "Templates", icon: LayoutTemplate },
  { to: "/failed", label: "Failed", icon: AlertTriangle },
] as const;

export function AppSidebar() {
  const { pathname } = useLocation();
  const { setOpenMobile, isMobile } = useSidebar();
  const { user, onLogout } = useAuth();
  const queryClient = useQueryClient();

  const handleNav = () => {
    if (isMobile) setOpenMobile(false);
  };

  async function handleLogout() {
    try {
      await api.logout();
    } catch {}
    queryClient.clear();
    onLogout();
  }

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="h-14 border-b border-sidebar-border px-3 justify-center">
        <div className="flex items-center gap-2.5 px-2">
          <div className="size-7 shrink-0 rounded-md bg-primary text-primary-foreground grid place-items-center text-sm font-semibold">
            M
          </div>
          <span className="text-sm font-medium tracking-tight group-data-[collapsible=icon]:hidden">
            Multilevel
          </span>
        </div>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {nav.map((item) => {
                const Icon = item.icon;
                const active =
                  item.to === "/"
                    ? pathname === "/"
                    : pathname.startsWith(item.to);
                return (
                  <SidebarMenuItem key={item.to}>
                    <SidebarMenuButton asChild isActive={active} tooltip={item.label}>
                      <Link to={item.to} onClick={handleNav}>
                        <Icon />
                        <span>{item.label}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="border-t border-sidebar-border">
        <div className="flex items-center gap-2 px-2 py-1.5">
          <div className="size-7 shrink-0 rounded-full bg-sidebar-accent grid place-items-center text-xs font-medium">
            {user.username.charAt(0).toUpperCase()}
          </div>
          <div className="flex-1 min-w-0 group-data-[collapsible=icon]:hidden">
            <div className="text-xs font-medium truncate">{user.username}</div>
            <div className="text-[11px] text-muted-foreground truncate">
              Signed in
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="size-7 shrink-0 group-data-[collapsible=icon]:hidden"
            onClick={handleLogout}
            title="Sign out"
          >
            <LogOut size={14} />
          </Button>
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}
