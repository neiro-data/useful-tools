import { apiRequest } from "./client";
import type { TagCreate, TagListResponse, TagRead, TagUpdate } from "./types";

export function listTags(includeInactive = false): Promise<TagListResponse> {
  return apiRequest<TagListResponse>("/tags", { query: { include_inactive: includeInactive } });
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
