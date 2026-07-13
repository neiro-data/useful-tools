import type { ApiErrorCode } from "./types";

/**
 * Typed error thrown by the API client for every non-2xx response (and for network failures).
 * `code` matches the backend's error envelope (`app/API_CONTRACT.md`) so callers can branch on
 * stable strings like `"timer_already_running"` instead of parsing status codes/messages.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly code: ApiErrorCode;
  readonly details: Record<string, unknown> | null;

  constructor(
    status: number,
    code: ApiErrorCode,
    message: string,
    details: Record<string, unknown> | null = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }

  /** True when this is the "a timer is already running" 409 conflict. */
  get isTimerAlreadyRunning(): boolean {
    return this.code === "timer_already_running";
  }

  /** The id of the entry already running, when {@link isTimerAlreadyRunning} is true. */
  get runningEntryId(): number | null {
    const value = this.details?.["running_entry_id"];
    return typeof value === "number" ? value : null;
  }
}
