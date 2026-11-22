"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import {
  ApiClientError,
  reconcileQuote,
  reviewQuote,
  submitQuote,
  type DraftQuotePublic,
  type QuoteReviewPublic,
  type QuoteReviewRequest,
  type QuoteSubmissionPublic,
} from "@/lib/api/client";

const reviewSchema = z
  .object({
    delivery_city: z.string().trim().max(100),
    email: z.string().trim().email("Enter a valid email address").or(z.literal("")),
    first_name: z.string().trim().min(1, "Enter your first name").max(80),
    fulfillment: z.enum(["delivery", "cali_pickup"]),
    last_name: z.string().trim().min(1, "Enter your last name").max(80),
    phone: z.string().trim().max(40).or(z.literal("")),
  })
  .superRefine((value, context) => {
    if (!value.email && !value.phone) {
      context.addIssue({
        code: "custom",
        message: "Provide an email address or phone number",
        path: ["email"],
      });
    }
    if (value.fulfillment === "delivery" && !value.delivery_city) {
      context.addIssue({
        code: "custom",
        message: "Enter a delivery city",
        path: ["delivery_city"],
      });
    }
  });

type ReviewFormValues = z.infer<typeof reviewSchema>;

type ReviewState = {
  request: QuoteReviewRequest;
  response: QuoteReviewPublic;
};

type QuotationReviewProps = {
  draft: DraftQuotePublic;
  onCancel: () => void;
  onSubmitted: () => Promise<void>;
};

function isDefiniteFailure(error: unknown): boolean {
  return error instanceof ApiClientError && [400, 401, 403, 404, 409, 422].includes(error.status);
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiClientError && error.status === 409) {
    return "This review is no longer valid because the quotation changed or expired. Review it again.";
  }
  if (error instanceof ApiClientError && [401, 403].includes(error.status)) {
    return "Your guest session is no longer valid. Refresh to start a new session.";
  }
  if (error instanceof ApiClientError && error.status === 422) {
    return "The quotation details need attention. Refresh and review again.";
  }
  return "We could not confirm the request. No quotation submission has been assumed.";
}

function ReviewLines({ draft }: { draft: DraftQuotePublic }) {
  return (
    <div className="mt-4 space-y-3" aria-label="Reviewed quotation lines">
      {draft.lines.map((line) => (
        <article className="rounded border border-slate-200 p-3" key={line.id}>
          <p className="font-medium">{line.product_name}</p>
          <p className="text-sm">
            {line.sku} · {line.sales_unit} · quantity {line.requested_quantity}
          </p>
          <p className="text-sm">
            Current indicative price: ${line.indicative_unit_price_usd} each
          </p>
          <p className="text-sm text-slate-600">{line.availability_notice}</p>
        </article>
      ))}
      <p className="font-semibold">Current indicative total: ${draft.indicative_total_usd}</p>
    </div>
  );
}

export function QuotationReview({ draft, onCancel, onSubmitted }: QuotationReviewProps) {
  const form = useForm<ReviewFormValues>({
    defaultValues: {
      delivery_city: "",
      email: "",
      first_name: "",
      fulfillment: "delivery",
      last_name: "",
      phone: "",
    },
    resolver: zodResolver(reviewSchema),
  });
  const fulfillment = useWatch({ control: form.control, name: "fulfillment" });
  const [review, setReview] = useState<ReviewState | null>(null);
  const [submission, setSubmission] = useState<QuoteSubmissionPublic | null>(null);
  const [operationId, setOperationId] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [isReviewing, setReviewing] = useState(false);
  const [isSubmitting, setSubmitting] = useState(false);
  const [isReconciling, setReconciling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uncertain, setUncertain] = useState(false);

  const staleReview = Boolean(review && review.response.draft.version !== draft.version);
  const displayedError = staleReview
    ? "The quotation changed. Review the refreshed details before submitting."
    : error;

  async function requestReview(values: ReviewFormValues) {
    setError(null);
    setReviewing(true);
    const request: QuoteReviewRequest = {
      contact: {
        email: values.email || null,
        first_name: values.first_name,
        last_name: values.last_name,
        phone: values.phone || null,
      },
      delivery_city: values.fulfillment === "delivery" ? values.delivery_city : null,
      expected_version: draft.version,
      fulfillment: values.fulfillment,
    };
    try {
      setReview({ request, response: await reviewQuote(request) });
      setConfirmed(false);
      setOperationId(null);
      setUncertain(false);
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setReviewing(false);
    }
  }

  async function submit() {
    if (!review || !confirmed) return;
    const nextOperationId = operationId ?? crypto.randomUUID();
    setOperationId(nextOperationId);
    setError(null);
    setSubmitting(true);
    try {
      const result = await submitQuote({
        confirmation: true,
        expected_version: review.response.draft.version,
        operation_id: nextOperationId,
        review_token: review.response.review_token,
      });
      setSubmission(result);
      await onSubmitted();
    } catch (submissionError) {
      if (isDefiniteFailure(submissionError)) {
        if (submissionError instanceof ApiClientError && submissionError.status === 409) {
          setReview(null);
          setConfirmed(false);
          setOperationId(null);
        }
        setError(errorMessage(submissionError));
      } else {
        setUncertain(true);
        setError(errorMessage(submissionError));
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function reconcile() {
    if (!operationId) return;
    setError(null);
    setReconciling(true);
    try {
      const result = await reconcileQuote(operationId);
      setSubmission(result);
      setUncertain(false);
      await onSubmitted();
    } catch (reconcileError) {
      if (reconcileError instanceof ApiClientError && reconcileError.status === 404) {
        setError(
          "The submission has not been confirmed yet. You may retry safely with the same confirmation.",
        );
      } else {
        setError(errorMessage(reconcileError));
      }
    } finally {
      setReconciling(false);
    }
  }

  if (submission) {
    return (
      <section
        aria-label="Quotation submitted"
        className="mt-4 rounded-md border border-emerald-200 bg-emerald-50 p-4"
      >
        <h2 className="font-semibold text-emerald-950">Quotation inquiry recorded</h2>
        <p className="mt-1 text-sm text-emerald-900">Reference: {submission.reference}</p>
        <p className="mt-2 text-sm text-emerald-900">{submission.message}</p>
        <p className="mt-2 text-sm text-emerald-900">
          This synthetic demonstration does not create an order, reserve inventory, or guarantee
          fulfillment.
        </p>
        <button className="mt-3 underline" onClick={onCancel} type="button">
          Return to quotation
        </button>
      </section>
    );
  }

  if (review && !staleReview) {
    return (
      <section aria-label="Review quotation" className="mt-4">
        <h2 className="text-lg font-semibold">Review quotation</h2>
        <ReviewLines draft={review.response.draft} />
        <div className="mt-4 rounded-md bg-slate-50 p-3 text-sm text-slate-700">
          <p>
            {review.request.contact.first_name} {review.request.contact.last_name}
          </p>
          <p>{review.request.contact.email || review.request.contact.phone}</p>
          <p>
            {review.request.fulfillment === "delivery"
              ? `Delivery preference: ${review.request.delivery_city}`
              : "Fictional Cali pickup preference"}
          </p>
        </div>
        <p className="mt-3 text-sm text-slate-600">{review.response.disclosure}</p>
        <label className="mt-4 flex gap-2 text-sm">
          <input
            checked={confirmed}
            onChange={(event) => setConfirmed(event.target.checked)}
            type="checkbox"
          />{" "}
          I confirm this synthetic quotation inquiry.
        </label>
        {displayedError ? (
          <p className="mt-3 text-sm text-red-800" role="alert">
            {displayedError}
          </p>
        ) : null}
        <div className="mt-4 flex flex-wrap gap-3">
          <button
            className="rounded bg-sky-700 px-3 py-2 text-sm font-medium text-white disabled:bg-slate-300"
            disabled={!confirmed || isSubmitting || isReconciling}
            onClick={() => void submit()}
            type="button"
          >
            {isSubmitting ? "Submitting…" : "Confirm quotation inquiry"}
          </button>
          <button
            className="rounded border border-slate-300 px-3 py-2 text-sm"
            disabled={isSubmitting || isReconciling}
            onClick={() => {
              setReview(null);
              setConfirmed(false);
              setOperationId(null);
              setUncertain(false);
            }}
            type="button"
          >
            Edit review
          </button>
          <button
            className="rounded border border-slate-300 px-3 py-2 text-sm"
            disabled={isSubmitting || isReconciling}
            onClick={onCancel}
            type="button"
          >
            Cancel
          </button>
        </div>
        {uncertain ? (
          <div className="mt-3">
            <button
              className="underline"
              disabled={isReconciling || isSubmitting}
              onClick={() => void reconcile()}
              type="button"
            >
              {isReconciling ? "Checking submission…" : "Check submission status"}
            </button>
            <button
              className="ml-3 underline"
              disabled={isReconciling || isSubmitting}
              onClick={() => void submit()}
              type="button"
            >
              Retry submission safely
            </button>
          </div>
        ) : null}
      </section>
    );
  }

  return (
    <form
      aria-label="Quotation review form"
      className="mt-4 space-y-3"
      onSubmit={form.handleSubmit(requestReview)}
    >
      <h2 className="text-lg font-semibold">Review your quotation</h2>
      <p className="text-sm text-slate-600">
        Provide the minimum contact and preference details for this synthetic inquiry.
      </p>
      <label className="block text-sm">
        First name
        <input
          aria-describedby={form.formState.errors.first_name ? "first-name-error" : undefined}
          className="mt-1 block w-full rounded border p-2"
          {...form.register("first_name")}
        />
      </label>
      {form.formState.errors.first_name ? (
        <p id="first-name-error" role="alert" className="text-sm text-red-800">
          {form.formState.errors.first_name.message}
        </p>
      ) : null}
      <label className="block text-sm">
        Last name
        <input
          aria-describedby={form.formState.errors.last_name ? "last-name-error" : undefined}
          className="mt-1 block w-full rounded border p-2"
          {...form.register("last_name")}
        />
      </label>
      {form.formState.errors.last_name ? (
        <p id="last-name-error" role="alert" className="text-sm text-red-800">
          {form.formState.errors.last_name.message}
        </p>
      ) : null}
      <label className="block text-sm">
        Email
        <input
          className="mt-1 block w-full rounded border p-2"
          type="email"
          {...form.register("email")}
        />
      </label>
      <label className="block text-sm">
        Phone
        <input
          className="mt-1 block w-full rounded border p-2"
          type="tel"
          {...form.register("phone")}
        />
      </label>
      {form.formState.errors.email ? (
        <p role="alert" className="text-sm text-red-800">
          {form.formState.errors.email.message}
        </p>
      ) : null}
      <fieldset>
        <legend className="text-sm">Fulfillment preference</legend>
        <label className="mr-4">
          <input type="radio" value="delivery" {...form.register("fulfillment")} /> Delivery
        </label>
        <label>
          <input type="radio" value="cali_pickup" {...form.register("fulfillment")} /> Fictional
          Cali pickup
        </label>
      </fieldset>
      {fulfillment === "delivery" ? (
        <label className="block text-sm">
          Delivery city
          <input
            aria-describedby={
              form.formState.errors.delivery_city ? "delivery-city-error" : undefined
            }
            className="mt-1 block w-full rounded border p-2"
            {...form.register("delivery_city")}
          />
        </label>
      ) : null}
      {form.formState.errors.delivery_city ? (
        <p id="delivery-city-error" role="alert" className="text-sm text-red-800">
          {form.formState.errors.delivery_city.message}
        </p>
      ) : null}
      {displayedError ? (
        <p role="alert" className="text-sm text-red-800">
          {displayedError}
        </p>
      ) : null}
      <div className="flex gap-3">
        <button
          className="rounded bg-sky-700 px-3 py-2 text-sm font-medium text-white disabled:bg-slate-300"
          disabled={isReviewing}
          type="submit"
        >
          {isReviewing ? "Refreshing review…" : "Review quotation"}
        </button>
        <button
          className="rounded border border-slate-300 px-3 py-2 text-sm"
          onClick={onCancel}
          type="button"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
