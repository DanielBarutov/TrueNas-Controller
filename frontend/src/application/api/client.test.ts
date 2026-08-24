import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, ControllerApi } from "./client";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ControllerApi", () => {
  it("sends Basic Auth and parses a successful health response", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: "ok" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(new ControllerApi({ username: "admin", password: "secret" }).health())
      .resolves.toEqual({ status: "ok" });

    expect(fetchMock).toHaveBeenCalledWith("/health", expect.objectContaining({
      headers: expect.objectContaining({
        Authorization: `Basic ${btoa("admin:secret")}`,
      }),
    }));
  });

  it("maps a non-JSON 401 response to a safe ApiError", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => {
        throw new Error("not json");
      },
    }));

    await expect(new ControllerApi({ username: "admin", password: "bad" }).health())
      .rejects.toEqual(new ApiError("Request failed with status 401", 401));
  });

  it("supports an authenticated station deletion with an empty 204 response", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 204 });
    vi.stubGlobal("fetch", fetchMock);

    await expect(new ControllerApi({ username: "admin", password: "secret" }).deleteStation("station-1"))
      .resolves.toBeUndefined();

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/stations/station-1", expect.objectContaining({
      method: "DELETE",
    }));
  });
});
