/**
 * Typed mirror of `app/schemas.py`. Keep field names/types in lockstep with the backend contract
 * (see `app/API_CONTRACT.md`). Timestamps are ISO-8601 UTC strings on the wire; components format
 * them for display via `utils/duration.ts` / `Intl` at render time.
 */

export type EntryMode = "timer" | "manual";

export type CategoryColorKey =
  | "red"
  | "orange"
  | "amber"
  | "lime"
  | "green"
  | "teal"
  | "cyan"
  | "blue"
  | "indigo"
  | "violet"
  | "pink"
  | "slate";

export interface CategoryRead {
  id: number;
  name: string;
  color: string | null;
  is_active: boolean;
  sort_order: number;
}

export interface CategoryCreate {
  name: string;
  color?: string | null;
  sort_order?: number;
}

export interface CategoryUpdate {
  name?: string;
  color?: string | null;
  sort_order?: number;
  is_active?: boolean;
}

export interface CategoryListResponse {
  items: CategoryRead[];
  total: number;
}

export interface TagRead {
  id: number;
  name: string;
  is_active: boolean;
}

export interface TagCreate {
  name: string;
}

export interface TagUpdate {
  name?: string;
  is_active?: boolean;
}

export interface TagListResponse {
  items: TagRead[];
  total: number;
}

export interface EntryRead {
  id: number;
  title: string;
  notes: string | null;
  category: CategoryRead | null;
  tags: TagRead[];
  start_ts: string;
  end_ts: string | null;
  duration_minutes: number | null;
  entry_mode: EntryMode;
  created_at: string;
  updated_at: string;
}

export interface EntryCreateManual {
  title: string;
  notes?: string | null;
  category_id?: number | null;
  tag_ids?: number[];
  start_ts: string;
  end_ts: string;
}

export interface EntryUpdate {
  title?: string;
  notes?: string | null;
  category_id?: number | null;
  tag_ids?: number[];
  start_ts?: string;
  end_ts?: string;
}

export interface EntryListResponse {
  items: EntryRead[];
  total: number;
  limit: number;
  offset: number;
}

export interface EntryListQuery {
  start_date?: string;
  end_date?: string;
  category_id?: number;
  tag_id?: number;
  entry_mode?: EntryMode;
  limit?: number;
  offset?: number;
}

export interface TimerStartRequest {
  title?: string | null;
  notes?: string | null;
  category_id?: number | null;
  tag_ids?: number[];
}

export interface TimerStopRequest {
  title?: string | null;
  notes?: string | null;
  category_id?: number | null;
  tag_ids?: number[];
}

export interface TimerCurrentResponse {
  running: boolean;
  entry: EntryRead | null;
}

export interface TodayResponse {
  entries: EntryRead[];
  running_timer: EntryRead | null;
  recent_categories: CategoryRead[];
  recent_tags: TagRead[];
}

export type ReportPeriod = "week" | "month" | "quarter";

export interface ReportCategoryBreakdown {
  category: CategoryRead | null;
  total_minutes: number;
  entry_count: number;
}

export interface ReportTagBreakdown {
  tag: TagRead;
  total_minutes: number;
  entry_count: number;
}

export interface ReportDayBreakdown {
  date: string;
  total_minutes: number;
  entry_count: number;
}

export interface ReportSummaryResponse {
  period: ReportPeriod;
  start_date: string;
  end_date: string;
  timezone: string;
  total_minutes: number;
  entry_count: number;
  by_category: ReportCategoryBreakdown[];
  by_tag: ReportTagBreakdown[];
  by_day: ReportDayBreakdown[];
}

export interface ReportNarrativeResponse {
  period: ReportPeriod;
  start_date: string;
  end_date: string;
  timezone: string;
  narrative: string;
  highlights: string[];
}

/** Stable, machine-readable error codes the frontend can branch on (see API_CONTRACT.md). */
export type ApiErrorCode =
  | "bad_request"
  | "resource_not_found"
  | "conflict"
  | "timer_already_running"
  | "no_running_timer"
  | "validation_error"
  | "internal_error"
  | "network_error"
  | "unknown_error";

export interface ErrorDetail {
  code: string;
  message: string;
  details?: Record<string, unknown> | null;
}

export interface ErrorResponse {
  error: ErrorDetail;
}
