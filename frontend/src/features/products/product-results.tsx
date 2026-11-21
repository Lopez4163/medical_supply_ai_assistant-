"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { ApiClientError, getProduct, type ProductCardPublic } from "@/lib/api/client";
import { queryKeys } from "@/lib/query/query-keys";

import { ProductCard } from "./product-card";

type ProductResultsProps = {
  conversationId: string;
  products: ProductCardPublic[];
  resultContext?: "search" | "alternatives";
  nextCursor: string | null;
  onShowMore: (cursor: string) => void;
};

function productGroups(products: ProductCardPublic[]): ProductCardPublic[][] {
  const groups = new Map<string, ProductCardPublic[]>();
  for (const product of products.slice(0, 5)) {
    const group = groups.get(product.product_id) ?? [];
    group.push(product);
    groups.set(product.product_id, group);
  }
  return [...groups.values()];
}

function ProductDetail({ conversationId, sku }: { conversationId: string; sku: string }) {
  const detailQuery = useQuery({
    queryKey: queryKeys.product(conversationId, sku),
    queryFn: ({ signal }) => getProduct(sku, signal),
  });

  if (detailQuery.isPending) {
    return <p role="status">Loading product details…</p>;
  }
  if (detailQuery.error) {
    const unavailable =
      detailQuery.error instanceof ApiClientError && detailQuery.error.status === 404;
    return (
      <p role="alert">
        {unavailable
          ? "This product is no longer available. Choose another result."
          : "Product details could not be loaded. Try selecting the product again."}
      </p>
    );
  }
  const detail = detailQuery.data;
  return (
    <section
      aria-label={`Details for ${detail.sku}`}
      className="rounded-md bg-slate-50 p-3 text-sm text-slate-700"
    >
      <p className="font-medium text-slate-900">{detail.name}</p>
      <p className="mt-1">{detail.description}</p>
      <p className="mt-2">Current indicative price: ${detail.indicative_price_usd} USD</p>
      <p>Current categorical availability: {detail.availability.replaceAll("_", " ")}</p>
      <p className="mt-2 text-slate-600">Details are indicative synthetic catalog information.</p>
    </section>
  );
}

export function ProductResults({
  conversationId,
  products,
  resultContext = "search",
  nextCursor,
  onShowMore,
}: ProductResultsProps) {
  const availableProducts = products.slice(0, resultContext === "alternatives" ? 3 : 5);
  const groups = useMemo(() => productGroups(availableProducts), [availableProducts]);
  const [selectedSku, setSelectedSku] = useState<string | null>(null);
  const activeSku = availableProducts.some((product) => product.sku === selectedSku)
    ? selectedSku
    : null;

  if (availableProducts.length === 0) {
    return <p className="text-sm text-slate-700">No matching products were returned.</p>;
  }

  return (
    <section aria-label="Product results" className="space-y-3">
      {groups.map((variants) => (
        <section key={variants[0].product_id}>
          {variants.length > 1 ? (
            <label className="mb-2 block text-sm font-medium text-slate-800">
              Choose a sellable SKU for {variants[0].name}
              <select
                aria-label={`Choose a sellable SKU for ${variants[0].name}`}
                className="mt-1 block w-full rounded-md border border-slate-300 bg-white p-2"
                onChange={(event) => setSelectedSku(event.target.value)}
                value={activeSku ?? ""}
              >
                <option disabled value="">
                  Select a SKU
                </option>
                {variants.map((variant) => (
                  <option key={variant.sku} value={variant.sku}>
                    {variant.sku}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <div className="grid gap-3 sm:grid-cols-2">
            {variants.map((product) => (
              <ProductCard
                isSelected={activeSku === product.sku}
                key={product.sku}
                onSelect={setSelectedSku}
                product={product}
              />
            ))}
          </div>
        </section>
      ))}
      {activeSku ? (
        <ProductDetail conversationId={conversationId} key={activeSku} sku={activeSku} />
      ) : null}
      {nextCursor ? (
        <button
          className="min-h-11 rounded-md border border-sky-700 px-3 py-2 text-sm font-medium text-sky-800 hover:bg-sky-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-700"
          onClick={() => onShowMore(nextCursor)}
          type="button"
        >
          Show more products
        </button>
      ) : null}
    </section>
  );
}
