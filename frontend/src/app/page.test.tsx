import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Providers } from "./providers";
import HomePage from "./page";

function sessionResponse({ restored }: { restored: boolean }): Response {
  return new Response(
    JSON.stringify({
      conversation_id: "31dced59-7efc-4b51-8c8a-2e8a1c2f34f9",
      expires_at: "2026-11-18T12:00:00Z",
      restored,
      welcome_message: "Welcome to the synthetic demonstration.",
    }),
    { status: restored ? 200 : 201 },
  );
}

function conversationResponse(): Response {
  return new Response(
    JSON.stringify({
      conversation_id: "31dced59-7efc-4b51-8c8a-2e8a1c2f34f9",
      messages: [
        {
          id: "d186f5c2-6cd5-4a36-8f99-9d4d2a791527",
          role: "assistant",
          kind: "welcome",
          ordinal: 0,
          text: "Welcome to the synthetic demonstration.",
          elements: [],
          created_at: "2026-11-18T12:00:00Z",
          freshness: "historical_snapshot",
        },
      ],
    }),
    { status: 200 },
  );
}

function emptyDraftResponse(): Response {
  return new Response(JSON.stringify({ draft: null }), { status: 200 });
}

function renderPage() {
  return render(
    <Providers>
      <HomePage />
    </Providers>,
  );
}

describe("HomePage session bootstrap", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("renders the shell after a first session bootstrap", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(sessionResponse({ restored: false }))
      .mockResolvedValueOnce(conversationResponse())
      .mockResolvedValueOnce(emptyDraftResponse());
    vi.stubGlobal("fetch", fetchMock);

    renderPage();

    expect(screen.getByRole("status")).toHaveTextContent(/starting your guest session/i);
    await screen.findByText("Welcome to the synthetic demonstration.");

    expect(screen.getByRole("heading", { name: "AI Supply Assistant" })).toBeInTheDocument();
    expect(screen.getByText(/synthetic-data demonstration/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Quotation (0)" })).toBeEnabled();
    expect(screen.getByText("Welcome to the synthetic demonstration.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/sessions",
      expect.objectContaining({ credentials: "include", method: "POST" }),
    );
  });

  it("restores an existing guest session from a 200 bootstrap response", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(sessionResponse({ restored: true }))
        .mockResolvedValueOnce(conversationResponse())
        .mockResolvedValueOnce(emptyDraftResponse()),
    );

    renderPage();

    expect(await screen.findByText("Welcome to the synthetic demonstration.")).toBeInTheDocument();
  });

  it("renders an expiry-safe error when rebootstrap is rejected", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 401 })));

    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent(/guest session expired/i);
  });

  it("renders a safe accessible error for unavailable bootstrap", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network unavailable")));

    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent(/could not start a guest session/i);
  });

  it("aborts the bootstrap request when the page unmounts", async () => {
    let requestSignal: AbortSignal | undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string, options: RequestInit) => {
        requestSignal = options.signal ?? undefined;
        return new Promise<Response>(() => undefined);
      }),
    );

    const { unmount } = renderPage();
    await waitFor(() => expect(requestSignal).toBeDefined());
    unmount();

    expect(requestSignal?.aborted).toBe(true);
  });
});
