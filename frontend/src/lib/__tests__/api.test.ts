import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiRequest } from "@/lib/api";

function mockFetch(response: Partial<Response> & { jsonBody?: unknown }) {
  const { jsonBody, ...rest } = response;
  return vi.fn().mockResolvedValue({
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => jsonBody,
    ...rest,
  } as Response);
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("apiRequest", () => {
  it("returns parsed JSON on success", async () => {
    vi.stubGlobal("fetch", mockFetch({ ok: true, status: 200, jsonBody: { id: "1" } }));
    const result = await apiRequest<{ id: string }>("/api/x");
    expect(result.id).toBe("1");
  });

  it("returns undefined for 204 responses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ status: 204, ok: true } as Response));
    const result = await apiRequest("/api/x", { method: "DELETE" });
    expect(result).toBeUndefined();
  });

  it("throws ApiError with code and status from the error body", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch({
        ok: false,
        status: 409,
        jsonBody: { error: { code: "conflict", message: "Already exists" } },
      })
    );
    await expect(apiRequest("/api/x", { method: "POST", body: {} })).rejects.toMatchObject({
      status: 409,
      code: "conflict",
      message: "Already exists",
    });
  });

  it("maps a transport failure to a network error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("failed")));
    await expect(apiRequest("/api/x")).rejects.toBeInstanceOf(ApiError);
    await expect(apiRequest("/api/x")).rejects.toMatchObject({ code: "network_error" });
  });
});
