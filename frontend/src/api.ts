import type {
  UploadPreviewResponse,
  UploadConfirmRequest,
  UsageUploadResponse,
  PaginatedUploads,
  DashboardSummary,
  UserHistoryResponse,
  HealthResponse,
  Manager,
  Team,
  TeamMember,
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

// ── Teams (org hierarchy) ──

export function getManagers() {
  return request<Manager[]>('/teams/managers');
}

export function createManager(name: string) {
  return request<Manager>('/teams/managers', {
    method: 'POST',
    body: JSON.stringify({ name }),
  });
}

export function updateManager(id: number, name: string) {
  return request<Manager>(`/teams/managers/${id}`, {
    method: 'PUT',
    body: JSON.stringify({ name }),
  });
}

export function deleteManager(id: number) {
  return request<void>(`/teams/managers/${id}`, { method: 'DELETE' });
}

export function getTeams(managerId?: number) {
  const qs = managerId != null ? `?manager_id=${managerId}` : '';
  return request<Team[]>(`/teams/teams${qs}`);
}

export function createTeam(name: string, managerId: number) {
  return request<Team>('/teams/teams', {
    method: 'POST',
    body: JSON.stringify({ name, manager_id: managerId }),
  });
}

export function updateTeam(id: number, data: { name?: string; manager_id?: number }) {
  return request<Team>(`/teams/teams/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export function deleteTeam(id: number) {
  return request<void>(`/teams/teams/${id}`, { method: 'DELETE' });
}

export function getTeamMembers(teamId?: number) {
  const qs = teamId != null ? `?team_id=${teamId}` : '';
  return request<TeamMember[]>(`/teams/team-members${qs}`);
}

export function createTeamMember(name: string, teamId: number) {
  return request<TeamMember>('/teams/team-members', {
    method: 'POST',
    body: JSON.stringify({ name, team_id: teamId }),
  });
}

export function updateTeamMember(id: number, data: { name?: string; team_id?: number }) {
  return request<TeamMember>(`/teams/team-members/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export function deleteTeamMember(id: number) {
  return request<void>(`/teams/team-members/${id}`, { method: 'DELETE' });
}

export function resetTeamUsage(teamId: number) {
  return request<{ message: string }>(`/teams/teams/${teamId}/reset-usage`, { method: 'POST' });
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
  manager_id?: number;
  team_id?: number;
  from?: string;
  to?: string;
  skip?: number;
  limit?: number;
}) {
  const sp = new URLSearchParams();
  if (params?.user) sp.set('user', params.user);
  if (params?.manager_id != null) sp.set('manager_id', String(params.manager_id));
  if (params?.team_id != null) sp.set('team_id', String(params.team_id));
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

export function getDashboardSummary(params?: {
  days?: number;
  manager_id?: number;
  team_id?: number;
}) {
  const sp = new URLSearchParams();
  if (params?.days != null) sp.set('days', String(params.days));
  if (params?.manager_id != null) sp.set('manager_id', String(params.manager_id));
  if (params?.team_id != null) sp.set('team_id', String(params.team_id));
  const qs = sp.toString();
  return request<DashboardSummary>(`/dashboard/summary${qs ? '?' + qs : ''}`);
}

export function getUserHistory(name: string, limit?: number) {
  const qs = limit != null ? `?limit=${limit}` : '';
  return request<UserHistoryResponse>(
    `/dashboard/users/${encodeURIComponent(name)}/history${qs}`
  );
}
