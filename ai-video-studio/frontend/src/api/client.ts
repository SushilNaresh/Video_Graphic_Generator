import type {
  ActivityEntry,
  ProjectState,
  ProjectSummary,
  RenderProgress,
  SkillNote,
  StockMediaItem,
  StockSearchResponse,
  TaskStatus,
  UploadResponse
} from '../types';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {})
    }
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  listProjects: () => json<ProjectSummary[]>('/api/projects'),
  createProject: (name = 'Untitled Video Studio Project') =>
    json<ProjectState>('/api/projects', { method: 'POST', body: JSON.stringify({ name }) }),
  getProject: (id: string) => json<ProjectState>(`/api/projects/${id}`),
  deleteProject: (id: string) =>
    json<{ id: string; deleted: boolean }>(`/api/projects/${id}`, { method: 'DELETE' }),
  autosaveProject: (project: ProjectState) =>
    json<ProjectState>(`/api/projects/${project.id}/autosave`, { method: 'POST', body: JSON.stringify(project) }),
  transcribe: (projectId: string) =>
    json<ProjectState>(`/api/projects/${projectId}/transcribe`, { method: 'POST', body: JSON.stringify({}) }),
  autoProduce: (projectId: string) =>
    json<ProjectState>(`/api/projects/${projectId}/auto-produce`, { method: 'POST', body: JSON.stringify({}) }),
  analyzeTwelveLabs: (projectId: string) =>
    json<TaskStatus>(`/api/media/${projectId}/twelve-labs/analyze`, { method: 'POST', body: JSON.stringify({}) }),
  getTwelveLabsCredits: () =>
    json<{ configured: boolean; consumed_minutes: number; remaining_minutes: number; expires_at?: string | null }>(
      '/api/media/twelve-labs/credits'
    ),
  setTwelveLabsKey: (apiKey: string) =>
    json<{ configured: boolean; masked: string }>('/api/media/twelve-labs/set-key', {
      method: 'POST',
      body: JSON.stringify({ api_key: apiKey })
    }),
  searchStock: (query: string, mediaType = 'image') =>
    json<StockSearchResponse>(`/api/media/stock/search?q=${encodeURIComponent(query)}&media_type=${mediaType}`),
  downloadStock: (projectId: string, item: StockMediaItem) =>
    json<{ media_url: string; filename: string }>('/api/media/stock/download', {
      method: 'POST',
      body: JSON.stringify({ project_id: projectId, item })
    }),
  getActivityLog: (projectId: string) => json<ActivityEntry[]>(`/api/projects/${projectId}/activity-log`),
  getSkillNotes: (projectId: string) => json<SkillNote[]>(`/api/projects/${projectId}/skill-notes`),
  addSkillNote: (projectId: string, payload: Omit<SkillNote, 'ts' | 'author'>) =>
    json<SkillNote>(`/api/projects/${projectId}/skill-notes`, { method: 'POST', body: JSON.stringify(payload) }),
  addGraphic: (projectId: string, payload: object) =>
    json<ProjectState>(`/api/projects/${projectId}/graphics`, { method: 'POST', body: JSON.stringify(payload) }),
  deleteGraphic: (projectId: string, graphicId: string) =>
    json<ProjectState>(`/api/projects/${projectId}/graphics/${graphicId}`, { method: 'DELETE' }),
  renderBurnin: (projectId: string) =>
    json<{ render_id: string; status: string; output_url?: string }>(`/api/media/${projectId}/render-burnin`, {
      method: 'POST',
      body: JSON.stringify({})
    }),
  getRenderProgress: (projectId: string) => json<RenderProgress>(`/api/media/${projectId}/burnin-progress`),
  sourceVideoUrl: (projectId: string) => `${API_BASE}/api/media/${projectId}/source-video`,
  downloadMp4Url: (projectId: string) => `${API_BASE}/api/media/${projectId}/download-mp4`,
  assetUrl: (path: string) => (path.startsWith('http') ? path : `${API_BASE}${path}`),
  uploadVideo: (projectId: string, file: File, onProgress?: (progress: number) => void) =>
    new Promise<UploadResponse>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', `${API_BASE}/api/media/${projectId}/upload`);
      xhr.setRequestHeader('X-Filename', encodeURIComponent(file.name));
      xhr.setRequestHeader('Content-Type', file.type || 'application/octet-stream');
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable && onProgress) {
          onProgress(Math.round((event.loaded / event.total) * 100));
        }
      };
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            resolve(JSON.parse(xhr.responseText) as UploadResponse);
          } catch (error) {
            reject(error);
          }
        } else {
          reject(new Error(xhr.responseText || `Upload failed: ${xhr.status}`));
        }
      };
      xhr.onerror = () => reject(new Error('Network upload failed'));
      xhr.onabort = () => reject(new Error('Upload cancelled'));
      xhr.send(file);
    })
};
