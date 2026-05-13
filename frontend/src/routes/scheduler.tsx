import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, useMemo } from "react";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { api, type CreateSchedulePayload } from "@/lib/api";
import { toast } from "sonner";
import { Pause, Play, Plus, Trash2 } from "lucide-react";

export const Route = createFileRoute("/scheduler")({
  component: SchedulerPage,
});

const defaultForm: CreateSchedulePayload = {
  name: "",
  batch_id: 0,
  timezone: "Asia/Tashkent",
  start_date: "",
  end_date: "",
  posts_per_day: 5,
  dispatch_mode: "even",
  window_start: "09:00",
  window_end: "18:00",
  manual_times: ["09:00", "12:00", "15:00", "18:00"],
};

function SchedulerPage() {
  const qc = useQueryClient();
  const [form, setForm] = useState(defaultForm);
  const [manualTimesStr, setManualTimesStr] = useState("09:00,12:00,15:00,18:00");

  const { data: schedulesData } = useQuery({
    queryKey: ["schedules"],
    queryFn: api.schedules,
  });

  const { data: batchesData } = useQuery({
    queryKey: ["batches"],
    queryFn: api.vocabularyBatches,
  });

  const readyBatches = useMemo(
    () => (batchesData?.items ?? []).filter((b) => b.status === "ready"),
    [batchesData],
  );

  const schedules = schedulesData?.items ?? [];

  const createMutation = useMutation({
    mutationFn: api.createSchedule,
    onSuccess: () => {
      toast.success("Schedule created");
      setForm(defaultForm);
      setManualTimesStr("09:00,12:00,15:00,18:00");
      void qc.invalidateQueries({ queryKey: ["schedules"] });
    },
    onError: (err) =>
      toast.error(err instanceof Error ? err.message : "Failed to create"),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, is_paused }: { id: number; is_paused: boolean }) =>
      api.updateSchedule(id, { is_paused }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["schedules"] }),
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed"),
  });

  const deleteMutation = useMutation({
    mutationFn: api.deleteSchedule,
    onSuccess: () => {
      toast.success("Schedule deleted");
      void qc.invalidateQueries({ queryKey: ["schedules"] });
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed"),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    createMutation.mutate({
      ...form,
      manual_times:
        form.dispatch_mode === "manual"
          ? manualTimesStr
              .split(",")
              .map((t) => t.trim())
              .filter(Boolean)
          : [],
    });
  }

  async function pauseEngine() {
    try {
      await api.pauseScheduler();
      toast.success("Scheduler paused");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed");
    }
  }

  async function resumeEngine() {
    try {
      await api.resumeScheduler();
      toast.success("Scheduler resumed");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed");
    }
  }

  return (
    <>
      <PageHeader
        title="Scheduler"
        description="Assign prepared batches to publish dates and times."
        actions={
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={pauseEngine}>
              <Pause size={14} /> Pause engine
            </Button>
            <Button size="sm" variant="outline" onClick={resumeEngine}>
              <Play size={14} /> Resume engine
            </Button>
          </div>
        }
      />

      {/* Create schedule form */}
      <form
        onSubmit={handleSubmit}
        className="rounded-lg border border-border bg-card p-6 mb-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4"
      >
        <div className="space-y-2">
          <Label>Name</Label>
          <Input
            required
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="Morning vocab drop"
          />
        </div>

        <div className="space-y-2">
          <Label>Prepared batch</Label>
          <Select
            required
            value={String(form.batch_id || "")}
            onValueChange={(v) => setForm({ ...form, batch_id: Number(v) })}
          >
            <SelectTrigger>
              <SelectValue placeholder="Select batch" />
            </SelectTrigger>
            <SelectContent>
              {readyBatches.map((b) => (
                <SelectItem key={b.id} value={String(b.id)}>
                  {b.name} · {b.generated_items} posts
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label>Timezone</Label>
          <Input
            value={form.timezone}
            onChange={(e) => setForm({ ...form, timezone: e.target.value })}
          />
        </div>

        <div className="space-y-2">
          <Label>Start date</Label>
          <Input
            required
            type="date"
            value={form.start_date}
            onChange={(e) => setForm({ ...form, start_date: e.target.value })}
          />
        </div>

        <div className="space-y-2">
          <Label>End date</Label>
          <Input
            required
            type="date"
            value={form.end_date}
            onChange={(e) => setForm({ ...form, end_date: e.target.value })}
          />
        </div>

        <div className="space-y-2">
          <Label>Posts per day</Label>
          <Input
            type="number"
            min={1}
            value={form.posts_per_day}
            onChange={(e) =>
              setForm({ ...form, posts_per_day: Number(e.target.value) })
            }
          />
        </div>

        <div className="space-y-2">
          <Label>Timing mode</Label>
          <Select
            value={form.dispatch_mode}
            onValueChange={(v) =>
              setForm({ ...form, dispatch_mode: v as "even" | "manual" })
            }
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="even">Evenly spaced</SelectItem>
              <SelectItem value="manual">Specific times</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {form.dispatch_mode === "even" ? (
          <>
            <div className="space-y-2">
              <Label>From</Label>
              <Input
                type="time"
                value={form.window_start}
                onChange={(e) =>
                  setForm({ ...form, window_start: e.target.value })
                }
              />
            </div>
            <div className="space-y-2">
              <Label>Until</Label>
              <Input
                type="time"
                value={form.window_end}
                onChange={(e) =>
                  setForm({ ...form, window_end: e.target.value })
                }
              />
            </div>
          </>
        ) : (
          <div className="space-y-2 sm:col-span-2">
            <Label>Specific times (comma-separated)</Label>
            <Input
              value={manualTimesStr}
              onChange={(e) => setManualTimesStr(e.target.value)}
              placeholder="09:00,12:00,15:00"
            />
          </div>
        )}

        <div className="sm:col-span-2 lg:col-span-3 flex justify-end">
          <Button type="submit" size="sm" disabled={createMutation.isPending}>
            <Plus size={14} /> Create schedule
          </Button>
        </div>
      </form>

      {/* Schedules table */}
      <div className="rounded-lg border border-border bg-card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/40 text-muted-foreground text-xs">
            <tr>
              <th className="px-4 py-3 text-left font-medium">Name</th>
              <th className="px-4 py-3 text-left font-medium">Batch</th>
              <th className="px-4 py-3 text-left font-medium hidden md:table-cell">Date range</th>
              <th className="px-4 py-3 text-left font-medium hidden lg:table-cell">Plan</th>
              <th className="px-4 py-3 text-left font-medium">Posts</th>
              <th className="px-4 py-3 text-left font-medium">Status</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {schedules.length === 0 ? (
              <tr>
                <td
                  colSpan={7}
                  className="px-4 py-6 text-center text-sm text-muted-foreground"
                >
                  No schedules yet.
                </td>
              </tr>
            ) : null}
            {schedules.map((s) => (
              <tr key={s.id} className="hover:bg-muted/20">
                <td className="px-4 py-3 font-medium">{s.name}</td>
                <td className="px-4 py-3 text-muted-foreground">
                  {s.batch_name ?? "—"}
                </td>
                <td className="px-4 py-3 text-muted-foreground hidden md:table-cell">
                  {s.start_date} → {s.end_date}
                </td>
                <td className="px-4 py-3 text-muted-foreground hidden lg:table-cell">
                  {s.dispatch_mode === "manual"
                    ? s.manual_times.join(", ")
                    : `${s.posts_per_day}/day, ${s.window_start}–${s.window_end}`}
                </td>
                <td className="px-4 py-3">{s.scheduled_post_count}</td>
                <td className="px-4 py-3">
                  <Badge variant={s.is_paused ? "secondary" : "outline"}>
                    {s.is_paused ? "Paused" : "Active"}
                  </Badge>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-1 justify-end">
                    <Button
                      size="icon"
                      variant="ghost"
                      className="size-7"
                      onClick={() =>
                        toggleMutation.mutate({
                          id: s.id,
                          is_paused: !s.is_paused,
                        })
                      }
                      title={s.is_paused ? "Resume" : "Pause"}
                    >
                      {s.is_paused ? <Play size={14} /> : <Pause size={14} />}
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      className="size-7 text-destructive hover:text-destructive"
                      onClick={() => {
                        if (
                          confirm(
                            "Delete this schedule? Unpublished posts return to the batch.",
                          )
                        ) {
                          deleteMutation.mutate(s.id);
                        }
                      }}
                      title="Delete"
                    >
                      <Trash2 size={14} />
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
