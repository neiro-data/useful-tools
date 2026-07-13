import { apiRequest } from "./client";
import type { TodayResponse } from "./types";

export function getToday(): Promise<TodayResponse> {
  return apiRequest<TodayResponse>("/today");
}
