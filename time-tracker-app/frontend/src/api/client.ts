import { ApiError } from "./errors";
import type { ApiErrorCode, ErrorResponse } from "./types";

/**
 * Base URL for the FastAPI backend. In dev, Vite proxies `/api/*` to the backend origin (see
 * `vite.config.ts`), so the client always calls relative `/api/...` paths — no CORS, no
 * hardcoded origin baked into the bundle. Override via `VITE_API_BASE_URL` if needed (e.g. a
 * built/served bundle pointed at a non-default backend origin).
 */
export const API_PREFIX = "/api";

type QueryValue = string | number | boolean | undefined | null;
type QueryParams = Record<string, QueryValue>;

function buildQuery(params?: object): string {
  if (!params) return "";
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params as QueryParams)) {
    if (value === undefined || value === null) continue;
    search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

async function parseErrorBody(
  response: Response,
): Promise<{ code: ApiErrorCode; message: string; details: Record<string, unknown> | null }> {
  try {
    const body = (await response.json()) as ErrorResponse;
    if (body?.error?.code) {
      return {
        code: body.error.code as ApiErrorCode,
        message: body.error.message,
        details: body.error.details ?? null,
      };
    }
  } catch {
    // fall through to generic message below
  }
  return {
    code: "unknown_error",
    message: `Request failed with status ${response.status}.`,
    details: null,
  };
}

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  query?: object;
  signal?: AbortSignal;
}

/**
 * Fetch wrapper that centralizes error-envelope handling: any non-2xx response is normalized into
 * an {@link ApiError} carrying the backend's `code`/`message`/`details` (see
 * `app/API_CONTRACT.md`'s error envelope). Network failures (fetch throwing) surface as an
 * `ApiError` with `code: "network_error"` so all call sites can rely on a single catch shape.
 */
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, query, signal } = options;
  const url = `${API_PREFIX}${path}${buildQuery(query)}`;

  const init: RequestInit = { method };
  if (signal) init.signal = signal;
  if (body !== undefined) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(body);
  }

  let response: Response;
  try {
    response = await fetch(url, init);
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    throw new ApiError(0, "network_error", "Could not reach the server. Is the backend running?");
  }

  if (!response.ok) {
    const { code, message, details } = await parseErrorBody(response);
    throw new ApiError(response.status, code, message, details);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
