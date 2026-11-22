import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "./app-shell";

const conversationId = "31dced59-7efc-4b51-8c8a-2e8a1c2f34f9";

const sessionState = {
  status: "ready" as const,
  session: {
    conversation_id: conversationId,
    expires_at: "2026-11-20T12:00:00Z",
    restored: true,
    welcome_message: "Welcome.",
  },
};

function response(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200 });
}

function draft() {
  return {
    id: "c84d9f32-1b01-4c8b-b56f-a38b46e1c60d",
    status: "active",
    version: 1,
    lines: [
      {
        id: "9dc44386-ff7b-4c47-9779-15d13e5b3b0a",
        sku: "PPE-NIT-M",
        product_id: "gloves",
        product_name: "Nitrile Gloves",
        selector_attributes: { size: "Medium" },
        sales_unit: "Box of 100",
        requested_quantity: 2,
        indicative_unit_price_usd: "12.00",
        indicative_line_subtotal_usd: "24.00",
        availability: "in_stock",
        quantity_sufficient: true,
        availability_notice: "Available.",
        created_at: "2026-11-20T12:00:00Z",
        updated_at: "2026-11-20T12:00:00Z",
      },
    ],
    indicative_total_usd: "24.00",
    created_at: "2026-11-20T12:00:00Z",
    updated_at: "2026-11-20T12:00:00Z",
  };
}

function history() {
  return {
    conversation_id: conversationId,
    messages: [
      {
        id: "welcome",
        ordinal: 0,
        role: "assistant",
        kind: "welcome",
        text: "Nitrile gloves are available.",
        elements: [
          {
            kind: "product_results",
            result_context: "search",
            result_set: {
              next_cursor: null,
              products: [
                {
                  sku: "PPE-NIT-M",
                  product_id: "gloves",
                  name: "Nitrile Gloves",
                  category_code: "PPE",
                  category_name: "Personal protective equipment",
                  sales_unit: "Box of 100",
                  indicative_price_usd: "12.00",
                  lifecycle_status: "active",
                  selector_attributes: { size: "Medium" },
                  primary_image_reference: null,
                  image_fallback_key: "PPE fallback",
                  availability: "in_stock",
                },
              ],
            },
          },
        ],
        created_at: "2026-11-20T12:00:00Z",
        freshness: "historical_snapshot",
      },
    ],
  };
}

describe("AppShell quotation controller", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("uses one authoritative draft controller for a product-card add and the header count", async () => {
    let currentDraft: ReturnType<typeof draft> | null = null;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/conversations/current")) return response(history());
      if (url.endsWith("/quotations/draft")) return response({ draft: currentDraft });
      if (url.endsWith("/products/PPE-NIT-M")) {
        return response({
          ...history().messages[0]?.elements[0]?.result_set.products[0],
          description: "Synthetic details.",
          searchable_attributes: {},
        });
      }
      if (url.endsWith("/quotations/draft/lines") && init?.method === "POST") {
        expect(JSON.parse(String(init.body))).toMatchObject({
          expected_version: 0,
          quantity: 2,
          sku: "PPE-NIT-M",
        });
        currentDraft = draft();
        return response(currentDraft);
      }
      throw new Error(`Unexpected request ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <AppShell sessionState={sessionState} />
      </QueryClientProvider>,
    );

    await screen.findByText("Nitrile gloves are available.");
    expect(
      fetchMock.mock.calls.filter(([url]) => String(url).endsWith("/quotations/draft")),
    ).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "View details for PPE-NIT-M" }));
    fireEvent.change(screen.getByLabelText("Quantity for PPE-NIT-M"), { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: "Add to quote" }));

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Quotation (1)" })).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Quotation (1)" }));
    fireEvent.change(screen.getByRole("spinbutton", { name: "Quantity" }), {
      target: { value: "0" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Update" }));
    expect(screen.getByRole("alert")).toHaveTextContent("positive whole quantity");
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "PATCH")).toBe(false);
  });

  it("keeps Add to quote disabled until the authoritative draft query resolves", async () => {
    let resolveDraft: (value: Response) => void = () => undefined;
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/conversations/current")) return Promise.resolve(response(history()));
      if (url.endsWith("/quotations/draft")) {
        return new Promise<Response>((resolve) => {
          resolveDraft = resolve;
        });
      }
      if (url.endsWith("/products/PPE-NIT-M")) {
        return Promise.resolve(
          response({
            ...history().messages[0]?.elements[0]?.result_set.products[0],
            description: "Synthetic details.",
            searchable_attributes: {},
          }),
        );
      }
      throw new Error(`Unexpected request ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <AppShell sessionState={sessionState} />
      </QueryClientProvider>,
    );

    await screen.findByText("Nitrile gloves are available.");
    fireEvent.click(screen.getByRole("button", { name: "View details for PPE-NIT-M" }));
    fireEvent.change(screen.getByLabelText("Quantity for PPE-NIT-M"), { target: { value: "2" } });
    expect(screen.getByRole("button", { name: "Adding…" })).toBeDisabled();

    resolveDraft(response({ draft: null }));
    expect(await screen.findByRole("button", { name: "Add to quote" })).toBeEnabled();
    expect(
      fetchMock.mock.calls.some(([url]) => String(url).endsWith("/quotations/draft/lines")),
    ).toBe(false);
  });

  it("opens as a keyboard-accessible responsive dialog and restores focus on Escape", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/conversations/current")) return Promise.resolve(response(history()));
        if (url.endsWith("/quotations/draft")) return Promise.resolve(response({ draft: draft() }));
        throw new Error(`Unexpected request ${url}`);
      }),
    );
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <AppShell sessionState={sessionState} />
      </QueryClientProvider>,
    );

    await screen.findByText("Nitrile gloves are available.");
    const trigger = screen.getByRole("button", { name: "Quotation (1)" });
    trigger.focus();
    fireEvent.click(trigger);
    const drawer = screen.getByRole("dialog", { name: "Quotation drawer" });
    await waitFor(() => expect(screen.getByRole("button", { name: "Close" })).toHaveFocus());
    expect(drawer).toHaveClass("w-full", "max-w-md");
    fireEvent.keyDown(drawer, { key: "Escape" });

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(trigger).toHaveFocus();
  });
});
