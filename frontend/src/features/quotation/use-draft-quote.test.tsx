import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useDraftQuote } from "./use-draft-quote";

const conversationId = "31dced59-7efc-4b51-8c8a-2e8a1c2f34f9";

function draft(version: number, quantity = 1) {
  return {
    id: "c84d9f32-1b01-4c8b-b56f-a38b46e1c60d",
    status: "active",
    version,
    lines: [
      {
        id: "9dc44386-ff7b-4c47-9779-15d13e5b3b0a",
        sku: "PPE-NIT-M",
        product_id: "gloves",
        product_name: "Nitrile Gloves",
        selector_attributes: { size: "Medium" },
        sales_unit: "Box of 100",
        requested_quantity: quantity,
        indicative_unit_price_usd: "12.00",
        indicative_line_subtotal_usd: String(12 * quantity),
        availability: "in_stock",
        quantity_sufficient: true,
        availability_notice: "Available.",
        created_at: "2026-11-20T12:00:00Z",
        updated_at: "2026-11-20T12:00:00Z",
      },
    ],
    indicative_total_usd: String(12 * quantity),
    created_at: "2026-11-20T12:00:00Z",
    updated_at: "2026-11-20T12:00:00Z",
  };
}

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

function DraftHarness({
  activeConversationId = conversationId,
}: {
  activeConversationId?: string;
}) {
  const quote = useDraftQuote(activeConversationId);
  return (
    <div>
      <p>version:{quote.draft?.version ?? "empty"}</p>
      <button
        disabled={quote.isPending}
        onClick={() => quote.addLine("PPE-NIT-M", 2)}
        type="button"
      >
        Add
      </button>
      <button
        onClick={() => quote.updateLine("9dc44386-ff7b-4c47-9779-15d13e5b3b0a", 3)}
        type="button"
      >
        Update
      </button>
      <button
        onClick={() => quote.removeLine("9dc44386-ff7b-4c47-9779-15d13e5b3b0a")}
        type="button"
      >
        Remove
      </button>
      {quote.retryOperation ? (
        <button onClick={quote.retryLastOperation} type="button">
          Retry
        </button>
      ) : null}
      {quote.error ? <p role="alert">request failed</p> : null}
    </div>
  );
}

function renderHarness() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <DraftHarness />
    </QueryClientProvider>,
  );
}

describe("useDraftQuote", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("adds, updates, and removes using the authoritative draft version", async () => {
    let currentDraft: ReturnType<typeof draft> | null = null;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/quotations/draft")) return response({ draft: currentDraft });
      if (url.endsWith("/quotations/draft/lines") && init?.method === "POST") {
        expect(JSON.parse(String(init.body))).toMatchObject({
          expected_version: 0,
          quantity: 2,
          sku: "PPE-NIT-M",
        });
        currentDraft = draft(1, 2);
        return response(currentDraft);
      }
      if (init?.method === "PATCH") {
        expect(JSON.parse(String(init?.body))).toMatchObject({ expected_version: 1, quantity: 3 });
        currentDraft = draft(2, 3);
        return response(currentDraft);
      }
      if (init?.method === "DELETE") {
        expect(JSON.parse(String(init?.body))).toMatchObject({ expected_version: 2 });
        currentDraft = null;
        return response(draft(3, 3));
      }
      throw new Error(`Unexpected request ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    renderHarness();

    await waitFor(() => expect(screen.getByRole("button", { name: "Add" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "Add" }));
    await screen.findByText("version:1");
    fireEvent.click(screen.getByRole("button", { name: "Update" }));
    await screen.findByText("version:2");
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/lines/"),
        expect.objectContaining({ method: "DELETE" }),
      ),
    );
  });

  it("reuses a stable operation id only for an uncertain retry", async () => {
    let addAttempts = 0;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/quotations/draft")) {
        return response({ draft: addAttempts > 1 ? draft(1, 2) : null });
      }
      if (init?.method === "POST") {
        addAttempts += 1;
        if (addAttempts === 1) throw new TypeError("network unavailable");
        return response(draft(1, 2));
      }
      throw new Error(`Unexpected request ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    renderHarness();

    await waitFor(() => expect(screen.getByRole("button", { name: "Add" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    const first = JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body));
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await screen.findByText("version:1");
    const retry = JSON.parse(String(fetchMock.mock.calls[2]?.[1]?.body));

    expect(retry.operation_id).toBe(first.operation_id);
  });

  it("refreshes the draft after a version conflict without offering an unsafe retry", async () => {
    const refreshed = draft(4, 4);
    let draftReads = 0;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/quotations/draft")) {
        draftReads += 1;
        return response({ draft: draftReads === 1 ? draft(3, 1) : refreshed });
      }
      if (init?.method === "PATCH")
        return response({ error: { code: "QUOTE_VERSION_CONFLICT" } }, 409);
      throw new Error(`Unexpected request ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    renderHarness();

    await screen.findByText("version:3");
    fireEvent.click(screen.getByRole("button", { name: "Update" }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    await screen.findByText("version:4");
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
  });

  it("does not retain a replaced guest's draft while the new conversation is loading", async () => {
    const guestB = "5600df46-1be9-4f08-9eb9-c4c0496b3b63";
    let guestAAborted = false;
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        if (String(input).endsWith("/quotations/draft") && !guestAAborted) {
          return new Promise<Response>((_resolve, reject) => {
            init?.signal?.addEventListener("abort", () => {
              guestAAborted = true;
              reject(new DOMException("Aborted", "AbortError"));
            });
          });
        }
        return Promise.resolve(response({ draft: draft(5, 2) }));
      }),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const view = render(
      <QueryClientProvider client={client}>
        <DraftHarness />
      </QueryClientProvider>,
    );

    view.rerender(
      <QueryClientProvider client={client}>
        <DraftHarness activeConversationId={guestB} />
      </QueryClientProvider>,
    );
    expect(await screen.findByText("version:5")).toBeInTheDocument();
    await waitFor(() => expect(guestAAborted).toBe(true));
  });
});
