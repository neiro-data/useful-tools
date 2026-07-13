import { apiRequest } from "./client";
import type { EntryCreateManual, EntryListQuery, EntryListResponse, EntryRead, EntryUpdate } from "./types";

export function listEntries(query: EntryListQuery = {}): Promise<EntryListResponse> {
  return apiRequest<EntryListResponse>("/entries", { query });
}

export function createEntry(body: EntryCreateManual): Promise<EntryRead> {
  return apiRequest<EntryRead>("/entries", { method: "POST", body });
}

export function getEntry(id: number): Promise<EntryRead> {
  return apiRequest<EntryRead>(`/entries/${id}`);
}

export function updateEntry(id: number, body: EntryUpdate): Promise<EntryRead> {
  return apiRequest<EntryRead>(`/entries/${id}`, { method: "PATCH", body });
}

export function deleteEntry(id: number): Promise<void> {
  return apiRequest<void>(`/entries/${id}`, { method: "DELETE" });
}
