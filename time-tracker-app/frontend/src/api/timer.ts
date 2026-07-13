import { apiRequest } from "./client";
import type { EntryRead, TimerCurrentResponse, TimerStartRequest, TimerStopRequest } from "./types";

/** Throws `ApiError` with `code: "timer_already_running"` (see `errors.ts`) if a timer is live. */
export function startTimer(body: TimerStartRequest = {}): Promise<EntryRead> {
  return apiRequest<EntryRead>("/timer/start", { method: "POST", body });
}

export function getCurrentTimer(): Promise<TimerCurrentResponse> {
  return apiRequest<TimerCurrentResponse>("/timer/current");
}

/** Throws `ApiError` with `code: "no_running_timer"` if nothing is running. */
export function stopTimer(body: TimerStopRequest = {}): Promise<EntryRead> {
  return apiRequest<EntryRead>("/timer/stop", { method: "POST", body });
}
