import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "./app-shell";

const guestA = "31dced59-7efc-4b51-8c8a-2e8a1c2f34f9";
const guestB = "5600df46-1be9-4f08-9eb9-c4c0496b3b63";

function sessionState(conversationId: string) {
  return {
    status: "ready" as const,
    session: {
      conversation_id: conversationId,
      expires_at: "2026-11-20T12:00:00Z",
      restored: true,
      welcome_message: "Welcome.",
    },
  };
}

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

function draft() {
  return {
    created_at: "2026-11-20T12:00:00Z",
    id: "c84d9f32-1b01-4c8b-b56f-a38b46e1c60d",
    indicative_total_usd: "24.00",
    lines: [
      {
        availability: "in_stock",
        availability_notice: "Available.",
        created_at: "2026-11-20T12:00:00Z",
        id: "9dc44386-ff7b-4c47-9779-15d13e5b3b0a",
        indicative_line_subtotal_usd: "24.00",
        indicative_unit_price_usd: "12.00",
        product_id: "gloves",
        product_name: "Nitrile Gloves",
        quantity_sufficient: true,
        requested_quantity: 2,
        sales_unit: "Box of 100",
        selector_attributes: { size: "Medium" },
        sku: "PPE-NIT-M",
        updated_at: "2026-11-20T12:00:00Z",
      },
    ],
    status: "active",
    updated_at: "2026-11-20T12:00:00Z",
    version: 1,
  };
}

function history(conversationId: string, support = false) {
  return {
    conversation_id: conversationId,
    messages: [
      {
        created_at: "2026-11-20T12:00:00Z",
        elements: support
          ? [
              {
                form: {
                  description: "We can prepare a synthetic inquiry.",
                  title: "Need support?",
                },
                kind: "support_inquiry_form",
              },
            ]
          : [],
        freshness: "historical_snapshot",
        id: `welcome-${conversationId}`,
        kind: "welcome",
        ordinal: 0,
        role: "assistant",
        text: conversationId === guestA ? "Guest A history." : "Guest B history.",
      },
    ],
  };
}

function renderShell(state = sessionState(guestA)) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(
    <QueryClientProvider client={queryClient}>
      <AppShell sessionState={state} />
    </QueryClientProvider>,
  );
  return { ...view, queryClient };
}

function fillQuoteReview() {
  fireEvent.change(screen.getByLabelText("First name"), { target: { value: "Ada" } });
  fireEvent.change(screen.getByLabelText("Last name"), { target: { value: "Lovelace" } });
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: "ada@example.test" } });
  fireEvent.change(screen.getByLabelText("Delivery city"), { target: { value: "Cali" } });
}

function fillSupportForm() {
  fireEvent.click(screen.getByLabelText("I want to create a synthetic support inquiry."));
  fireEvent.change(screen.getByLabelText("First name"), { target: { value: "Ada" } });
  fireEvent.change(screen.getByLabelText("Last name"), { target: { value: "Lovelace" } });
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: "ada@example.test" } });
  fireEvent.change(screen.getByLabelText("Subject"), { target: { value: "Delivery question" } });
  fireEvent.change(screen.getByLabelText("Summary"), {
    target: { value: "Please review delivery options." },
  });
}

describe("AppShell protected workflows", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("clears the authoritative draft and header count after a verified quotation submission", async () => {
    let submitted = false;
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/conversations/current"))
          return Promise.resolve(response(history(guestA)));
        if (url.endsWith("/quotations/draft"))
          return Promise.resolve(response({ draft: submitted ? null : draft() }));
        if (url.endsWith("/quotations/draft/review")) {
          return Promise.resolve(
            response({
              disclosure: "Synthetic quotation inquiry.",
              draft: draft(),
              expires_at: "2026-11-20T13:00:00Z",
              review_token: "x".repeat(24),
            }),
          );
        }
        if (url.endsWith("/quotations/submissions") && init?.method === "POST") {
          submitted = true;
          return Promise.resolve(
            response(
              {
                message: "The synthetic quotation inquiry was recorded.",
                reference: "Q-20261120-004",
                submitted_at: "2026-11-20T12:15:00Z",
              },
              201,
            ),
          );
        }
        throw new Error(`Unexpected request ${url}`);
      }),
    );
    renderShell();

    await screen.findByText("Guest A history.");
    fireEvent.click(screen.getByRole("button", { name: "Quotation (1)" }));
    fireEvent.click(screen.getByRole("button", { name: "Review quotation" }));
    fillQuoteReview();
    fireEvent.click(screen.getByRole("button", { name: "Review quotation" }));
    await screen.findByRole("heading", { name: "Review quotation" });
    fireEvent.click(screen.getByLabelText("I confirm this synthetic quotation inquiry."));
    fireEvent.click(screen.getByRole("button", { name: "Confirm quotation inquiry" }));

    expect(await screen.findByText("Reference: Q-20261120-004")).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Quotation (0)" })).toBeInTheDocument(),
    );
  });

  it("cancels a structured support form without changing the actual draft or chat", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/conversations/current"))
        return Promise.resolve(response(history(guestA, true)));
      if (url.endsWith("/quotations/draft")) return Promise.resolve(response({ draft: draft() }));
      throw new Error(`Unexpected request ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    renderShell();

    await screen.findByText("Guest A history.");
    fireEvent.click(screen.getByRole("button", { name: "Start support inquiry" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.getByText("Guest A history.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Quotation (1)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start support inquiry" })).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/support/"))).toBe(false);
  });

  it("drops stale in-flight quote and support reviews after guest replacement", async () => {
    let resolveQuoteReview: (value: Response) => void = () => undefined;
    let resolveSupportReview: (value: Response) => void = () => undefined;
    let quoteReviewStarted = false;
    let supportReviewStarted = false;
    let activeConversation = guestA;
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/conversations/current")) {
          return Promise.resolve(response(history(activeConversation, true)));
        }
        if (url.endsWith("/quotations/draft")) return Promise.resolve(response({ draft: draft() }));
        if (url.endsWith("/quotations/draft/review")) {
          quoteReviewStarted = true;
          return new Promise<Response>((resolve) => {
            resolveQuoteReview = resolve;
          });
        }
        if (url.endsWith("/support/review")) {
          supportReviewStarted = true;
          return new Promise<Response>((resolve) => {
            resolveSupportReview = resolve;
          });
        }
        throw new Error(`Unexpected request ${url}`);
      }),
    );
    const { rerender, queryClient } = renderShell();

    await screen.findByText("Guest A history.");
    fireEvent.click(screen.getByRole("button", { name: "Quotation (1)" }));
    fireEvent.click(screen.getByRole("button", { name: "Review quotation" }));
    fillQuoteReview();
    fireEvent.click(screen.getByRole("button", { name: "Review quotation" }));
    await waitFor(() => expect(quoteReviewStarted).toBe(true));
    activeConversation = guestB;
    rerender(
      <QueryClientProvider client={queryClient}>
        <AppShell sessionState={sessionState(guestB)} />
      </QueryClientProvider>,
    );
    resolveQuoteReview(
      response({
        disclosure: "stale",
        draft: draft(),
        expires_at: "2026-11-20T13:00:00Z",
        review_token: "x".repeat(24),
      }),
    );
    expect(await screen.findByText("Guest B history.")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Review quotation" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Start support inquiry" }));
    fillSupportForm();
    fireEvent.click(screen.getByRole("button", { name: "Review inquiry" }));
    await waitFor(() => expect(supportReviewStarted).toBe(true));
    activeConversation = guestA;
    rerender(
      <QueryClientProvider client={queryClient}>
        <AppShell sessionState={sessionState(guestA)} />
      </QueryClientProvider>,
    );
    resolveSupportReview(
      response({
        disclosure: "stale",
        expires_at: "2026-11-20T13:00:00Z",
        review_token: "x".repeat(24),
        subject: "stale",
        summary: "stale",
      }),
    );
    expect(await screen.findByText("Guest A history.")).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Review support inquiry" }),
    ).not.toBeInTheDocument();
  });
});
