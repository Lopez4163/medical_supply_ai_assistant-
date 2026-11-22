import type { ConversationMessagePublic } from "@/lib/api/client";

import { ProductResults } from "@/features/products/product-results";
import type { DraftQuoteController } from "@/features/quotation/use-draft-quote";
import { SupportInquiry } from "@/features/support/support-inquiry";

type StructuredElementsProps = {
  conversationId: string;
  elements: ConversationMessagePublic["elements"];
  onShowMore: (cursor: string) => void;
  quotationController?: DraftQuoteController;
};

export function StructuredElements({
  conversationId,
  elements,
  onShowMore,
  quotationController,
}: StructuredElementsProps) {
  return (
    <div className="mt-3 space-y-3">
      {elements.map((element, index) => {
        switch (element.kind) {
          case "product_results":
            return (
              <div
                className="rounded-md border border-slate-200 p-3"
                key={`${element.kind}-${index}`}
              >
                <p className="mb-2 text-sm font-medium text-slate-800">Product results</p>
                <ProductResults
                  conversationId={conversationId}
                  nextCursor={element.result_set.next_cursor}
                  onShowMore={onShowMore}
                  products={element.result_set.products}
                  isAddingToQuote={
                    quotationController?.isPending ||
                    quotationController?.draftQuery.isPending ||
                    false
                  }
                  onAddToQuote={quotationController?.addLine}
                  resultContext={element.result_context ?? "search"}
                />
              </div>
            );
          case "inventory_notice":
            return (
              <p
                className="rounded-md bg-amber-50 p-3 text-sm text-amber-900"
                key={`${element.kind}-${index}`}
              >
                {element.notice.message}
              </p>
            );
          case "quote_update":
            return (
              <p
                className="rounded-md bg-sky-50 p-3 text-sm text-sky-900"
                key={`${element.kind}-${index}`}
              >
                Your quotation draft was updated.
              </p>
            );
          case "confirmation_prompt":
            return (
              <section
                className="rounded-md border border-slate-200 p-3"
                key={`${element.kind}-${index}`}
              >
                <p className="font-medium text-slate-800">{element.prompt.title}</p>
                <p className="mt-1 text-sm text-slate-700">{element.prompt.message}</p>
                <p className="mt-2 text-sm text-slate-500">
                  {element.prompt.confirm_label} will be available in a later step.
                </p>
              </section>
            );
          case "source_reference":
            return (
              <aside
                className="rounded-md bg-slate-100 p-3 text-sm text-slate-700"
                key={`${element.kind}-${index}`}
              >
                <p className="font-medium">Source: {element.source.title}</p>
                <p className="mt-1">{element.source.excerpt}</p>
              </aside>
            );
          case "support_inquiry_form":
            return (
              <SupportInquiry
                description={element.form.description}
                key={`${element.kind}-${index}`}
                title={element.form.title}
              />
            );
        }
      })}
    </div>
  );
}
