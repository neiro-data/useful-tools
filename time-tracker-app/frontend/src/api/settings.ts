import { apiRequest } from "./client";
import type { SettingsRead, SettingsUpdate } from "./types";

export function getSettings(): Promise<SettingsRead> {
  return apiRequest<SettingsRead>("/settings");
}

export function updateSettings(payload: SettingsUpdate): Promise<SettingsRead> {
  return apiRequest<SettingsRead>("/settings", { method: "PATCH", body: payload });
}
