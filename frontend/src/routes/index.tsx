import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import {
  ArrowUpRight,
  Sparkles,
  RefreshCw,
  HardDriveDownload,
  Wifi,
  WifiOff,
  Loader2,
} from "lucide-react";
import { toast } from "sonner";
import { useMemo } from "react";
import { format } from "date-fns";

export const Route = createFileRoute("/")({
  component: Dashboard,
});

function Dashboard() {
  const qc = useQueryClient();

  const { data: analytics, isLoading: loadingAnalytics } = useQuery({
    queryKey: ["analytics"],
    queryFn: api.analytics,
  });

  const { data: queueData } = useQuery({
    queryKey: ["queue"],
    queryFn: api.queue,
  });

  const { data: calendarData } = useQuery({
    queryKey: ["calendar"],
    queryFn: api.calendar,
  });

  const { data: driveStatus, isLoading: loadingDrive } = useQuery({
    queryKey: ["driveStatus"],
    queryFn: api.driveOAuthStatus,
  });

  const stats = analytics
    ? [
        {
          label: "Published",
          value: String(analytics.published),
          hint: "Total posts sent",
        },
        {
          label: "In queue",
          value: String(analytics.queued),
          hint: "Waiting to publish",
        },
        {
          label: "Templates",
          value: String(analytics.templates),
          hint: "Available templates",
        },
        {
          label: "Failed",
          value: String(analytics.failed),
          hint: "Retry available",
        },
      ]
    : [];

  const weekData = useMemo(() => {
    const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
    const counts: Record<string, number> = Object.fromEntries(
      days.map((d) => [d, 0]),
    );
    const now = new Date();
    const weekStart = new Date(now);
    weekStart.setDate(now.getDate() - 6);

    calendarData?.items.forEach((post) => {
      const date = post.scheduled_at ? new Date(post.scheduled_at) : null;
      if (!date || date < weekStart) return;
      const idx = (date.getDay() + 6) % 7; // Mon=0
      counts[days[idx]] = (counts[days[idx]] ?? 0) + 1;
    });

    return days.map((day) => ({ day, items: counts[day] ?? 0 }));
  }, [calendarData]);

  async function connectDrive() {
    try {
      const data = await api.startDriveOAuth();
      window.location.href = data.authorization_url;
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to start OAuth");
    }
  }

  async function refreshDrive() {
    try {
      await api.refreshDrive();
      await qc.invalidateQueries({ queryKey: ["driveStatus"] });
      toast.success("Drive catalog refreshed");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Refresh failed");
    }
  }

  const upNext = queueData?.items.slice(0, 4) ?? [];
  const maxWeek = Math.max(...weekData.map((d) => d.items), 1);

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="What's happening across your channels."
        actions={
          <Button asChild size="sm">
            <Link to="/generator">
              <Sparkles size={15} /> New batch
            </Link>
          </Button>
        }
      />

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-10">
        {loadingAnalytics
          ? Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className="rounded-lg border border-border bg-card p-4 animate-pulse h-20"
              />
            ))
          : stats.map((s) => (
              <div
                key={s.label}
                className="rounded-lg border border-border bg-card p-4"
              >
                <div className="text-xs text-muted-foreground">{s.label}</div>
                <div className="text-2xl font-semibold tracking-tight mt-1">
                  {s.value}
                </div>
                <div className="text-[11px] text-muted-foreground mt-1">
                  {s.hint}
                </div>
              </div>
            ))}
      </div>

      <div className="grid lg:grid-cols-3 gap-6 mb-6">
        {/* Up next */}
        <section className="lg:col-span-2 rounded-lg border border-border bg-card">
          <div className="flex items-center justify-between px-5 h-12 border-b border-border">
            <h2 className="text-sm font-medium">Up next</h2>
            <Link
              to="/queue"
              className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
            >
              View queue <ArrowUpRight size={12} />
            </Link>
          </div>
          <ul className="divide-y divide-border">
            {upNext.length === 0 ? (
              <li className="px-5 h-14 flex items-center text-sm text-muted-foreground">
                Queue is empty
              </li>
            ) : null}
            {upNext.map((post) => (
              <li
                key={post.id}
                className="flex items-center gap-4 px-5 h-14"
              >
                <div
                  className={`size-1.5 rounded-full ${
                    post.status === "processing"
                      ? "bg-foreground"
                      : "bg-muted-foreground/40"
                  }`}
                />
                <div className="flex-1 min-w-0">
                  <div className="text-sm truncate">{post.word.word}</div>
                  <div className="text-xs text-muted-foreground truncate">
                    {post.status}
                  </div>
                </div>
                <div className="text-xs text-muted-foreground">
                  {post.scheduled_at
                    ? format(new Date(post.scheduled_at), "dd MMM, HH:mm")
                    : "Unscheduled"}
                </div>
              </li>
            ))}
          </ul>
        </section>

        {/* This week */}
        <section className="rounded-lg border border-border bg-card">
          <div className="flex items-center justify-between px-5 h-12 border-b border-border">
            <h2 className="text-sm font-medium">This week</h2>
          </div>
          <div className="p-5 space-y-2.5">
            {weekData.map((d) => (
              <div key={d.day} className="flex items-center gap-3 text-xs">
                <span className="w-8 text-muted-foreground">{d.day}</span>
                <div className="flex-1 h-1.5 rounded-full bg-secondary overflow-hidden">
                  <div
                    className="h-full bg-foreground/80"
                    style={{ width: `${(d.items / maxWeek) * 100}%` }}
                  />
                </div>
                <span className="w-4 text-right tabular-nums">{d.items}</span>
              </div>
            ))}
          </div>
        </section>
      </div>

      {/* Google Drive status */}
      <section className="rounded-lg border border-border bg-card">
        <div className="flex items-center justify-between px-5 h-12 border-b border-border">
          <h2 className="text-sm font-medium">Google Drive</h2>
          {loadingDrive && (
            <Loader2 size={14} className="animate-spin text-muted-foreground" />
          )}
        </div>
        <div className="px-5 py-4 flex items-center gap-4">
          {driveStatus?.connected ? (
            <>
              <Wifi size={16} className="text-green-600 shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium">Connected</div>
                {driveStatus.email && (
                  <div className="text-xs text-muted-foreground">
                    {driveStatus.email}
                  </div>
                )}
              </div>
              <Badge variant="outline" className="text-green-700 border-green-300 bg-green-50">
                Active
              </Badge>
              <Button size="sm" variant="outline" onClick={refreshDrive}>
                <RefreshCw size={14} /> Refresh catalog
              </Button>
            </>
          ) : (
            <>
              <WifiOff size={16} className="text-muted-foreground shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium">Not connected</div>
                <div className="text-xs text-muted-foreground">
                  Connect Drive to enable vocabulary batch imports
                </div>
              </div>
              <Button size="sm" onClick={connectDrive}>
                <HardDriveDownload size={14} /> Connect Drive
              </Button>
            </>
          )}
        </div>
      </section>

      {/* Recent logs */}
      {analytics?.recent_logs && analytics.recent_logs.length > 0 && (
        <section className="mt-6 rounded-lg border border-border bg-card">
          <div className="px-5 h-12 border-b border-border flex items-center">
            <h2 className="text-sm font-medium">Recent activity</h2>
          </div>
          <ul className="divide-y divide-border">
            {analytics.recent_logs.slice(0, 8).map((log, i) => (
              <li
                key={i}
                className="flex items-start gap-3 px-5 py-3 text-xs"
              >
                <span
                  className={`mt-0.5 font-medium uppercase shrink-0 ${
                    log.level === "ERROR"
                      ? "text-destructive"
                      : log.level === "WARNING"
                        ? "text-yellow-600"
                        : "text-muted-foreground"
                  }`}
                >
                  {log.level}
                </span>
                <span className="flex-1 text-foreground">{log.message}</span>
                <span className="text-muted-foreground shrink-0">
                  {log.timestamp
                    ? format(new Date(log.timestamp), "HH:mm")
                    : ""}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}
