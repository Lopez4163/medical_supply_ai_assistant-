"use client";

import { useEffect, useRef, useState } from "react";

import { ApiClientError } from "@/lib/api/client";
import type { DraftQuotePublic } from "@/lib/api/client";

import { QuotationReview } from "./quotation-review";
import type { DraftQuoteController } from "./use-draft-quote";

type QuotationDrawerProps = { controller: DraftQuoteController };

function errorMessage(error: unknown): string {
  if (error instanceof ApiClientError && error.status === 409) {
    return "The quotation changed. Refresh it before trying again.";
  }
  return "The quotation could not be updated. No change has been assumed.";
}

export function QuotationDrawer({ controller }: QuotationDrawerProps) {
  const [isOpen, setOpen] = useState(false);
  const [view, setView] = useState<"draft" | "review">("draft");
  const [reviewDraft, setReviewDraft] = useState<DraftQuotePublic | null>(null);
  const [quantity, setQuantity] = useState<Record<string, string>>({});
  const [quantityError, setQuantityError] = useState<Record<string, string>>({});
  const triggerRef = useRef<HTMLButtonElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const draft = controller.draft;

  useEffect(() => {
    if (isOpen) closeRef.current?.focus();
  }, [isOpen]);

  function closeDrawer() {
    setOpen(false);
    triggerRef.current?.focus();
  }

  function updateLine(lineId: string, value: string) {
    const nextQuantity = Number(value);
    if (!Number.isInteger(nextQuantity) || nextQuantity <= 0) {
      setQuantityError({ ...quantityError, [lineId]: "Enter a positive whole quantity." });
      return;
    }
    setQuantityError({ ...quantityError, [lineId]: "" });
    controller.updateLine(lineId, nextQuantity);
  }

  return (
    <>
      <button
        aria-expanded={isOpen}
        aria-controls="quotation-drawer"
        className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm"
        onClick={() => setOpen(true)}
        ref={triggerRef}
        type="button"
      >
        Quotation ({draft?.lines.length ?? 0})
      </button>
      <aside
        aria-label="Quotation drawer"
        aria-modal="false"
        aria-labelledby="quotation-drawer-title"
        className="fixed inset-y-0 right-0 z-20 w-full max-w-none overflow-y-auto border-l border-slate-200 bg-white p-4 shadow-xl sm:max-w-md sm:p-5"
        id="quotation-drawer"
        hidden={!isOpen}
        onKeyDown={(event) => {
          if (event.key === "Escape") closeDrawer();
        }}
        role="dialog"
        tabIndex={-1}
      >
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold" id="quotation-drawer-title">
            Draft quotation
          </h2>
          <button
            className="rounded px-2 py-1 underline"
            onClick={closeDrawer}
            ref={closeRef}
            type="button"
          >
            Close
          </button>
        </div>
        <p className="mt-2 text-sm text-slate-600">
          Indicative only. This does not reserve stock or create an order.
        </p>
        {controller.draftQuery.isPending ? (
          <p role="status" className="mt-4">
            Loading quotation…
          </p>
        ) : null}
        {controller.draftQuery.error ? (
          <p role="alert" className="mt-4 text-red-800">
            Unable to restore your quotation.
          </p>
        ) : null}
        {!controller.draftQuery.isPending && !controller.draftQuery.error && !draft ? (
          <p className="mt-4">Your draft is empty.</p>
        ) : null}
        {draft && view === "draft" ? (
          <div className="mt-4 space-y-4">
            {draft.lines.map((line) => (
              <article className="rounded border border-slate-200 p-3" key={line.id}>
                <p className="font-medium">{line.product_name}</p>
                <p className="text-sm">
                  {line.sku} · {line.sales_unit}
                </p>
                <p className="text-sm">
                  ${line.indicative_unit_price_usd} each · ${line.indicative_line_subtotal_usd}{" "}
                  total
                </p>
                <p className="text-sm text-slate-600">{line.availability_notice}</p>
                <label className="mt-2 block text-sm">
                  Quantity
                  <input
                    aria-describedby={
                      quantityError[line.id] ? `line-quantity-error-${line.id}` : undefined
                    }
                    className="ml-2 w-20 rounded border p-1"
                    min="1"
                    onChange={(event) =>
                      setQuantity({ ...quantity, [line.id]: event.target.value })
                    }
                    type="number"
                    value={quantity[line.id] ?? String(line.requested_quantity)}
                  />
                </label>
                {quantityError[line.id] ? (
                  <p
                    className="mt-1 text-sm text-red-800"
                    id={`line-quantity-error-${line.id}`}
                    role="alert"
                  >
                    {quantityError[line.id]}
                  </p>
                ) : null}
                <div className="mt-2 flex gap-3">
                  <button
                    disabled={controller.isPending}
                    onClick={() =>
                      updateLine(line.id, quantity[line.id] ?? String(line.requested_quantity))
                    }
                    type="button"
                  >
                    Update
                  </button>
                  <button
                    disabled={controller.isPending}
                    onClick={() => controller.removeLine(line.id)}
                    type="button"
                  >
                    Remove
                  </button>
                </div>
              </article>
            ))}
            <p className="font-semibold">Indicative total: ${draft.indicative_total_usd}</p>
            <p className="text-sm text-slate-600">
              Prices and availability will be revalidated when you review this quotation.
            </p>
            <button
              className="rounded bg-sky-700 px-3 py-2 text-sm font-medium text-white disabled:bg-slate-300"
              disabled={controller.isPending}
              onClick={() => {
                setReviewDraft(draft);
                setView("review");
              }}
              type="button"
            >
              Review quotation
            </button>
          </div>
        ) : null}
        {view === "review" && (draft ?? reviewDraft) ? (
          <QuotationReview
            draft={draft ?? reviewDraft!}
            onCancel={() => {
              setReviewDraft(null);
              setView("draft");
            }}
            onSubmitted={controller.refreshDraft}
          />
        ) : null}
        {controller.error ? (
          <p role="alert" className="mt-4 text-red-800">
            {errorMessage(controller.error)}
          </p>
        ) : null}
        {controller.retryOperation ? (
          <button
            className="mt-2 underline"
            disabled={controller.isPending}
            onClick={controller.retryLastOperation}
            type="button"
          >
            Retry draft change
          </button>
        ) : null}
      </aside>
    </>
  );
}
