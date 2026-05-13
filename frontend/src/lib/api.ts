const API_BASE = import.meta.env.VITE_API_BASE || "";

async function request<T = Record<string, unknown>>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const isFormData = options.body instanceof FormData;
  const headers: Record<string, string> = isFormData
    ? {}
    : { "Content-Type": "application/json" };

  const response = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    ...options,
    headers: {
      ...headers,
      ...(options.headers as Record<string, string> | undefined),
    },
  });

  const text = await response.text();
  let data: Record<string, unknown> = {};
  try {
    data = text ? (JSON.parse(text) as Record<string, unknown>) : {};
  } catch {
    data = { error: text || "Request failed" };
  }
  if (!response.ok) {
    throw new Error((data.error as string) || "Request failed");
  }
  return data as T;
}

export const api = {
  me: () => request<{ user: User }>("/api/me"),
  login: (payload: { username: string; password: string }) =>
    request<{ user: User }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  logout: () => request("/api/auth/logout", { method: "POST" }),

  analytics: () => request<Analytics>("/api/analytics"),

  schedules: () => request<{ items: Schedule[] }>("/api/schedules"),
  createSchedule: (payload: CreateSchedulePayload) =>
    request("/api/schedules", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateSchedule: (id: number, payload: Partial<Schedule>) =>
    request(`/api/schedules/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  deleteSchedule: (id: number) =>
    request(`/api/schedules/${id}`, { method: "DELETE" }),
  pauseScheduler: () => request("/api/scheduler/pause", { method: "POST" }),
  resumeScheduler: () => request("/api/scheduler/resume", { method: "POST" }),

  queue: () => request<{ items: Post[] }>("/api/queue"),
  publishManual: () => request("/api/publish/manual", { method: "POST" }),
  publishPost: (id: number) =>
    request(`/api/publish/${id}`, { method: "POST" }),
  deletePost: (id: number) =>
    request(`/api/posts/${id}`, { method: "DELETE" }),

  calendar: () => request<{ items: Post[] }>("/api/calendar"),
  failedJobs: () => request<{ items: Post[] }>("/api/failed-jobs"),

  driveOAuthStatus: () => request<DriveStatus>("/api/drive/oauth/status"),
  startDriveOAuth: () =>
    request<{ authorization_url: string }>("/api/drive/oauth/start", {
      method: "POST",
    }),
  driveVocabulary: () =>
    request<{ collections: Collection[]; sources: Source[] }>(
      "/api/drive/vocabulary",
    ),
  refreshDrive: () =>
    request<{ collections: Collection[]; sources: Source[] }>(
      "/api/drive/refresh",
      { method: "POST" },
    ),

  templates: () => request<{ items: Template[] }>("/api/templates"),
  activateTemplate: (id: number) =>
    request(`/api/templates/${id}/activate`, { method: "POST" }),
  previewTemplate: (id: number, payload: Record<string, string>) =>
    request<{ image_url: string; caption: string }>(
      `/api/templates/${id}/preview`,
      { method: "POST", body: JSON.stringify(payload) },
    ),
  uploadTemplate: (payload: FormData) =>
    request("/api/templates", { method: "POST", body: payload }),
  uploadFont: (payload: FormData) =>
    request("/api/fonts", { method: "POST", body: payload }),

  vocabularyBatches: () =>
    request<{ items: Batch[] }>("/api/generator/vocabulary/batches"),
  uploadVocabularySource: (payload: FormData) =>
    request<{ source: Source; rows: VocabRow[] }>(
      "/api/generator/vocabulary/upload-source",
      { method: "POST", body: payload },
    ),
  vocabularySourceRows: (id: number | string) =>
    request<{ source: Source; rows: VocabRow[] }>(
      `/api/generator/vocabulary/sources/${id}/rows`,
    ),
  generateVocabularyBatch: (payload: GenerateBatchPayload) =>
    request<{ job: GenerationJob }>("/api/generator/vocabulary/batches", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  vocabularyBatchJob: (id: string) =>
    request<{ job: GenerationJob; item?: Batch }>(
      `/api/generator/vocabulary/batches/jobs/${id}`,
    ),
  cancelVocabularyBatchJob: (id: string) =>
    request<{ job: GenerationJob }>(
      `/api/generator/vocabulary/batches/jobs/${id}/cancel`,
      { method: "POST" },
    ),
};

// ─── Types ───────────────────────────────────────────────────────────────────

export interface User {
  username: string;
}

export interface Analytics {
  words: number;
  queued: number;
  published: number;
  failed: number;
  templates: number;
  recent_logs: LogEntry[];
}

export interface LogEntry {
  level: string;
  message: string;
  timestamp: string;
}

export interface Schedule {
  id: number;
  name: string;
  batch_id: number;
  batch_name?: string;
  timezone: string;
  start_date: string;
  end_date: string;
  posts_per_day: number;
  dispatch_mode: "even" | "manual";
  window_start: string;
  window_end: string;
  manual_times: string[];
  is_paused: boolean;
  scheduled_post_count: number;
}

export interface CreateSchedulePayload {
  name: string;
  batch_id: number;
  timezone: string;
  start_date: string;
  end_date: string;
  posts_per_day: number;
  dispatch_mode: "even" | "manual";
  window_start: string;
  window_end: string;
  manual_times: string[];
}

export interface Post {
  id: number;
  status: string;
  word: {
    word: string;
    phonetic?: string;
    word_type?: string;
    definition?: string;
    example?: string;
  };
  image_url?: string;
  audio: { id: number; url: string }[];
  scheduled_at?: string;
  published_at?: string;
  error_message?: string;
}

export interface DriveStatus {
  connected: boolean;
  email?: string;
}

export interface Collection {
  id: number | string;
  name: string;
}

export interface Source {
  id: number | string;
  name: string;
  collection_id: number | string;
}

export interface Template {
  id: number;
  name: string;
  image_url: string;
  is_active: boolean;
}

export interface Batch {
  id: number;
  name: string;
  status: string;
  total_items: number;
  generated_items: number;
}

export interface GenerationJob {
  id: string;
  status: "queued" | "generating" | "cancelling" | "ready" | "failed" | "cancelled";
  batch_id?: number;
  batch_name?: string;
  source_file_id: number;
  template_id: number;
  total_items: number;
  generated_items: number;
  percent: number;
  error?: string;
  cancel_requested: boolean;
  created_at: string;
  updated_at: string;
}

export interface VocabRow {
  source_row_key: string;
  word: string;
  word_type?: string;
  phonetic?: string;
  definition: string;
  example?: string;
  level?: string;
}

export interface GenerateBatchPayload {
  source_file_id: number | string;
  template_id: number;
  name: string;
  caption_text: string;
}
