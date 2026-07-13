import { afterEach, describe, expect, it, vi } from "vitest";
import { apiRequest } from "./client";
import { ApiError } from "./errors";

/**
 * Error-envelope parsing tests for the API client. `fetch` is mocked (there's no real backend to
 * hit in a unit test) but the envelope-parsing logic in `apiRequest`/`parseErrorBody` itself runs
 * for real — this is what backs every call site's error handling (see `app/API_CONTRACT.md`'s
 * error envelope).
 */
function mockJsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("apiRequest error-envelope parsing", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("maps a 409 timer_already_running response to a typed ApiError with the stable code and runningEntryId", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockJsonResponse(409, {
          error: {
            code: "timer_already_running",
            message: "A timer is already running (entry_id=42). Stop it before starting another.",
            details: { running_entry_id: 42 },
          },
        }),
      ),
    );

    await expect(apiRequest("/timer/start", { method: "POST", body: {} })).rejects.toSatisfy(
      (error: unknown) => {
        expect(error).toBeInstanceOf(ApiError);
        const apiError = error as ApiError;
        expect(apiError.status).toBe(409);
        expect(apiError.code).toBe("timer_already_running");
        expect(apiError.isTimerAlreadyRunning).toBe(true);
        expect(apiError.runningEntryId).toBe(42);
        return true;
      },
    );
  });

  it("maps a 404 resource_not_found response into the typed error shape", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockJsonResponse(404, {
          error: {
            code: "resource_not_found",
            message: "Category 999 does not exist.",
            details: { category_id: 999 },
          },
        }),
      ),
    );

    await expect(apiRequest("/categories/999")).rejects.toSatisfy((error: unknown) => {
      expect(error).toBeInstanceOf(ApiError);
      const apiError = error as ApiError;
      expect(apiError.status).toBe(404);
      expect(apiError.code).toBe("resource_not_found");
      expect(apiError.isTimerAlreadyRunning).toBe(false);
      expect(apiError.details).toEqual({ category_id: 999 });
      return true;
    });
  });

  it("maps a 422 validation_error response into the typed error shape, including field details", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockJsonResponse(422, {
          error: {
            code: "validation_error",
            message: "Validation failed.",
            details: { fields: [{ loc: ["body", "name"], msg: "field required" }] },
          },
        }),
      ),
    );

    await expect(apiRequest("/categories", { method: "POST", body: { name: "" } })).rejects.toSatisfy(
      (error: unknown) => {
        expect(error).toBeInstanceOf(ApiError);
        const apiError = error as ApiError;
        expect(apiError.status).toBe(422);
        expect(apiError.code).toBe("validation_error");
        expect(apiError.details).toEqual({
          fields: [{ loc: ["body", "name"], msg: "field required" }],
        });
        return true;
      },
    );
  });

  it("falls back to a generic unknown_error shape when the error body isn't the expected envelope", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("Internal Server Error", { status: 500 }),
      ),
    );

    await expect(apiRequest("/today")).rejects.toSatisfy((error: unknown) => {
      expect(error).toBeInstanceOf(ApiError);
      const apiError = error as ApiError;
      expect(apiError.status).toBe(500);
      expect(apiError.code).toBe("unknown_error");
      return true;
    });
  });

  it("resolves normally (no ApiError) for a 2xx JSON response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockJsonResponse(200, { running: false, entry: null })),
    );

    const result = await apiRequest("/timer/current");

    expect(result).toEqual({ running: false, entry: null });
  });
});
