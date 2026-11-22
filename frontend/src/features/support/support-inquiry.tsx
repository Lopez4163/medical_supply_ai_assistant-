"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import {
  ApiClientError,
  reconcileSupport,
  reviewSupport,
  submitSupport,
  type SupportInquiryPublic,
  type SupportReviewPublic,
  type SupportReviewRequest,
} from "@/lib/api/client";

const supportSchema = z
  .object({
    conversation_context: z.string().trim().max(2000),
    email: z.string().trim().email("Enter a valid email address").or(z.literal("")),
    first_name: z.string().trim().max(80),
    last_name: z.string().trim().max(80),
    opt_in: z.boolean().refine((value) => value, {
      error: "Choose to create a synthetic support inquiry",
    }),
    phone: z.string().trim().max(40).or(z.literal("")),
    reuse_contact: z.boolean(),
    subject: z.string().trim().min(1, "Enter a subject").max(200),
    summary: z.string().trim().min(1, "Enter a short summary").max(2000),
  })
  .superRefine((value, context) => {
    if (value.reuse_contact) return;
    if (!value.first_name) {
      context.addIssue({ code: "custom", message: "Enter your first name", path: ["first_name"] });
    }
    if (!value.last_name) {
      context.addIssue({ code: "custom", message: "Enter your last name", path: ["last_name"] });
    }
    if (!value.email && !value.phone) {
      context.addIssue({
        code: "custom",
        message: "Provide an email address or phone number",
        path: ["email"],
      });
    }
  });

type SupportFormValues = z.infer<typeof supportSchema>;

type SupportReviewState = {
  request: SupportReviewRequest;
  response: SupportReviewPublic;
};

type SupportInquiryProps = {
  description: string;
  title: string;
};

function isDefiniteFailure(error: unknown): boolean {
  return error instanceof ApiClientError && [400, 401, 403, 404, 409, 422].includes(error.status);
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiClientError && error.status === 409) {
    return "This support review is invalid or expired. Review it again.";
  }
  if (error instanceof ApiClientError && [401, 403].includes(error.status)) {
    return "Your guest session is no longer valid. Refresh to start a new session.";
  }
  if (error instanceof ApiClientError && error.status === 422) {
    return "The support inquiry needs attention. Check the details and review again.";
  }
  return "We could not confirm the support inquiry. No inquiry has been assumed.";
}

export function SupportInquiry({ description, title }: SupportInquiryProps) {
  const [stage, setStage] = useState<"intro" | "form" | "review" | "success">("intro");
  const [review, setReview] = useState<SupportReviewState | null>(null);
  const [submission, setSubmission] = useState<SupportInquiryPublic | null>(null);
  const [operationId, setOperationId] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [isReviewing, setReviewing] = useState(false);
  const [isSubmitting, setSubmitting] = useState(false);
  const [isReconciling, setReconciling] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const form = useForm<SupportFormValues>({
    defaultValues: {
      conversation_context: "",
      email: "",
      first_name: "",
      last_name: "",
      opt_in: false,
      phone: "",
      reuse_contact: false,
      subject: "",
      summary: "",
    },
    resolver: zodResolver(supportSchema),
  });
  const reuseContact = useWatch({ control: form.control, name: "reuse_contact" });

  function cancel() {
    setStage("intro");
    setReview(null);
    setConfirmed(false);
    setOperationId(null);
    setUncertain(false);
    setError(null);
  }

  async function requestReview(values: SupportFormValues) {
    setError(null);
    setReviewing(true);
    const request: SupportReviewRequest = {
      contact: values.reuse_contact
        ? null
        : {
            email: values.email || null,
            first_name: values.first_name,
            last_name: values.last_name,
            phone: values.phone || null,
          },
      conversation_context: values.conversation_context || null,
      opt_in: true,
      reuse_contact: values.reuse_contact,
      subject: values.subject,
      summary: values.summary,
    };
    try {
      setReview({ request, response: await reviewSupport(request) });
      setConfirmed(false);
      setOperationId(null);
      setUncertain(false);
      setStage("review");
    } catch (reviewError) {
      setError(errorMessage(reviewError));
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
      const result = await submitSupport({
        confirmation: true,
        operation_id: nextOperationId,
        review_token: review.response.review_token,
      });
      setSubmission(result);
      setStage("success");
    } catch (submissionError) {
      if (isDefiniteFailure(submissionError)) {
        if (submissionError instanceof ApiClientError && submissionError.status === 409) {
          setReview(null);
          setConfirmed(false);
          setOperationId(null);
          setStage("form");
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
      const result = await reconcileSupport(operationId);
      setSubmission(result);
      setUncertain(false);
      setStage("success");
    } catch (reconcileError) {
      if (reconcileError instanceof ApiClientError && reconcileError.status === 404) {
        setError(
          "The inquiry has not been confirmed yet. You may retry safely with the same confirmation.",
        );
      } else {
        setError(errorMessage(reconcileError));
      }
    } finally {
      setReconciling(false);
    }
  }

  if (stage === "success" && submission) {
    return (
      <section
        aria-label="Support inquiry submitted"
        className="rounded-md border border-emerald-200 bg-emerald-50 p-3"
      >
        <h3 className="font-medium text-emerald-950">Synthetic support inquiry recorded</h3>
        <p className="mt-1 text-sm text-emerald-900">Reference: {submission.reference}</p>
        <p className="mt-1 text-sm text-emerald-900">{submission.message}</p>
        <p className="mt-2 text-sm text-emerald-900">
          This demonstration does not notify real staff or promise a response.
        </p>
        <button className="mt-3 underline" onClick={cancel} type="button">
          Close
        </button>
      </section>
    );
  }

  if (stage === "review" && review) {
    return (
      <section
        aria-label="Review support inquiry"
        className="rounded-md border border-slate-200 p-3"
      >
        <h3 className="font-medium text-slate-900">Review support inquiry</h3>
        <p className="mt-2 text-sm font-medium">{review.response.subject}</p>
        <p className="mt-1 text-sm text-slate-700">{review.response.summary}</p>
        <p className="mt-3 text-sm text-slate-600">{review.response.disclosure}</p>
        <label className="mt-3 flex gap-2 text-sm">
          <input
            checked={confirmed}
            onChange={(event) => setConfirmed(event.target.checked)}
            type="checkbox"
          />{" "}
          I confirm this synthetic support inquiry.
        </label>
        {error ? (
          <p className="mt-3 text-sm text-red-800" role="alert">
            {error}
          </p>
        ) : null}
        <div className="mt-3 flex flex-wrap gap-3">
          <button
            className="rounded bg-sky-700 px-3 py-2 text-sm font-medium text-white disabled:bg-slate-300"
            disabled={!confirmed || isSubmitting || isReconciling}
            onClick={() => void submit()}
            type="button"
          >
            {isSubmitting ? "Submitting…" : "Confirm support inquiry"}
          </button>
          <button
            className="rounded border border-slate-300 px-3 py-2 text-sm"
            disabled={isSubmitting || isReconciling}
            onClick={() => {
              setStage("form");
              setConfirmed(false);
              setOperationId(null);
              setUncertain(false);
            }}
            type="button"
          >
            Edit inquiry
          </button>
          <button
            className="rounded border border-slate-300 px-3 py-2 text-sm"
            disabled={isSubmitting || isReconciling}
            onClick={cancel}
            type="button"
          >
            Cancel
          </button>
        </div>
        {uncertain ? (
          <div className="mt-3">
            <button
              className="underline"
              disabled={isSubmitting || isReconciling}
              onClick={() => void reconcile()}
              type="button"
            >
              {isReconciling ? "Checking inquiry…" : "Check inquiry status"}
            </button>
            <button
              className="ml-3 underline"
              disabled={isSubmitting || isReconciling}
              onClick={() => void submit()}
              type="button"
            >
              Retry inquiry safely
            </button>
          </div>
        ) : null}
      </section>
    );
  }

  if (stage === "form") {
    return (
      <form
        aria-label="Support inquiry form"
        className="space-y-3"
        onSubmit={form.handleSubmit(requestReview)}
      >
        <h3 className="font-medium text-slate-900">{title}</h3>
        <p className="text-sm text-slate-700">{description}</p>
        <label className="flex gap-2 text-sm">
          <input type="checkbox" {...form.register("opt_in")} /> I want to create a synthetic
          support inquiry.
        </label>
        {form.formState.errors.opt_in ? (
          <p className="text-sm text-red-800" role="alert">
            {form.formState.errors.opt_in.message}
          </p>
        ) : null}
        <label className="flex gap-2 text-sm">
          <input type="checkbox" {...form.register("reuse_contact")} /> Reuse contact details
          previously submitted in this same guest session.
        </label>
        {reuseContact ? (
          <p className="text-sm text-slate-600">
            Reuse is allowed only if this guest session has prior submitted contact details.
          </p>
        ) : (
          <>
            <label className="block text-sm">
              First name
              <input
                className="mt-1 block w-full rounded border p-2"
                {...form.register("first_name")}
              />
            </label>
            <label className="block text-sm">
              Last name
              <input
                className="mt-1 block w-full rounded border p-2"
                {...form.register("last_name")}
              />
            </label>
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
          </>
        )}
        {form.formState.errors.first_name ? (
          <p className="text-sm text-red-800" role="alert">
            {form.formState.errors.first_name.message}
          </p>
        ) : null}
        {form.formState.errors.last_name ? (
          <p className="text-sm text-red-800" role="alert">
            {form.formState.errors.last_name.message}
          </p>
        ) : null}
        {form.formState.errors.email ? (
          <p className="text-sm text-red-800" role="alert">
            {form.formState.errors.email.message}
          </p>
        ) : null}
        <label className="block text-sm">
          Subject
          <input className="mt-1 block w-full rounded border p-2" {...form.register("subject")} />
        </label>
        {form.formState.errors.subject ? (
          <p className="text-sm text-red-800" role="alert">
            {form.formState.errors.subject.message}
          </p>
        ) : null}
        <label className="block text-sm">
          Summary
          <textarea
            className="mt-1 block w-full rounded border p-2"
            rows={3}
            {...form.register("summary")}
          />
        </label>
        {form.formState.errors.summary ? (
          <p className="text-sm text-red-800" role="alert">
            {form.formState.errors.summary.message}
          </p>
        ) : null}
        <label className="block text-sm">
          Optional conversation context
          <textarea
            className="mt-1 block w-full rounded border p-2"
            rows={2}
            {...form.register("conversation_context")}
          />
        </label>
        {error ? (
          <p className="text-sm text-red-800" role="alert">
            {error}
          </p>
        ) : null}
        <div className="flex gap-3">
          <button
            className="rounded bg-sky-700 px-3 py-2 text-sm font-medium text-white disabled:bg-slate-300"
            disabled={isReviewing}
            type="submit"
          >
            {isReviewing ? "Reviewing…" : "Review inquiry"}
          </button>
          <button
            className="rounded border border-slate-300 px-3 py-2 text-sm"
            onClick={cancel}
            type="button"
          >
            Cancel
          </button>
        </div>
      </form>
    );
  }

  return (
    <section className="rounded-md border border-slate-200 p-3">
      <p className="font-medium text-slate-800">{title}</p>
      <p className="mt-1 text-sm text-slate-700">{description}</p>
      <button
        className="mt-3 rounded border border-sky-700 px-3 py-2 text-sm font-medium text-sky-800"
        onClick={() => setStage("form")}
        type="button"
      >
        Start support inquiry
      </button>
    </section>
  );
}
