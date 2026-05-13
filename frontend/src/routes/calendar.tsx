import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { format } from "date-fns";

export const Route = createFileRoute("/calendar")({
  component: CalendarPage,
});

const statusVariant = (status: string): "secondary" | "outline" | "destructive" => {
  if (status === "published") return "outline";
  if (status === "failed") return "destructive";
  return "secondary";
};

function CalendarPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["calendar"],
    queryFn: api.calendar,
  });

  const items = data?.items ?? [];

  return (
    <>
      <PageHeader
        title="Calendar"
        description="All posts with their scheduled and published times."
      />

      <div className="rounded-lg border border-border bg-card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/40 text-muted-foreground text-xs">
            <tr>
              <th className="px-4 py-3 text-left font-medium">Word</th>
              <th className="px-4 py-3 text-left font-medium">Status</th>
              <th className="px-4 py-3 text-left font-medium hidden sm:table-cell">
                Scheduled
              </th>
              <th className="px-4 py-3 text-left font-medium hidden md:table-cell">
                Published
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i}>
                  <td colSpan={4} className="px-4 py-3">
                    <div className="h-4 bg-muted animate-pulse rounded" />
                  </td>
                </tr>
              ))
            ) : items.length === 0 ? (
              <tr>
                <td
                  colSpan={4}
                  className="px-4 py-8 text-center text-muted-foreground"
                >
                  No posts yet.
                </td>
              </tr>
            ) : (
              items.map((post) => (
                <tr key={post.id} className="hover:bg-muted/20">
                  <td className="px-4 py-3 font-medium">{post.word.word}</td>
                  <td className="px-4 py-3">
                    <Badge variant={statusVariant(post.status)}>
                      {post.status}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground hidden sm:table-cell">
                    {post.scheduled_at
                      ? format(new Date(post.scheduled_at), "dd MMM yyyy, HH:mm")
                      : "Unscheduled"}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground hidden md:table-cell">
                    {post.published_at
                      ? format(new Date(post.published_at), "dd MMM yyyy, HH:mm")
                      : "—"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
