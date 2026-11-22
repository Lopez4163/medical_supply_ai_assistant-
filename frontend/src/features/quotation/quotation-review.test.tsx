import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { DraftQuotePublic } from "@/lib/api/client";

import { QuotationReview } from "./quotation-review";

function draft(version = 3): DraftQuotePublic {
  return {
    created_at: "2026-11-20T12:00:00Z",
    id: "c84d9f32-1b01-4c8b-b56f-a38b46e1c60d",
    indicative_total_usd: "24.00",
    lines: [
      {
        availability: "limited_stock",
        availability_notice: "Availability is limited.",
        created_at: "2026-11-20T12:00:00Z",
        id: "9dc44386-ff7b-4c47-9779-15d13e5b3b0a",
        indicative_line_subtotal_usd: "24.00",
        indicative_unit_price_usd: "12.00",
        product_id: "gloves",
        product_name: "Nitrile Gloves",
        quantity_sufficient: false,
        requested_quantity: 2,
        sales_unit: "Box of 100",
        selector_attributes: { size: "Medium" },
        sku: "PPE-NIT-M",
        updated_at: "2026-11-20T12:00:00Z",
      },
    ],
    status: "active",
    updated_at: "2026-11-20T12:00:00Z",
    version,
  };
}

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

function reviewResponse() {
  return {
    disclosure: "This is a synthetic quotation inquiry.",
    draft: draft(),
    expires_at: "2026-11-20T13:00:00Z",
    review_token: "x".repeat(24),
  };
}

function renderReview(currentDraft = draft()) {
  const onCancel = vi.fn();
  const onSubmitted = vi.fn().mockResolvedValue(undefined);
  const view = render(
    <QuotationReview draft={currentDraft} onCancel={onCancel} onSubmitted={onSubmitted} />,
  );
  return { ...view, onCancel, onSubmitted };
}

function fillValidContact() {
  fireEvent.change(screen.getByLabelText("First name"), { target: { value: "Ada" } });
  fireEvent.change(screen.getByLabelText("Last name"), { target: { value: "Lovelace" } });
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: "ada@example.test" } });
  fireEvent.change(screen.getByLabelText("Delivery city"), { target: { value: "Cali" } });
}

async function openReview() {
  fillValidContact();
  fireEvent.click(screen.getByRole("button", { name: "Review quotation" }));
  await screen.findByRole("heading", { name: "Review quotation" });
}

describe("QuotationReview", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("requires contact and a delivery city before requesting a review", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    renderReview();

    fireEvent.click(screen.getByRole("button", { name: "Review quotation" }));

    expect(await screen.findByText("Enter your first name")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toHaveAttribute("aria-describedby", "contact-error");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("cancels review collection without making a protected request", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const { onCancel } = renderReview();

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onCancel).toHaveBeenCalledOnce();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("renders the authoritative review and requires explicit confirmation before submitting", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(reviewResponse()))
      .mockResolvedValueOnce(
        response(
          {
            message: "The synthetic quotation inquiry was recorded.",
            reference: "Q-20261120-001",
            submitted_at: "2026-11-20T12:15:00Z",
          },
          201,
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    const { onSubmitted } = renderReview();

    await openReview();
    expect(screen.getByText("Current indicative price: $12.00 each")).toBeInTheDocument();
    expect(screen.getByText("Availability is limited.")).toBeInTheDocument();
    const confirm = screen.getByRole("button", { name: "Confirm quotation inquiry" });
    expect(confirm).toBeDisabled();
    fireEvent.click(screen.getByLabelText("I confirm this synthetic quotation inquiry."));
    fireEvent.click(confirm);

    expect(await screen.findByText("Reference: Q-20261120-001")).toBeInTheDocument();
    expect(onSubmitted).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("returns to a fresh review after a stale or expired confirmation", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(response(reviewResponse()))
        .mockResolvedValueOnce(response({ error: { code: "CONFIRMATION_INVALID" } }, 409)),
    );
    renderReview();

    await openReview();
    fireEvent.click(screen.getByLabelText("I confirm this synthetic quotation inquiry."));
    fireEvent.click(screen.getByRole("button", { name: "Confirm quotation inquiry" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("review is no longer valid");
    expect(screen.getByRole("form", { name: "Quotation review form" })).toBeInTheDocument();
    expect(screen.getByLabelText("First name")).toHaveValue("Ada");
  });

  it("reconciles an uncertain submission using the original operation id", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(reviewResponse()))
      .mockRejectedValueOnce(new TypeError("network unavailable"))
      .mockResolvedValueOnce(
        response({
          message: "The synthetic quotation inquiry was recorded.",
          reference: "Q-20261120-002",
          submitted_at: "2026-11-20T12:15:00Z",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    renderReview();

    await openReview();
    fireEvent.click(screen.getByLabelText("I confirm this synthetic quotation inquiry."));
    fireEvent.click(screen.getByRole("button", { name: "Confirm quotation inquiry" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("could not confirm");
    fireEvent.click(screen.getByRole("button", { name: "Check submission status" }));

    expect(await screen.findByText("Reference: Q-20261120-002")).toBeInTheDocument();
    expect(String(fetchMock.mock.calls[2]?.[0])).toContain("/quotations/submissions/reconcile/");
  });

  it("retries an unconfirmed submission with the original idempotency identifier", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(reviewResponse()))
      .mockRejectedValueOnce(new TypeError("network unavailable"))
      .mockResolvedValueOnce(response({ error: { code: "NOT_FOUND" } }, 404))
      .mockResolvedValueOnce(
        response({
          message: "The synthetic quotation inquiry was recorded.",
          reference: "Q-20261120-003",
          submitted_at: "2026-11-20T12:15:00Z",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    renderReview();

    await openReview();
    fireEvent.click(screen.getByLabelText("I confirm this synthetic quotation inquiry."));
    fireEvent.click(screen.getByRole("button", { name: "Confirm quotation inquiry" }));
    await screen.findByRole("button", { name: "Check submission status" });
    fireEvent.click(screen.getByRole("button", { name: "Check submission status" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("not been confirmed");
    fireEvent.click(screen.getByRole("button", { name: "Retry submission safely" }));

    expect(await screen.findByText("Reference: Q-20261120-003")).toBeInTheDocument();
    const firstSubmission = JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body));
    const retrySubmission = JSON.parse(String(fetchMock.mock.calls[3]?.[1]?.body));
    expect(retrySubmission.operation_id).toBe(firstSubmission.operation_id);
  });

  it("invalidates a rendered review if its draft version changes", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(reviewResponse())));
    const { rerender } = renderReview();

    await openReview();
    rerender(<QuotationReview draft={draft(4)} onCancel={vi.fn()} onSubmitted={vi.fn()} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("quotation changed");
    expect(screen.getByRole("form", { name: "Quotation review form" })).toBeInTheDocument();
  });

  it("drops review state when a replacement conversation remounts the drawer", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(reviewResponse())));
    const view = render(
      <QuotationReview key="guest-a" draft={draft()} onCancel={vi.fn()} onSubmitted={vi.fn()} />,
    );

    await openReview();
    view.rerender(
      <QuotationReview key="guest-b" draft={draft()} onCancel={vi.fn()} onSubmitted={vi.fn()} />,
    );

    expect(screen.getByRole("form", { name: "Quotation review form" })).toBeInTheDocument();
    expect(screen.getByLabelText("First name")).toHaveValue("");
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });
});
