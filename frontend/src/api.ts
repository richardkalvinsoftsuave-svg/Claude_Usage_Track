import type {
  UploadPreviewResponse,
  UploadConfirmRequest,
  UsageUploadResponse,
  PaginatedUploads,
  DashboardSummary,
  UserHistoryResponse,
  HealthResponse,
} from './types';

const BASE = '/api';

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || `${res.status} ${res.statusText}`);
  }
  return res.json();
}

// ── Health ──

export function healthCheck() {
  return request<HealthResponse>('/health');
}

// ── Uploads ──

export async function uploadImage(file: File): Promise<UploadPreviewResponse> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${BASE}/uploads`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || `${res.status} ${res.statusText}`);
  }
  return res.json();
}

export function reextract(imagePath: string) {
  return request<UploadPreviewResponse>(
    `/uploads/reextract?image_path=${encodeURIComponent(imagePath)}`,
    { method: 'POST' }
  );
}

export function confirmUpload(data: UploadConfirmRequest) {
  return request<UsageUploadResponse>('/uploads/confirm', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function getUploads(params?: {
  user?: string;
  from?: string;
  to?: string;
  skip?: number;
  limit?: number;
}) {
  const sp = new URLSearchParams();
  if (params?.user) sp.set('user', params.user);
  if (params?.from) sp.set('from', params.from);
  if (params?.to) sp.set('to', params.to);
  if (params?.skip != null) sp.set('skip', String(params.skip));
  if (params?.limit != null) sp.set('limit', String(params.limit));
  const qs = sp.toString();
  return request<PaginatedUploads>(`/uploads${qs ? '?' + qs : ''}`);
}

export function getUpload(id: number) {
  return request<UsageUploadResponse>(`/uploads/${id}`);
}

// ── Dashboard ──

export function getDashboardSummary(days?: number) {
  const qs = days != null ? `?days=${days}` : '';
  return request<DashboardSummary>(`/dashboard/summary${qs}`);
}

export function getUserHistory(name: string, limit?: number) {
  const qs = limit != null ? `?limit=${limit}` : '';
  return request<UserHistoryResponse>(
    `/dashboard/users/${encodeURIComponent(name)}/history${qs}`
  );
}
