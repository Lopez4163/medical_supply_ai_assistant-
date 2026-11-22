import { useState } from "react";

import type { ProductCardPublic } from "@/lib/api/client";

type ProductCardProps = {
  product: ProductCardPublic;
  isSelected: boolean;
  isAddingToQuote?: boolean;
  onAddToQuote?: (sku: string, quantity: number) => void;
  onSelect: (sku: string) => void;
  requiresSelection?: boolean;
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

export function ProductCard({
  product,
  isAddingToQuote = false,
  isSelected,
  onAddToQuote,
  onSelect,
  requiresSelection = false,
}: ProductCardProps) {
  const attributes = attributeSummary(product.selector_attributes);
  const [imageUnavailable, setImageUnavailable] = useState(false);
  const [quantity, setQuantity] = useState("");
  const [quantityError, setQuantityError] = useState<string | null>(null);

  function addToQuote() {
    const parsedQuantity = Number(quantity);
    if (!Number.isInteger(parsedQuantity) || parsedQuantity <= 0) {
      setQuantityError("Enter a positive whole quantity before adding this SKU.");
      return;
    }
    setQuantityError(null);
    onAddToQuote?.(product.sku, parsedQuantity);
  }

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
      {onAddToQuote ? (
        <div className="mt-3 border-t border-slate-100 pt-3">
          <label
            className="block text-sm font-medium text-slate-800"
            htmlFor={`quantity-${product.sku}`}
          >
            Quantity for {product.sku}
          </label>
          <div className="mt-1 flex gap-2">
            <input
              aria-describedby={quantityError ? `quantity-error-${product.sku}` : undefined}
              className="w-24 rounded-md border border-slate-300 p-2"
              id={`quantity-${product.sku}`}
              inputMode="numeric"
              min="1"
              onChange={(event) => setQuantity(event.target.value)}
              type="number"
              value={quantity}
            />
            <button
              className="min-h-11 rounded-md bg-sky-700 px-3 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-300"
              disabled={isAddingToQuote || (requiresSelection && !isSelected)}
              onClick={addToQuote}
              type="button"
            >
              {isAddingToQuote ? "Adding…" : "Add to quote"}
            </button>
          </div>
          {requiresSelection && !isSelected ? (
            <p className="mt-1 text-xs text-slate-600">Select this SKU to add it.</p>
          ) : null}
          {quantityError ? (
            <p
              className="mt-1 text-sm text-red-800"
              id={`quantity-error-${product.sku}`}
              role="alert"
            >
              {quantityError}
            </p>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}
