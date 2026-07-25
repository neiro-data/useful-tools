import { apiRequest } from "./client";
import type { SettingsRead, SettingsUpdate, TimezoneListResponse } from "./types";

export function getSettings(): Promise<SettingsRead> {
  return apiRequest<SettingsRead>("/settings");
}

export function updateSettings(payload: SettingsUpdate): Promise<SettingsRead> {
  return apiRequest<SettingsRead>("/settings", { method: "PATCH", body: payload });
}

export function listTimezones(): Promise<TimezoneListResponse> {
  return apiRequest<TimezoneListResponse>("/settings/timezones");
}
