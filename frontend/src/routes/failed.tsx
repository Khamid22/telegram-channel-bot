import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { RotateCcw } from "lucide-react";

export const Route = createFileRoute("/failed")({
  component: FailedPage,
});

function FailedPage() {
  const qc = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["failedJobs"],
    queryFn: api.failedJobs,
  });

  const retryMutation = useMutation({
    mutationFn: api.publishPost,
    onSuccess: () => {
      toast.success("Retry triggered");
      void qc.invalidateQueries({ queryKey: ["failedJobs"] });
      void qc.invalidateQueries({ queryKey: ["queue"] });
      void qc.invalidateQueries({ queryKey: ["analytics"] });
    },
    onError: (err) =>
      toast.error(err instanceof Error ? err.message : "Retry failed"),
  });

  const items = data?.items ?? [];

  return (
    <>
      <PageHeader
        title="Failed Jobs"
        description="Posts that failed to publish. Retry to queue them again."
      />

      {isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 2 }).map((_, i) => (
            <div
              key={i}
              className="rounded-lg border border-border bg-card p-5 h-20 animate-pulse"
            />
          ))}
        </div>
      )}

      {!isLoading && items.length === 0 && (
        <div className="rounded-lg border border-border bg-card px-5 py-12 text-center text-sm text-muted-foreground">
          No failed jobs. All good!
        </div>
      )}

      <div className="space-y-3">
        {items.map((post) => (
          <article
            key={post.id}
            className="rounded-lg border border-destructive/30 bg-card p-5 flex items-start gap-4"
          >
            <div className="flex-1 min-w-0 space-y-1">
              <div className="flex items-center gap-2">
                <h3 className="font-semibold">{post.word.word}</h3>
                <Badge variant="destructive">failed</Badge>
              </div>
              {post.error_message && (
                <p className="text-sm text-muted-foreground">
                  {post.error_message}
                </p>
              )}
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={() => retryMutation.mutate(post.id)}
              disabled={retryMutation.isPending}
            >
              <RotateCcw size={14} /> Retry
            </Button>
          </article>
        ))}
      </div>
    </>
  );
}
