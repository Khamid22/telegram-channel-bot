import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, useMemo, useEffect } from "react";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { api, type Batch, type GenerationJob, type VocabRow } from "@/lib/api";
import { toast } from "sonner";
import {
  BookOpen,
  Eye,
  FileText,
  FolderOpen,
  Loader2,
  RefreshCw,
  Sparkles,
  Upload,
} from "lucide-react";

export const Route = createFileRoute("/generator")({
  component: GeneratorPage,
});

function rowLabel(row: VocabRow, index: number) {
  return row.word ? `${index + 1}. ${row.word}` : `Row ${index + 1}`;
}

const activeGenerationStatuses = new Set(["queued", "generating", "cancelling"]);

function GeneratorPage() {
  const qc = useQueryClient();

  // ── catalog (Drive folders + CSV files) ──────────────────────────────────
  const {
    data: catalogData,
    isLoading: catalogLoading,
    refetch: refetchCatalog,
  } = useQuery({
    queryKey: ["driveVocabulary"],
    queryFn: api.driveVocabulary,
  });

  const { data: templatesData } = useQuery({
    queryKey: ["templates"],
    queryFn: api.templates,
  });

  // ── local state ──────────────────────────────────────────────────────────
  const [collectionId, setCollectionId] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [rows, setRows] = useState<VocabRow[]>([]);
  const [rowIndex, setRowIndex] = useState(0);
  const [templateId, setTemplateId] = useState("");
  const [batchName, setBatchName] = useState("");
  const [captionText, setCaptionText] = useState("");
  const [preview, setPreview] = useState<{
    image_url: string;
    caption: string;
  } | null>(null);
  const [createdBatch, setCreatedBatch] = useState<{
    name: string;
    generated_items: number;
  } | null>(null);
  const [generationDialogOpen, setGenerationDialogOpen] = useState(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [generationJob, setGenerationJob] = useState<GenerationJob | null>(
    null,
  );

  const catalog = catalogData ?? { collections: [], sources: [] };
  const templates = templatesData?.items ?? [];

  const generationJobQuery = useQuery({
    queryKey: ["generationJob", activeJobId],
    queryFn: () => api.vocabularyBatchJob(activeJobId!),
    enabled: Boolean(activeJobId),
    refetchInterval: activeJobId ? 1000 : false,
  });

  const sourcesForCollection = useMemo(
    () =>
      catalog.sources.filter(
        (s) =>
          !collectionId || String(s.collection_id) === String(collectionId),
      ),
    [catalog.sources, collectionId],
  );

  const currentRow = rows[rowIndex] ?? null;
  const selectedSource = catalog.sources.find(
    (s) => String(s.id) === String(sourceId),
  );
  const selectedTemplate = templates.find(
    (t) => String(t.id) === String(templateId),
  );
  const liveGenerationJob = generationJobQuery.data?.job ?? generationJob;
  const generationRunning = liveGenerationJob
    ? activeGenerationStatuses.has(liveGenerationJob.status)
    : false;
  const generationTotal = liveGenerationJob?.total_items || rows.length || 0;
  const generationDone = liveGenerationJob?.generated_items ?? 0;
  const generationPercent =
    liveGenerationJob?.percent ??
    (generationTotal ? Math.round((generationDone / generationTotal) * 100) : 0);

  // Auto-select active template
  useEffect(() => {
    if (!templateId && templates.length) {
      const active = templates.find((t) => t.is_active) ?? templates[0];
      setTemplateId(String(active.id));
    }
  }, [templateId, templates]);

  useEffect(() => {
    if (!activeJobId || !generationJobQuery.data?.job) return;

    const job = generationJobQuery.data.job;
    setGenerationJob(job);

    if (job.status === "ready") {
      const batch = generationJobQuery.data.item as Batch | undefined;
      if (batch) {
        setCreatedBatch(batch);
        toast.success(`${batch.generated_items} posts generated and saved to Drive`);
      } else {
        toast.success("Posts generated and saved to Drive");
      }
      setActiveJobId(null);
      void qc.invalidateQueries({ queryKey: ["batches"] });
      void qc.invalidateQueries({ queryKey: ["driveVocabulary"] });
      return;
    }

    if (job.status === "failed") {
      toast.error(job.error || "Generation failed");
      setActiveJobId(null);
      return;
    }

    if (job.status === "cancelled") {
      toast.info("Generation cancelled");
      setActiveJobId(null);
    }
  }, [
    activeJobId,
    generationJobQuery.data?.job,
    generationJobQuery.data?.item,
    qc,
  ]);

  // ── mutations ─────────────────────────────────────────────────────────────
  const refreshMutation = useMutation({
    mutationFn: api.refreshDrive,
    onSuccess: (data) => {
      void qc.invalidateQueries({ queryKey: ["driveVocabulary"] });
      toast.success(
        `Drive refreshed: ${data.collections.length} folders, ${data.sources.length} CSV files`,
      );
    },
    onError: (err) =>
      toast.error(err instanceof Error ? err.message : "Refresh failed"),
  });

  const uploadMutation = useMutation({
    mutationFn: api.uploadVocabularySource,
    onSuccess: (data) => {
      setRows(data.rows);
      setRowIndex(0);
      setSourceId(String(data.source.id));
      setBatchName(data.source.name.replace(/\.csv$/i, ""));
      void qc.invalidateQueries({ queryKey: ["driveVocabulary"] });
      toast.success(`${data.rows.length} vocabulary rows loaded from Drive`);
    },
    onError: (err) =>
      toast.error(err instanceof Error ? err.message : "Upload failed"),
  });

  const loadSourceMutation = useMutation({
    mutationFn: api.vocabularySourceRows,
    onSuccess: (data) => {
      setRows(data.rows);
      setRowIndex(0);
      setBatchName(data.source.name.replace(/\.csv$/i, ""));
    },
    onError: (err) =>
      toast.error(err instanceof Error ? err.message : "Failed to load rows"),
  });

  const previewMutation = useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: number;
      payload: Record<string, string>;
    }) => api.previewTemplate(id, payload),
    onSuccess: (data) => {
      setPreview(data);
    },
    onError: (err) =>
      toast.error(err instanceof Error ? err.message : "Preview failed"),
  });

  const generateMutation = useMutation({
    mutationFn: api.generateVocabularyBatch,
    onSuccess: (data) => {
      setCreatedBatch(null);
      setGenerationJob(data.job);
      setActiveJobId(data.job.id);
      setGenerationDialogOpen(true);
      toast.success("Generation started");
    },
    onError: (err) =>
      toast.error(err instanceof Error ? err.message : "Generation failed"),
  });

  const cancelGenerationMutation = useMutation({
    mutationFn: api.cancelVocabularyBatchJob,
    onSuccess: (data) => {
      setGenerationJob(data.job);
      toast.info("Cancelling generation after the current item");
    },
    onError: (err) =>
      toast.error(err instanceof Error ? err.message : "Cancel failed"),
  });

  // ── handlers ──────────────────────────────────────────────────────────────
  function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!collectionId || !uploadFile) {
      toast.error("Choose a vocabulary folder and CSV file first.");
      return;
    }
    const body = new FormData();
    body.append("collection_id", collectionId);
    body.append("file", uploadFile);
    uploadMutation.mutate(body);
  }

  function handleLoadSource(id: string) {
    setSourceId(id);
    if (!id) {
      setRows([]);
      setPreview(null);
      return;
    }
    loadSourceMutation.mutate(id);
  }

  function handlePreview() {
    if (!selectedTemplate || !currentRow) {
      toast.error("Select a template and a CSV row to preview.");
      return;
    }
    previewMutation.mutate({
      id: selectedTemplate.id,
      payload: {
        ...(currentRow as unknown as Record<string, string>),
        caption_text: captionText,
      },
    });
  }

  function handleGenerate(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedSource || !selectedTemplate || !rows.length) {
      toast.error("Load a Drive CSV source and choose a saved template first.");
      return;
    }
    generateMutation.mutate({
      source_file_id: selectedSource.id,
      template_id: selectedTemplate.id,
      name: batchName,
      caption_text: captionText,
    });
  }

  return (
    <>
      <PageHeader
        title="Generator"
        description="Prepare vocabulary batches from Google Drive CSV files."
        actions={
          <Button
            size="sm"
            variant="outline"
            onClick={() => refreshMutation.mutate()}
            disabled={refreshMutation.isPending || catalogLoading}
          >
            {refreshMutation.isPending ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <RefreshCw size={14} />
            )}
            Refresh Drive
          </Button>
        }
      />

      <div className="grid lg:grid-cols-[1fr_1fr] gap-6 mb-6">
        {/* Vocabulary source panel */}
        <form
          onSubmit={handleUpload}
          className="rounded-lg border border-border bg-card p-5 space-y-4"
        >
          <div className="flex items-center gap-2 text-sm font-medium">
            <FolderOpen size={15} className="text-muted-foreground" />
            Vocabulary source
          </div>

          <div className="space-y-2">
            <Label>Drive folder</Label>
            <Select
              value={collectionId}
              onValueChange={setCollectionId}
            >
              <SelectTrigger>
                <SelectValue
                  placeholder={
                    catalogLoading ? "Loading…" : "Select folder"
                  }
                />
              </SelectTrigger>
              <SelectContent>
                {catalog.collections.map((c) => (
                  <SelectItem key={String(c.id)} value={String(c.id)}>
                    {c.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Upload local CSV</Label>
            <Input
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)}
            />
          </div>

          <Button
            type="submit"
            size="sm"
            disabled={uploadMutation.isPending || !uploadFile}
          >
            {uploadMutation.isPending ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Upload size={14} />
            )}
            Upload to Drive
          </Button>

          <div className="space-y-2">
            <Label>Or use existing Drive CSV</Label>
            <Select
              value={sourceId}
              onValueChange={handleLoadSource}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select CSV file" />
              </SelectTrigger>
              <SelectContent>
                {sourcesForCollection.map((s) => (
                  <SelectItem key={String(s.id)} value={String(s.id)}>
                    {s.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </form>

        {/* Batch setup panel */}
        <form
          onSubmit={handleGenerate}
          className="rounded-lg border border-border bg-card p-5 space-y-4"
        >
          <div className="flex items-center gap-2 text-sm font-medium">
            <Sparkles size={15} className="text-muted-foreground" />
            Batch setup
          </div>

          <div className="space-y-2">
            <Label>Saved template</Label>
            <Select value={templateId} onValueChange={setTemplateId}>
              <SelectTrigger>
                <SelectValue placeholder="Select template" />
              </SelectTrigger>
              <SelectContent>
                {templates.map((t) => (
                  <SelectItem key={t.id} value={String(t.id)}>
                    {t.name}
                    {t.is_active && (
                      <span className="ml-2 text-xs text-muted-foreground">
                        (active)
                      </span>
                    )}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Batch name</Label>
            <Input
              value={batchName}
              onChange={(e) => setBatchName(e.target.value)}
              placeholder="May new words"
            />
          </div>

          <div className="space-y-2">
            <Label>Telegram caption / hashtags</Label>
            <Textarea
              value={captionText}
              onChange={(e) => setCaptionText(e.target.value)}
              placeholder={"#vocabulary\nDaily vocabulary post"}
              rows={3}
            />
          </div>

          <div className="flex gap-2">
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={handlePreview}
              disabled={!rows.length || previewMutation.isPending}
            >
              {previewMutation.isPending ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Eye size={14} />
              )}
              Preview row
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={!rows.length || generateMutation.isPending || generationRunning}
            >
              {generateMutation.isPending || generationRunning ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Sparkles size={14} />
              )}
              Generate all posts
            </Button>
          </div>
        </form>
      </div>

      {/* CSV review + preview */}
      {rows.length > 0 && (
        <div className="grid lg:grid-cols-[1fr_1fr] gap-6 mb-6">
          {/* CSV row list */}
          <div className="rounded-lg border border-border bg-card overflow-hidden">
            <div className="flex items-center gap-2 px-5 h-11 border-b border-border text-sm font-medium">
              <FileText size={15} className="text-muted-foreground" />
              CSV review ({rows.length} rows)
            </div>
            <div className="divide-y divide-border max-h-80 overflow-y-auto">
              {rows.map((row, i) => (
                <button
                  key={row.source_row_key}
                  onClick={() => setRowIndex(i)}
                  className={`w-full text-left px-5 py-3 transition-colors ${
                    i === rowIndex
                      ? "bg-secondary"
                      : "hover:bg-muted/40"
                  }`}
                >
                  <div className="text-sm font-medium truncate">
                    {rowLabel(row, i)}
                  </div>
                  <div className="text-xs text-muted-foreground truncate">
                    {row.word_type ?? "word"} · {row.definition}
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Preview panel */}
          <div className="rounded-lg border border-border bg-card overflow-hidden">
            <div className="flex items-center gap-2 px-5 h-11 border-b border-border text-sm font-medium">
              <BookOpen size={15} className="text-muted-foreground" />
              Preview
            </div>
            {preview ? (
              <div className="flex flex-col gap-4 p-5">
                <img
                  src={preview.image_url}
                  alt="Vocabulary template preview"
                  className="rounded border border-border max-h-52 object-contain"
                />
                {currentRow && (
                  <div className="space-y-1">
                    <div className="font-semibold">{currentRow.word}</div>
                    <div className="text-sm text-muted-foreground">
                      {currentRow.definition}
                    </div>
                    {currentRow.example && (
                      <div className="text-xs text-muted-foreground italic">
                        {currentRow.example}
                      </div>
                    )}
                  </div>
                )}
                {preview.caption && (
                  <pre className="text-xs bg-muted rounded p-2 whitespace-pre-wrap">
                    {preview.caption}
                  </pre>
                )}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-48 gap-3 text-muted-foreground">
                <BookOpen size={32} />
                <span className="text-sm">
                  {currentRow
                    ? 'Click “Preview row” to render'
                    : "Select a row to preview"}
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Success result */}
      {createdBatch && (
        <div className="rounded-lg border border-border bg-card px-5 py-4 flex items-center gap-3">
          <Sparkles size={16} className="text-muted-foreground shrink-0" />
          <div>
            <div className="font-medium text-sm">{createdBatch.name}</div>
            <div className="text-xs text-muted-foreground">
              {createdBatch.generated_items} Drive-backed posts are ready for
              the Scheduler.
            </div>
          </div>
          <Badge variant="outline" className="ml-auto">
            Ready
          </Badge>
        </div>
      )}

      <Dialog
        open={generationDialogOpen}
        onOpenChange={(open) => {
          if (!open && generationRunning) return;
          setGenerationDialogOpen(open);
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Generating posts</DialogTitle>
            <DialogDescription>
              Images, audio, and Telegram captions are being prepared in Drive.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">
                {liveGenerationJob?.status === "cancelling"
                  ? "Cancelling"
                  : liveGenerationJob?.status === "ready"
                    ? "Complete"
                    : liveGenerationJob?.status === "failed"
                      ? "Failed"
                      : liveGenerationJob?.status === "cancelled"
                        ? "Cancelled"
                        : "Processing"}
              </span>
              <span className="font-medium">{generationPercent}%</span>
            </div>
            <Progress value={generationPercent} />
            <div className="text-sm text-muted-foreground">
              {generationDone} of {generationTotal || "?"} images processed
            </div>
            {liveGenerationJob?.error && (
              <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {liveGenerationJob.error}
              </div>
            )}
          </div>

          <DialogFooter>
            {generationRunning ? (
              <Button
                type="button"
                variant="outline"
                onClick={() =>
                  liveGenerationJob &&
                  cancelGenerationMutation.mutate(liveGenerationJob.id)
                }
                disabled={
                  !liveGenerationJob ||
                  liveGenerationJob.status === "cancelling" ||
                  cancelGenerationMutation.isPending
                }
              >
                {cancelGenerationMutation.isPending ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : null}
                Cancel
              </Button>
            ) : (
              <Button type="button" onClick={() => setGenerationDialogOpen(false)}>
                Close
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
