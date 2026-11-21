import { useState } from "react";

import type { ProductCardPublic } from "@/lib/api/client";

type ProductCardProps = {
  product: ProductCardPublic;
  isSelected: boolean;
  onSelect: (sku: string) => void;
};

function availabilityLabel(availability: ProductCardPublic["availability"]): string {
  return (availability ?? "unavailable")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function attributeSummary(attributes: ProductCardPublic["selector_attributes"]): string | null {
  const entries = Object.entries(attributes ?? {}).filter(
    ([, value]) => typeof value === "string" || typeof value === "number",
  );
  if (entries.length === 0) {
    return null;
  }
  return entries.map(([key, value]) => `${key}: ${String(value)}`).join(" · ");
}

export function ProductCard({ product, isSelected, onSelect }: ProductCardProps) {
  const attributes = attributeSummary(product.selector_attributes);
  const [imageUnavailable, setImageUnavailable] = useState(false);

  return (
    <article
      aria-label={`${product.name}, ${product.sku}`}
      className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
    >
      {product.primary_image_reference && !imageUnavailable ? (
        // Product images are backend-provided external references; a plain image preserves the
        // catalog fallback behavior without requiring a speculative Next image-host allowlist.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          alt={`${product.name} product image`}
          className="mb-3 h-32 w-full rounded-md bg-slate-100 object-cover"
          onError={() => setImageUnavailable(true)}
          src={product.primary_image_reference}
        />
      ) : (
        <div
          aria-label={`${product.name} placeholder image`}
          className="mb-3 flex h-32 items-center justify-center rounded-md bg-sky-50 text-sm text-sky-900"
          role="img"
        >
          {product.image_fallback_key ?? "Product image unavailable"}
        </div>
      )}
      <h3 className="font-semibold text-slate-900">{product.name}</h3>
      {attributes ? <p className="mt-1 text-sm text-slate-700">{attributes}</p> : null}
      <dl className="mt-3 grid gap-1 text-sm text-slate-700">
        <div>
          <dt className="inline font-medium">SKU: </dt>
          <dd className="inline">{product.sku}</dd>
        </div>
        <div>
          <dt className="inline font-medium">Sales unit: </dt>
          <dd className="inline">{product.sales_unit}</dd>
        </div>
        <div>
          <dt className="inline font-medium">Indicative price snapshot: </dt>
          <dd className="inline">${product.indicative_price_usd} USD</dd>
        </div>
        <div>
          <dt className="inline font-medium">Availability snapshot: </dt>
          <dd className="inline">{availabilityLabel(product.availability)}</dd>
        </div>
      </dl>
      <p className="mt-2 text-xs text-slate-500">
        Product details recheck current indicative price and categorical availability.
      </p>
      <button
        aria-pressed={isSelected}
        className="mt-4 min-h-11 rounded-md border border-sky-700 px-3 py-2 text-sm font-medium text-sky-800 hover:bg-sky-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-700"
        onClick={() => onSelect(product.sku)}
        type="button"
      >
        {isSelected ? "Viewing details" : `View details for ${product.sku}`}
      </button>
    </article>
  );
}
