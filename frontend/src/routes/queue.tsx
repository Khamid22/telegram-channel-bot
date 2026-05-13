import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Play, Volume2 } from "lucide-react";

export const Route = createFileRoute("/queue")({
  component: QueuePage,
});

function QueuePage() {
  const qc = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["queue"],
    queryFn: api.queue,
  });

  const publishMutation = useMutation({
    mutationFn: api.publishPost,
    onSuccess: () => {
      toast.success("Post published");
      void qc.invalidateQueries({ queryKey: ["queue"] });
      void qc.invalidateQueries({ queryKey: ["analytics"] });
    },
    onError: (err) =>
      toast.error(err instanceof Error ? err.message : "Publish failed"),
  });

  const manualPublishMutation = useMutation({
    mutationFn: api.publishManual,
    onSuccess: () => {
      toast.success("Manual publish triggered");
      void qc.invalidateQueries({ queryKey: ["queue"] });
    },
    onError: (err) =>
      toast.error(err instanceof Error ? err.message : "Failed"),
  });

  const items = data?.items ?? [];

  return (
    <>
      <PageHeader
        title="Queue"
        description="Posts waiting to be published."
        actions={
          <Button
            size="sm"
            onClick={() => manualPublishMutation.mutate()}
            disabled={manualPublishMutation.isPending}
          >
            <Play size={14} /> Manual publish
          </Button>
        }
      />

      {isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="rounded-lg border border-border bg-card p-5 h-28 animate-pulse"
            />
          ))}
        </div>
      )}

      {!isLoading && items.length === 0 && (
        <div className="rounded-lg border border-border bg-card px-5 py-12 text-center text-sm text-muted-foreground">
          Queue is empty.
        </div>
      )}

      <div className="space-y-3">
        {items.map((post) => (
          <article
            key={post.id}
            className="rounded-lg border border-border bg-card p-5 flex flex-col sm:flex-row gap-4"
          >
            <div className="flex-1 min-w-0 space-y-1">
              <div className="flex items-center gap-2">
                <h3 className="font-semibold">{post.word.word}</h3>
                <Badge variant="secondary">{post.status}</Badge>
              </div>
              {post.word.phonetic && (
                <p className="text-sm text-muted-foreground">
                  {post.word.phonetic}
                </p>
              )}
              {post.word.definition && (
                <p className="text-sm text-muted-foreground line-clamp-2">
                  {post.word.definition}
                </p>
              )}
            </div>

            <div className="flex flex-col gap-3 sm:items-end">
              {post.image_url && (
                <img
                  src={post.image_url}
                  alt={post.word.word}
                  className="h-20 w-20 rounded object-cover border border-border"
                />
              )}

              {post.audio.length > 0 ? (
                <div className="space-y-1">
                  {post.audio.map((a) => (
                    <audio
                      key={a.id}
                      controls
                      src={a.url}
                      className="h-8 w-48"
                      aria-label="pronunciation audio"
                    />
                  ))}
                </div>
              ) : (
                <span className="text-xs text-muted-foreground flex items-center gap-1">
                  <Volume2 size={12} /> audio after publish
                </span>
              )}

              <Button
                size="sm"
                onClick={() => publishMutation.mutate(post.id)}
                disabled={publishMutation.isPending}
              >
                <Play size={14} /> Publish
              </Button>
            </div>
          </article>
        ))}
      </div>
    </>
  );
}
