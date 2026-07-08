// ── Org hierarchy ──

export interface Manager {
  id: number;
  name: string;
}

export interface Team {
  id: number;
  name: string;
  manager_id: number;
}

export interface TeamMember {
  id: number;
  name: string;
  team_id: number;
}

// ── Extracted usage fields ──

export interface ExtractedUsage {
  auth_method: string | null;
  email: string | null;
  organization: string | null;
  plan_tier: string | null;
  session_usage_pct: number | null;
  weekly_usage_pct: number | null;
  weekly_fable_usage_pct: number | null;
  session_reset_at: string | null;
  weekly_reset_at: string | null;
  weekly_fable_reset_at: string | null;
}

// ── Upload preview (after initial extract, before confirm) ──

export interface UploadPreviewResponse {
  image_path: string;
  original_filename: string;
  extracted: ExtractedUsage;
  raw_text: string | null;
}

// ── Confirm request body ──

export interface UploadConfirmRequest {
  uploader_name: string;
  image_path: string;
  original_filename: string;
  manager_id: number | null;
  team_id: number | null;
  auth_method: string | null;
  email: string | null;
  organization: string | null;
  plan_tier: string | null;
  session_usage_pct: number | null;
  weekly_usage_pct: number | null;
  weekly_fable_usage_pct: number | null;
  session_reset_at: string | null;
  weekly_reset_at: string | null;
  weekly_fable_reset_at: string | null;
  extraction_method: string;
  raw_extracted_text: string | null;
  was_manually_edited: boolean;
}

// ── Saved upload record ──

export interface UsageUploadResponse extends UploadConfirmRequest {
  id: number;
  uploaded_at: string;
}

// ── Paginated list ──

export interface PaginatedUploads {
  total: number;
  skip: number;
  limit: number;
  items: UsageUploadResponse[];
}

// ── Dashboard ──

export interface LeaderboardEntry {
  uploader_name: string;
  latest_session_pct: number | null;
  latest_weekly_pct: number | null;
  last_upload_at: string | null;
  latest_image_path: string | null;
}

export interface TrendPoint {
  uploaded_at: string;
  session_usage_pct: number | null;
  weekly_usage_pct: number | null;
}

export interface PerUserTrend {
  uploader_name: string;
  points: TrendPoint[];
}

export interface ManagerSummary {
  manager_id: number;
  manager_name: string;
  team_count: number;
  avg_weekly_pct: number | null;
  avg_session_pct: number | null;
}

export interface TeamSummary {
  team_id: number;
  team_name: string;
  manager_name: string;
  member_count: number;
  avg_weekly_pct: number | null;
  avg_session_pct: number | null;
  max_session_pct: number | null;
  max_weekly_pct: number | null;
}

export interface DashboardSummary {
  team_avg_session_usage: number | null;
  team_avg_weekly_usage: number | null;
  leaderboard: LeaderboardEntry[];
  uploads_today: number;
  uploads_this_week: number;
  per_user_trends: PerUserTrend[];
  by_manager: ManagerSummary[];
  by_team: TeamSummary[];
}

export interface UserHistoryResponse {
  uploader_name: string;
  total_uploads: number;
  uploads: UsageUploadResponse[];
  trend: TrendPoint[];
}

// ── Health check ──

export interface HealthResponse {
  status: string;
}
