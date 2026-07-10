// ── Extracted usage fields ──

export interface ExtractedUsage {
  auth_method: string | null;
  email: string | null;
  organization: string | null;
  plan_tier: string | null;
  weekly_usage_pct: number | null;
  weekly_fable_usage_pct: number | null;
  weekly_reset_at: string | null;
  weekly_fable_reset_at: string | null;
}

// ── Upload preview (after initial extract, before confirm) ──

export interface UploadPreviewResponse {
  image_path: string;
  original_filename: string;
  extracted: ExtractedUsage;
  raw_text: string | null;
  weekly_reset_locked: boolean;
  fable_reset_locked: boolean;
}

// ── Confirm request body ──

export interface UploadConfirmRequest {
  email: string;
  image_path: string;
  original_filename: string;
  auth_method: string | null;
  organization: string | null;
  plan_tier: string | null;
  weekly_usage_pct: number | null;
  weekly_fable_usage_pct: number | null;
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

export interface DailyUsage {
  weekly: number | null;
  fable: number | null;
}

export interface UserDayRow {
  email: string;
  organization: string | null;
  plan_tier: string | null;
  daily: Record<string, DailyUsage>;
  latest_weekly: number | null;
  latest_fable: number | null;
  last_upload_at: string | null;
  latest_image_path: string | null;
  weekly_projected_pct: number | null;
  weekly_at_risk: boolean;
  fable_projected_pct: number | null;
  fable_at_risk: boolean;
}

export interface LeaderboardEntry {
  email: string;
  latest_weekly: number | null;
  latest_fable: number | null;
  last_upload_at: string | null;
  latest_image_path: string | null;
  weekly_projected_pct: number | null;
  weekly_at_risk: boolean;
  fable_projected_pct: number | null;
  fable_at_risk: boolean;
}

export interface TrendPoint {
  uploaded_at: string;
  weekly_usage_pct: number | null;
  weekly_fable_usage_pct: number | null;
}

export interface UserTrend {
  email: string;
  points: TrendPoint[];
}

export interface DashboardSummary {
  dates: string[];
  users: UserDayRow[];
  leaderboard: LeaderboardEntry[];
  uploads_today: number;
  uploads_this_week: number;
  per_user_trends: UserTrend[];
}

export interface UserComparison {
  email: string;
  weekly_from: number | null;
  weekly_to: number | null;
  weekly_delta: number | null;
  weekly_reset_occurred: boolean;
  fable_from: number | null;
  fable_to: number | null;
  fable_delta: number | null;
  fable_reset_occurred: boolean;
}

export interface DashboardCompareResponse {
  from_date: string;
  to_date: string;
  users: UserComparison[];
}

export interface UserHistoryResponse {
  email: string;
  total_uploads: number;
  uploads: UsageUploadResponse[];
  trend: TrendPoint[];
}

// ── Reset date correction ──

export interface ResetDateUpdateRequest {
  metric: 'weekly' | 'fable';
  reset_at: string;
}

export interface ResetDateUpdateResponse {
  email: string;
  metric: string;
  reset_at: string;
  rows_updated: number;
}

// ── Health check ──

export interface HealthResponse {
  status: string;
}
