import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

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

describe("HomePage session bootstrap", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("renders the shell after a first session bootstrap", async () => {
    const fetchMock = vi.fn().mockResolvedValue(sessionResponse({ restored: false }));
    vi.stubGlobal("fetch", fetchMock);

    render(<HomePage />);

    expect(screen.getByRole("status")).toHaveTextContent(/starting your guest session/i);
    await screen.findByText("Welcome to the synthetic demonstration.");

    expect(screen.getByRole("heading", { name: "AI Supply Assistant" })).toBeInTheDocument();
    expect(screen.getByText(/synthetic-data demonstration/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Quotation: 0 line items" })).toBeDisabled();
    expect(screen.getByText("Welcome to the synthetic demonstration.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/sessions",
      expect.objectContaining({ credentials: "include", method: "POST" }),
    );
  });

  it("restores an existing guest session from a 200 bootstrap response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sessionResponse({ restored: true })));

    render(<HomePage />);

    expect(await screen.findByText("Your guest session was restored.")).toBeInTheDocument();
  });

  it("renders an expiry-safe error when rebootstrap is rejected", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 401 })));

    render(<HomePage />);

    expect(await screen.findByRole("alert")).toHaveTextContent(/guest session expired/i);
  });

  it("renders a safe accessible error for unavailable bootstrap", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network unavailable")));

    render(<HomePage />);

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

    const { unmount } = render(<HomePage />);
    await waitFor(() => expect(requestSignal).toBeDefined());
    unmount();

    expect(requestSignal?.aborted).toBe(true);
  });
});
