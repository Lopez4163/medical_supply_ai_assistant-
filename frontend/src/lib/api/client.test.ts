import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiClientError, bootstrapGuestSession } from "./client";

describe("bootstrapGuestSession", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("uses the cookie-authenticated session bootstrap endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          conversation_id: "31dced59-7efc-4b51-8c8a-2e8a1c2f34f9",
          expires_at: "2026-11-18T12:00:00Z",
          restored: false,
          welcome_message: "Welcome.",
        }),
        { status: 201 },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(bootstrapGuestSession()).resolves.toMatchObject({ restored: false });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/sessions",
      expect.objectContaining({ credentials: "include", method: "POST" }),
    );
  });

  it("returns a typed API error for an expired or unavailable session response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 401 })));

    await expect(bootstrapGuestSession()).rejects.toMatchObject({
      message: "The API request could not be completed.",
      name: "ApiClientError",
      status: 401,
    } satisfies Partial<ApiClientError>);
  });
});
