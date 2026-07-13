import { apiRequest } from "./client";
import type { CategoryCreate, CategoryListResponse, CategoryRead, CategoryUpdate } from "./types";

export function listCategories(includeInactive = false): Promise<CategoryListResponse> {
  return apiRequest<CategoryListResponse>("/categories", {
    query: { include_inactive: includeInactive },
  });
}

export function createCategory(body: CategoryCreate): Promise<CategoryRead> {
  return apiRequest<CategoryRead>("/categories", { method: "POST", body });
}

export function updateCategory(id: number, body: CategoryUpdate): Promise<CategoryRead> {
  return apiRequest<CategoryRead>(`/categories/${id}`, { method: "PATCH", body });
}

export function deactivateCategory(id: number): Promise<CategoryRead> {
  return apiRequest<CategoryRead>(`/categories/${id}/deactivate`, { method: "POST" });
}
