import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ChatInterface } from "./chat-interface";

const sessionState = {
  status: "ready" as const,
  session: {
    conversation_id: "31dced59-7efc-4b51-8c8a-2e8a1c2f34f9",
    expires_at: "2026-11-18T12:00:00Z",
    restored: true,
    welcome_message: "Welcome.",
  },
};

function message({
  id,
  ordinal,
  role = "assistant",
  text,
  elements = [],
}: {
  id: string;
  ordinal: number;
  role?: "assistant" | "user";
  text: string;
  elements?: unknown[];
}) {
  return {
    id,
    ordinal,
    role,
    kind: ordinal === 0 ? "welcome" : "turn",
    text,
    elements,
    created_at: "2026-11-18T12:00:00Z",
    freshness: "historical_snapshot",
  };
}

function historyResponse(
  messages = [message({ id: "welcome", ordinal: 0, text: "Welcome back." })],
  conversationId = sessionState.session.conversation_id,
): Response {
  return new Response(JSON.stringify({ conversation_id: conversationId, messages }), {
    status: 200,
  });
}

function renderChat(state = sessionState) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(
    <QueryClientProvider client={queryClient}>
      <ChatInterface sessionState={state} />
    </QueryClientProvider>,
  );
  return { ...view, queryClient };
}

describe("ChatInterface", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("restores persisted messages and renders all approved structured elements", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        historyResponse([
          message({
            id: "assistant-turn",
            ordinal: 1,
            text: "Here is what I found.",
            elements: [
              {
                kind: "product_results",
                result_context: "search",
                result_set: {
                  products: [
                    {
                      sku: "PPE-NIT-M",
                      product_id: "nitrile-gloves",
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
                  next_cursor: null,
                },
              },
              {
                kind: "inventory_notice",
                notice: {
                  sku: "PPE-NIT-M",
                  availability: "limited_stock",
                  quantity_sufficient: false,
                  message: "Availability is limited.",
                },
              },
              { kind: "quote_update", quote: { draft_id: "draft", version: 2 } },
              {
                kind: "confirmation_prompt",
                prompt: {
                  title: "Review quote",
                  message: "Review before submitting.",
                  confirm_label: "Review",
                },
              },
              {
                kind: "source_reference",
                source: {
                  source_id: "about",
                  title: "About this demo",
                  excerpt: "Synthetic data only.",
                },
              },
              {
                kind: "support_inquiry_form",
                form: {
                  title: "Need support?",
                  description: "We can prepare a synthetic inquiry.",
                },
              },
            ],
          }),
        ]),
      ),
    );

    renderChat();

    expect(await screen.findByText("Here is what I found.")).toBeInTheDocument();
    expect(screen.getByText(/Nitrile Gloves/)).toBeInTheDocument();
    expect(screen.getByText("Availability snapshot:")).toBeInTheDocument();
    expect(screen.queryByText(/Current categorical availability:/)).not.toBeInTheDocument();
    expect(screen.getByText("Availability is limited.")).toBeInTheDocument();
    expect(screen.getByText("Your quotation draft was updated.")).toBeInTheDocument();
    expect(screen.getByText("Review quote")).toBeInTheDocument();
    expect(screen.getByText(/About this demo/)).toBeInTheDocument();
    expect(screen.getByText("Need support?")).toBeInTheDocument();
    expect(screen.getByRole("log", { name: "Conversation messages" })).toBeInTheDocument();
  });

  it("sends once with Enter while Shift+Enter preserves a newline", async () => {
    let resolveTurn: (response: Response) => void = () => undefined;
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(historyResponse())
      .mockImplementationOnce(
        () =>
          new Promise<Response>((resolve) => {
            resolveTurn = resolve;
          }),
      );
    vi.stubGlobal("fetch", fetchMock);
    renderChat();

    await screen.findByText("Welcome back.");
    const composer = screen.getByLabelText("Message the AI Supply Assistant");
    fireEvent.change(composer, { target: { value: "Hello" } });
    expect(fireEvent.keyDown(composer, { key: "Enter", shiftKey: true })).toBe(true);
    fireEvent.change(composer, { target: { value: "Hello\nthere" } });
    expect(composer).toHaveValue("Hello\nthere");

    fireEvent.keyDown(composer, { key: "Enter" });
    fireEvent.keyDown(composer, { key: "Enter" });
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(screen.getByRole("button", { name: "Sending…" })).toBeDisabled();

    resolveTurn(
      new Response(
        JSON.stringify({
          conversation_id: sessionState.session.conversation_id,
          client_message_id: "client-id",
          user_message: message({ id: "user-1", ordinal: 1, role: "user", text: "Hello\nthere" }),
          assistant_message: message({ id: "assistant-1", ordinal: 2, text: "Hello to you too." }),
          elements: [],
          draft_changed: false,
          request_id: "request-id",
        }),
        { status: 200 },
      ),
    );

    expect(await screen.findByText("Hello to you too.")).toBeInTheDocument();
    expect(screen.getAllByRole("article").map((article) => article.textContent)).toEqual([
      expect.stringContaining("Welcome back."),
      expect.stringContaining("Hello\nthere"),
      expect.stringContaining("Hello to you too."),
    ]);
    expect(screen.getAllByLabelText(/^Sent at /)).toHaveLength(3);
  });

  it("clears guest A history before guest B restoration in one QueryClient", async () => {
    const sessionB = {
      ...sessionState,
      session: { ...sessionState.session, conversation_id: "b6c9d102-5a27-48e3-9930-0e0c9f902c2d" },
    };
    let resolveGuestBHistory: (response: Response) => void = () => undefined;
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          historyResponse([message({ id: "guest-a", ordinal: 0, text: "Guest A history." })]),
        )
        .mockImplementationOnce(
          () =>
            new Promise<Response>((resolve) => {
              resolveGuestBHistory = resolve;
            }),
        ),
    );

    const { queryClient, rerender } = renderChat();
    await screen.findByText("Guest A history.");
    rerender(
      <QueryClientProvider client={queryClient}>
        <ChatInterface sessionState={sessionB} />
      </QueryClientProvider>,
    );

    expect(screen.queryByText("Guest A history.")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(/restoring your conversation/i);
    resolveGuestBHistory(
      historyResponse(
        [message({ id: "guest-b", ordinal: 0, text: "Guest B history." })],
        sessionB.session.conversation_id,
      ),
    );

    expect(await screen.findByText("Guest B history.")).toBeInTheDocument();
  });

  it("does not render a stale in-flight response after session replacement", async () => {
    const sessionB = {
      ...sessionState,
      session: { ...sessionState.session, conversation_id: "b6c9d102-5a27-48e3-9930-0e0c9f902c2d" },
    };
    let resolveGuestATurn: (response: Response) => void = () => undefined;
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(historyResponse())
        .mockImplementationOnce(
          () =>
            new Promise<Response>((resolve) => {
              resolveGuestATurn = resolve;
            }),
        )
        .mockResolvedValueOnce(
          historyResponse(
            [message({ id: "guest-b", ordinal: 0, text: "Guest B history." })],
            sessionB.session.conversation_id,
          ),
        ),
    );
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { rerender } = render(
      <QueryClientProvider client={queryClient}>
        <ChatInterface sessionState={sessionState} />
      </QueryClientProvider>,
    );

    await screen.findByText("Welcome back.");
    fireEvent.change(screen.getByLabelText("Message the AI Supply Assistant"), {
      target: { value: "Guest A request" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Sending…" })).toBeDisabled());
    rerender(
      <QueryClientProvider client={queryClient}>
        <ChatInterface sessionState={sessionB} />
      </QueryClientProvider>,
    );
    await screen.findByText("Guest B history.");

    resolveGuestATurn(
      new Response(
        JSON.stringify({
          conversation_id: sessionState.session.conversation_id,
          client_message_id: "stale-client-id",
          user_message: message({
            id: "user-a",
            ordinal: 1,
            role: "user",
            text: "Guest A request",
          }),
          assistant_message: message({
            id: "assistant-a",
            ordinal: 2,
            text: "Guest A stale reply.",
          }),
          elements: [],
          draft_changed: false,
          request_id: "request-id",
        }),
        { status: 200 },
      ),
    );

    await waitFor(() => expect(screen.queryByText("Guest A stale reply.")).not.toBeInTheDocument());
  });

  it("retries an uncertain request with the same client message identifier", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(historyResponse())
      .mockRejectedValueOnce(new TypeError("network unavailable"))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            conversation_id: sessionState.session.conversation_id,
            client_message_id: "reconciled",
            user_message: message({ id: "user-2", ordinal: 1, role: "user", text: "Find gloves" }),
            assistant_message: message({ id: "assistant-2", ordinal: 2, text: "I found gloves." }),
            elements: [],
            draft_changed: false,
            request_id: "request-id",
          }),
          { status: 200 },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    renderChat();

    await screen.findByText("Welcome back.");
    fireEvent.change(screen.getByLabelText("Message the AI Supply Assistant"), {
      target: { value: "Find gloves" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/could not confirm/i);

    const firstBody = JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body));
    fireEvent.click(screen.getByRole("button", { name: "Retry message" }));
    await screen.findByText("I found gloves.");
    const retryBody = JSON.parse(String(fetchMock.mock.calls[2]?.[1]?.body));

    expect(retryBody.client_message_id).toBe(firstBody.client_message_id);
    expect(screen.getAllByText("Find gloves")).toHaveLength(1);
  });

  it("continues product results with the opaque chat cursor and exact Show More command", async () => {
    const product = {
      sku: "PPE-NIT-M",
      product_id: "nitrile-gloves",
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
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        historyResponse([
          message({
            id: "results-1",
            ordinal: 1,
            text: "First product batch.",
            elements: [
              {
                kind: "product_results",
                result_context: "search",
                result_set: { products: [product], next_cursor: "opaque-chat-cursor" },
              },
            ],
          }),
        ]),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            conversation_id: sessionState.session.conversation_id,
            client_message_id: "show-more-id",
            user_message: message({ id: "user-more", ordinal: 2, role: "user", text: "show more" }),
            assistant_message: message({
              id: "results-2",
              ordinal: 3,
              text: "Second product batch.",
              elements: [
                {
                  kind: "product_results",
                  result_context: "search",
                  result_set: {
                    products: [{ ...product, sku: "PPE-NIT-L", name: "Large Nitrile Gloves" }],
                    next_cursor: null,
                  },
                },
              ],
            }),
            elements: [
              {
                kind: "product_results",
                result_context: "search",
                result_set: {
                  products: [{ ...product, sku: "PPE-NIT-L", name: "Large Nitrile Gloves" }],
                  next_cursor: null,
                },
              },
            ],
            draft_changed: false,
            request_id: "request-id",
          }),
          { status: 200 },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    renderChat();

    await screen.findByText("First product batch.");
    fireEvent.click(screen.getByRole("button", { name: "Show more products" }));
    await screen.findByText("Second product batch.");

    expect(JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body))).toMatchObject({
      cursor: "opaque-chat-cursor",
      text: "show more",
    });
    expect(screen.getByText("Nitrile Gloves")).toBeInTheDocument();
    expect(screen.getByText("Large Nitrile Gloves")).toBeInTheDocument();
    expect(screen.getAllByText("Nitrile Gloves")).toHaveLength(1);
  });

  it("uses the structured alternatives context to limit compatible alternatives", async () => {
    const products = Array.from({ length: 5 }, (_, index) => ({
      sku: `ALT-${index}`,
      product_id: `alternative-${index}`,
      name: `Alternative ${index}`,
      category_code: "PPE",
      category_name: "Personal protective equipment",
      sales_unit: "Box of 100",
      indicative_price_usd: "12.00",
      lifecycle_status: "active",
      selector_attributes: {},
      primary_image_reference: null,
      image_fallback_key: "PPE fallback",
      availability: "in_stock",
    }));
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        historyResponse([
          message({
            id: "alternatives",
            ordinal: 1,
            text: "Here are compatible choices.",
            elements: [
              {
                kind: "product_results",
                result_context: "alternatives",
                result_set: { products, next_cursor: null },
              },
            ],
          }),
        ]),
      ),
    );
    renderChat();

    expect(await screen.findByText("Alternative 0")).toBeInTheDocument();
    expect(screen.getByText("Alternative 2")).toBeInTheDocument();
    expect(screen.queryByText("Alternative 3")).not.toBeInTheDocument();
  });

  it("handles a rejected or expired product cursor as a definite failure", async () => {
    const product = {
      sku: "PPE-NIT-M",
      product_id: "nitrile-gloves",
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
    };
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          historyResponse([
            message({
              id: "results-1",
              ordinal: 1,
              text: "First product batch.",
              elements: [
                {
                  kind: "product_results",
                  result_context: "search",
                  result_set: { products: [product], next_cursor: "expired-cursor" },
                },
              ],
            }),
          ]),
        )
        .mockResolvedValueOnce(new Response(null, { status: 422 })),
    );
    renderChat();

    await screen.findByText("First product batch.");
    fireEvent.click(screen.getByRole("button", { name: "Show more products" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/message was not accepted/i);
    expect(screen.queryByRole("button", { name: "Retry message" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Message the AI Supply Assistant")).not.toBeDisabled();
  });

  it("renders an accessible expiration error and disables sending", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 401 })));
    renderChat();

    expect(await screen.findByRole("alert")).toHaveTextContent(/guest session expired/i);
    expect(screen.getByLabelText("Message the AI Supply Assistant")).toBeDisabled();
  });

  it("unlocks the composer after a definite validation failure without a retry action", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(historyResponse())
        .mockResolvedValueOnce(new Response(null, { status: 422 })),
    );
    renderChat();

    await screen.findByText("Welcome back.");
    fireEvent.change(screen.getByLabelText("Message the AI Supply Assistant"), {
      target: { value: "Find gloves" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/message was not accepted/i);
    expect(screen.queryByRole("button", { name: "Retry message" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Message the AI Supply Assistant")).not.toBeDisabled();
  });

  it("does not offer uncertain recovery after an Origin rejection", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(historyResponse())
        .mockResolvedValueOnce(new Response(null, { status: 403 })),
    );
    renderChat();

    await screen.findByText("Welcome back.");
    fireEvent.change(screen.getByLabelText("Message the AI Supply Assistant"), {
      target: { value: "Find gloves" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/security check/i);
    expect(screen.queryByRole("button", { name: "Retry message" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Message the AI Supply Assistant")).not.toBeDisabled();
  });
});
