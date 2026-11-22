import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ProductCardPublic } from "@/lib/api/client";

import { ProductResults } from "./product-results";

const conversationId = "f1e8f2ab-26cb-4e63-ae58-a82d1a649ada";

function product(overrides: Partial<ProductCardPublic> = {}): ProductCardPublic {
  return {
    availability: "in_stock",
    category_code: "PPE",
    category_name: "Personal protective equipment",
    image_fallback_key: "PPE fallback",
    indicative_price_usd: "12.00",
    lifecycle_status: "active",
    name: "Nitrile Gloves",
    primary_image_reference: null,
    product_id: "gloves",
    sales_unit: "Box of 100",
    selector_attributes: { size: "Medium" },
    sku: "PPE-NIT-M",
    ...overrides,
  };
}

function detailResponse(sku = "PPE-NIT-M"): Response {
  return new Response(
    JSON.stringify({
      ...product({ sku }),
      description: `Synthetic details for ${sku}.`,
      searchable_attributes: {},
    }),
    { status: 200 },
  );
}

function renderResults(props: Partial<React.ComponentProps<typeof ProductResults>> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(
    <QueryClientProvider client={client}>
      <ProductResults
        conversationId={conversationId}
        nextCursor={null}
        onShowMore={() => undefined}
        products={[product()]}
        {...props}
      />
    </QueryClientProvider>,
  );
  return { ...view, client };
}

describe("ProductResults", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("renders public card fields and safely loads a selected resolved SKU detail", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(detailResponse()));
    renderResults();

    expect(screen.getByText("Nitrile Gloves")).toBeInTheDocument();
    expect(screen.getByText("SKU:")).toBeInTheDocument();
    expect(screen.getByText("PPE-NIT-M")).toBeInTheDocument();
    expect(screen.getByText("Indicative price snapshot:")).toBeInTheDocument();
    expect(screen.getByText("Availability snapshot:")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /placeholder image/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "View details for PPE-NIT-M" }));
    expect(await screen.findByText(/Synthetic details for PPE-NIT-M/)).toBeInTheDocument();
    expect(screen.getByText("Current indicative price: $12.00 USD")).toBeInTheDocument();
    expect(screen.getByText("Current categorical availability: in stock")).toBeInTheDocument();
  });

  it("maps variant selection to the selected sellable SKU", async () => {
    const fetchMock = vi.fn().mockResolvedValue(detailResponse("PPE-NIT-L"));
    vi.stubGlobal("fetch", fetchMock);
    renderResults({
      products: [product(), product({ sku: "PPE-NIT-L", selector_attributes: { size: "Large" } })],
    });

    const selector = screen.getByRole("combobox", { name: /choose a sellable sku/i });
    fireEvent.change(selector, { target: { value: "PPE-NIT-L" } });
    await waitFor(() =>
      expect(fetchMock).toHaveBeenLastCalledWith(
        expect.stringContaining("PPE-NIT-L"),
        expect.any(Object),
      ),
    );
    expect(screen.getByRole("button", { name: "Viewing details" })).toBeInTheDocument();
  });

  it("requires a selected sellable SKU and positive whole quantity before adding", () => {
    const onAddToQuote = vi.fn();
    renderResults({ onAddToQuote });

    const addButton = screen.getByRole("button", { name: "Add to quote" });
    expect(addButton).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "View details for PPE-NIT-M" }));
    expect(addButton).toBeEnabled();
    fireEvent.click(addButton);
    expect(screen.getByRole("alert")).toHaveTextContent("positive whole quantity");
    fireEvent.change(screen.getByLabelText("Quantity for PPE-NIT-M"), { target: { value: "2" } });
    fireEvent.click(addButton);

    expect(onAddToQuote).toHaveBeenCalledWith("PPE-NIT-M", 2);
  });

  it("uses only the backend cursor for a five-card Show More batch", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(detailResponse()));
    const onShowMore = vi.fn();
    renderResults({
      nextCursor: "opaque-server-cursor",
      onShowMore,
      products: Array.from({ length: 6 }, (_, index) =>
        product({ product_id: `p-${index}`, sku: `SKU-${index}`, name: `Product ${index}` }),
      ),
    });

    expect(screen.getAllByRole("article")).toHaveLength(5);
    fireEvent.click(screen.getByRole("button", { name: "Show more products" }));
    expect(onShowMore).toHaveBeenCalledWith("opaque-server-cursor");
  });

  it("limits compatible alternative cards to the approved three-card presentation", () => {
    renderResults({
      resultContext: "alternatives",
      products: Array.from({ length: 5 }, (_, index) =>
        product({
          product_id: `alternative-${index}`,
          sku: `ALT-${index}`,
          name: `Alternative ${index}`,
        }),
      ),
    });

    expect(screen.getAllByRole("article")).toHaveLength(3);
    expect(screen.queryByText("Alternative 3")).not.toBeInTheDocument();
  });

  it("shows unavailable and loading errors without retaining a stale product detail", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 404 })));
    renderResults();
    fireEvent.click(screen.getByRole("button", { name: "View details for PPE-NIT-M" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("no longer available");
  });

  it("uses the fallback image if an approved remote image cannot load", () => {
    renderResults({
      products: [product({ primary_image_reference: "https://example.test/gloves.jpg" })],
    });

    fireEvent.error(screen.getByRole("img", { name: "Nitrile Gloves product image" }));

    expect(screen.getByRole("img", { name: "Nitrile Gloves placeholder image" })).toHaveTextContent(
      "PPE fallback",
    );
  });

  it("keeps native detail, SKU selection, and Show More controls keyboard-focusable", () => {
    renderResults({
      nextCursor: "opaque-server-cursor",
      products: [product(), product({ sku: "PPE-NIT-L", selector_attributes: { size: "Large" } })],
    });

    const selector = screen.getByRole("combobox", { name: /choose a sellable sku/i });
    const detailButton = screen.getByRole("button", { name: "View details for PPE-NIT-M" });
    const moreButton = screen.getByRole("button", { name: "Show more products" });
    selector.focus();
    expect(selector).toHaveFocus();
    detailButton.focus();
    expect(detailButton).toHaveFocus();
    moreButton.focus();
    expect(moreButton).toHaveFocus();
  });

  it("does not render an old session's in-flight product detail after session replacement", async () => {
    let guestAAborted = false;
    const guestB = "5600df46-1be9-4f08-9eb9-c4c0496b3b63";
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockImplementationOnce(
          (_input: RequestInfo | URL, init?: RequestInit) =>
            new Promise<Response>((_resolve, reject) => {
              init?.signal?.addEventListener("abort", () => {
                guestAAborted = true;
                reject(new DOMException("Aborted", "AbortError"));
              });
            }),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              ...product(),
              description: "Guest B product detail.",
              searchable_attributes: {},
            }),
            { status: 200 },
          ),
        ),
    );
    const { client, rerender } = renderResults();
    fireEvent.click(screen.getByRole("button", { name: "View details for PPE-NIT-M" }));
    expect(await screen.findByRole("status")).toHaveTextContent(/loading product details/i);

    rerender(
      <QueryClientProvider client={client}>
        <ProductResults
          conversationId={guestB}
          nextCursor={null}
          onShowMore={() => undefined}
          products={[product()]}
        />
      </QueryClientProvider>,
    );
    expect(await screen.findByText("Guest B product detail.")).toBeInTheDocument();
    await waitFor(() => expect(guestAAborted).toBe(true));
    expect(screen.queryByText("Guest A stale detail.")).not.toBeInTheDocument();
  });
});
