import { apiRequest } from "./client";
import type { TagCreate, TagListResponse, TagRead, TagUpdate } from "./types";

export interface ListTagsOptions {
  includeInactive?: boolean;
  /** Per `app/API_CONTRACT.md`'s `GET /tags`: defaults to 50 server-side (max 200) if omitted —
   * callers populating a dropdown/autocomplete of "every known tag" (e.g. `TagEditor`'s full-list
   * toggle) should pass a higher value so the default doesn't silently truncate the list. */
  limit?: number;
}

export function listTags(options: ListTagsOptions = {}): Promise<TagListResponse> {
  const { includeInactive = false, limit } = options;
  return apiRequest<TagListResponse>("/tags", {
    query: { include_inactive: includeInactive, ...(limit !== undefined && { limit }) },
  });
}

export function createTag(body: TagCreate): Promise<TagRead> {
  return apiRequest<TagRead>("/tags", { method: "POST", body });
}

export function updateTag(id: number, body: TagUpdate): Promise<TagRead> {
  return apiRequest<TagRead>(`/tags/${id}`, { method: "PATCH", body });
}

export function deactivateTag(id: number): Promise<TagRead> {
  return apiRequest<TagRead>(`/tags/${id}/deactivate`, { method: "POST" });
}
