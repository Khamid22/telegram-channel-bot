const API_BASE = import.meta.env.VITE_API_BASE || '';

export async function request(path, options = {}) {
  const headers = options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' };
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
    ...options,
    headers: {
      ...headers,
      ...(options.headers || {})
    }
  });

  const text = await response.text();
  const data = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(data.error || 'Request failed');
  }
  return data;
}

export const api = {
  me: () => request('/api/me'),
  login: (payload) => request('/api/auth/login', { method: 'POST', body: JSON.stringify(payload) }),
  logout: () => request('/api/auth/logout', { method: 'POST' }),
  analytics: () => request('/api/analytics'),
  schedules: () => request('/api/schedules'),
  createSchedule: (payload) => request('/api/schedules', { method: 'POST', body: JSON.stringify(payload) }),
  updateSchedule: (id, payload) => request(`/api/schedules/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  pauseScheduler: () => request('/api/scheduler/pause', { method: 'POST' }),
  resumeScheduler: () => request('/api/scheduler/resume', { method: 'POST' }),
  queue: () => request('/api/queue'),
  enqueueNext: () => request('/api/queue/enqueue-next', { method: 'POST' }),
  publishManual: () => request('/api/publish/manual', { method: 'POST' }),
  publishPost: (id) => request(`/api/publish/${id}`, { method: 'POST' }),
  calendar: () => request('/api/calendar'),
  failedJobs: () => request('/api/failed-jobs'),
  syncSheets: () => request('/api/sheets/sync', { method: 'POST' }),
  words: (params = {}) => request(`/api/words?${new URLSearchParams(params)}`),
  templates: () => request('/api/templates'),
  activateTemplate: (id) => request(`/api/templates/${id}/activate`, { method: 'POST' }),
  previewTemplate: (id, payload) => request(`/api/templates/${id}/preview`, { method: 'POST', body: JSON.stringify(payload) }),
  uploadTemplate: (payload) => request('/api/templates', { method: 'POST', body: payload }),
  uploadFont: (payload) => request('/api/fonts', { method: 'POST', body: payload }),
  deleteSchedule: (id) => request(`/api/schedules/${id}`, { method: 'DELETE' })
};
