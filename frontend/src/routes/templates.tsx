import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, useRef } from "react";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Check, Eye, FileImage, Upload } from "lucide-react";

export const Route = createFileRoute("/templates")({
  component: TemplatesPage,
});

const PREVIEW_PAYLOAD = {
  word: "resilient",
  word_type: "adjective",
  phonetic: "/rɪˈzɪl.i.ənt/",
  definition: "Able to recover quickly after difficulty or change.",
  example: "A resilient team keeps learning even when the plan changes.",
  level: "B2",
};

function TemplatesPage() {
  const qc = useQueryClient();
  const formRef = useRef<HTMLFormElement>(null);
  const [name, setName] = useState("");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [configFile, setConfigFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<{
    image_url: string;
    caption: string;
  } | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["templates"],
    queryFn: api.templates,
  });

  const uploadMutation = useMutation({
    mutationFn: (formData: FormData) => api.uploadTemplate(formData),
    onSuccess: () => {
      toast.success("Template uploaded");
      setName("");
      setImageFile(null);
      setConfigFile(null);
      formRef.current?.reset();
      void qc.invalidateQueries({ queryKey: ["templates"] });
    },
    onError: (err) =>
      toast.error(err instanceof Error ? err.message : "Upload failed"),
  });

  const activateMutation = useMutation({
    mutationFn: api.activateTemplate,
    onSuccess: () => {
      toast.success("Template activated");
      void qc.invalidateQueries({ queryKey: ["templates"] });
    },
    onError: (err) =>
      toast.error(err instanceof Error ? err.message : "Failed"),
  });

  const fontMutation = useMutation({
    mutationFn: (formData: FormData) => api.uploadFont(formData),
    onSuccess: () => toast.success("Font uploaded"),
    onError: (err) =>
      toast.error(err instanceof Error ? err.message : "Font upload failed"),
  });

  function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!imageFile) return;
    const body = new FormData();
    body.append("name", name);
    body.append("image", imageFile);
    if (configFile) body.append("config", configFile);
    uploadMutation.mutate(body);
  }

  async function handlePreview(id: number) {
    try {
      const data = await api.previewTemplate(id, PREVIEW_PAYLOAD);
      setPreview(data);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Preview failed");
    }
  }

  function handleFontUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const body = new FormData();
    body.append("font", file);
    fontMutation.mutate(body);
  }

  const templates = data?.items ?? [];

  return (
    <>
      <PageHeader
        title="Template Library"
        description="Upload and manage visual templates for your posts."
      />

      {/* Upload form */}
      <form
        ref={formRef}
        onSubmit={handleUpload}
        className="rounded-lg border border-border bg-card p-6 mb-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"
      >
        <div className="space-y-2">
          <Label>Name</Label>
          <Input
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Vocabulary card v2"
          />
        </div>
        <div className="space-y-2">
          <Label>Image (PNG / JPG)</Label>
          <Input
            required
            type="file"
            accept="image/png,image/jpeg"
            onChange={(e) => setImageFile(e.target.files?.[0] ?? null)}
          />
        </div>
        <div className="space-y-2">
          <Label>JSON config (optional)</Label>
          <Input
            type="file"
            accept="application/json"
            onChange={(e) => setConfigFile(e.target.files?.[0] ?? null)}
          />
        </div>
        <div className="space-y-2">
          <Label>Upload font (optional)</Label>
          <Input type="file" accept=".ttf,.otf,.woff,.woff2" onChange={handleFontUpload} />
        </div>
        <div className="sm:col-span-2 lg:col-span-4 flex justify-end">
          <Button type="submit" size="sm" disabled={uploadMutation.isPending}>
            <Upload size={14} /> Upload template
          </Button>
        </div>
      </form>

      {/* Preview */}
      {preview && (
        <div className="rounded-lg border border-border bg-card p-5 mb-6 flex flex-col sm:flex-row gap-5">
          <img
            src={preview.image_url}
            alt="Template preview"
            className="rounded border border-border max-h-64 object-contain"
          />
          <pre className="text-xs text-muted-foreground whitespace-pre-wrap flex-1">
            {preview.caption}
          </pre>
        </div>
      )}

      {/* Template grid */}
      {isLoading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="rounded-lg border border-border bg-card h-60 animate-pulse"
            />
          ))}
        </div>
      )}

      {!isLoading && templates.length === 0 && (
        <div className="rounded-lg border border-border bg-card px-5 py-12 text-center text-sm text-muted-foreground">
          No templates yet. Upload one above.
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {templates.map((t) => (
          <article
            key={t.id}
            className="rounded-lg border border-border bg-card overflow-hidden flex flex-col"
          >
            <img
              src={t.image_url}
              alt={t.name}
              className="w-full h-44 object-cover border-b border-border"
            />
            <div className="p-4 flex-1 flex flex-col gap-3">
              <div className="flex items-center gap-2">
                <FileImage size={15} className="text-muted-foreground" />
                <span className="font-medium text-sm">{t.name}</span>
                <Badge
                  variant={t.is_active ? "outline" : "secondary"}
                  className="ml-auto"
                >
                  {t.is_active ? "Active" : "Inactive"}
                </Badge>
              </div>
              <div className="flex gap-2 mt-auto">
                <Button
                  size="sm"
                  variant="outline"
                  className="flex-1"
                  onClick={() => handlePreview(t.id)}
                >
                  <Eye size={14} /> Preview
                </Button>
                <Button
                  size="sm"
                  className="flex-1"
                  onClick={() => activateMutation.mutate(t.id)}
                  disabled={activateMutation.isPending || t.is_active}
                >
                  <Check size={14} /> Activate
                </Button>
              </div>
            </div>
          </article>
        ))}
      </div>
    </>
  );
}
