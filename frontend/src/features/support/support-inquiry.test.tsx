import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SupportInquiry } from "./support-inquiry";

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

function reviewResponse() {
  return {
    disclosure: "This is a synthetic support inquiry.",
    expires_at: "2026-11-20T13:00:00Z",
    review_token: "x".repeat(24),
    subject: "Delivery question",
    summary: "Please review delivery options.",
  };
}

function renderInquiry() {
  return render(
    <SupportInquiry description="We can prepare a synthetic inquiry." title="Need support?" />,
  );
}

function startForm() {
  fireEvent.click(screen.getByRole("button", { name: "Start support inquiry" }));
}

function fillInquiry() {
  fireEvent.click(screen.getByLabelText("I want to create a synthetic support inquiry."));
  fireEvent.change(screen.getByLabelText("First name"), { target: { value: "Ada" } });
  fireEvent.change(screen.getByLabelText("Last name"), { target: { value: "Lovelace" } });
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: "ada@example.test" } });
  fireEvent.change(screen.getByLabelText("Subject"), { target: { value: "Delivery question" } });
  fireEvent.change(screen.getByLabelText("Summary"), {
    target: { value: "Please review delivery options." },
  });
}

async function openReview() {
  fillInquiry();
  fireEvent.click(screen.getByRole("button", { name: "Review inquiry" }));
  await screen.findByRole("heading", { name: "Review support inquiry" });
}

describe("SupportInquiry", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("requires explicit opt-in and contact before review", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    renderInquiry();
    startForm();

    fireEvent.click(screen.getByRole("button", { name: "Review inquiry" }));

    expect(
      await screen.findByText("Choose to create a synthetic support inquiry"),
    ).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("sends same-session contact reuse only after explicit consent", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(reviewResponse()));
    vi.stubGlobal("fetch", fetchMock);
    renderInquiry();
    startForm();
    fireEvent.click(screen.getByLabelText("I want to create a synthetic support inquiry."));
    fireEvent.click(
      screen.getByLabelText(
        "Reuse contact details previously submitted in this same guest session.",
      ),
    );
    fireEvent.change(screen.getByLabelText("Subject"), { target: { value: "Delivery question" } });
    fireEvent.change(screen.getByLabelText("Summary"), {
      target: { value: "Please review delivery options." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Review inquiry" }));

    await screen.findByRole("heading", { name: "Review support inquiry" });
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toMatchObject({
      contact: null,
      opt_in: true,
      reuse_contact: true,
    });
  });

  it("cancels without requesting or submitting an inquiry", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    renderInquiry();
    startForm();

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.getByRole("button", { name: "Start support inquiry" })).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("requires confirmation and shows the verified synthetic reference", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(reviewResponse()))
      .mockResolvedValueOnce(
        response(
          {
            message: "The synthetic support inquiry was recorded.",
            reference: "S-20261120-001",
            submitted_at: "2026-11-20T12:15:00Z",
          },
          201,
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    renderInquiry();
    startForm();

    await openReview();
    const confirm = screen.getByRole("button", { name: "Confirm support inquiry" });
    expect(confirm).toBeDisabled();
    fireEvent.click(screen.getByLabelText("I confirm this synthetic support inquiry."));
    fireEvent.click(confirm);

    expect(await screen.findByText("Reference: S-20261120-001")).toBeInTheDocument();
    expect(screen.getByText(/does not notify real staff/i)).toBeInTheDocument();
  });

  it("reconciles an uncertain inquiry with its original operation id", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(reviewResponse()))
      .mockRejectedValueOnce(new TypeError("network unavailable"))
      .mockResolvedValueOnce(
        response({
          message: "The synthetic support inquiry was recorded.",
          reference: "S-20261120-002",
          submitted_at: "2026-11-20T12:15:00Z",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    renderInquiry();
    startForm();

    await openReview();
    fireEvent.click(screen.getByLabelText("I confirm this synthetic support inquiry."));
    fireEvent.click(screen.getByRole("button", { name: "Confirm support inquiry" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("could not confirm");
    fireEvent.click(screen.getByRole("button", { name: "Check inquiry status" }));

    expect(await screen.findByText("Reference: S-20261120-002")).toBeInTheDocument();
    expect(String(fetchMock.mock.calls[2]?.[0])).toContain("/support/inquiries/reconcile/");
  });

  it("returns to collection after an expired or stale support review", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(response(reviewResponse()))
        .mockResolvedValueOnce(response({ error: { code: "CONFIRMATION_INVALID" } }, 409)),
    );
    renderInquiry();
    startForm();

    await openReview();
    fireEvent.click(screen.getByLabelText("I confirm this synthetic support inquiry."));
    fireEvent.click(screen.getByRole("button", { name: "Confirm support inquiry" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("invalid or expired");
    expect(screen.getByRole("form", { name: "Support inquiry form" })).toBeInTheDocument();
    expect(screen.getByLabelText("Subject")).toHaveValue("Delivery question");
  });

  it("retries an unresolved inquiry with the original idempotency identifier", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(reviewResponse()))
      .mockRejectedValueOnce(new TypeError("network unavailable"))
      .mockResolvedValueOnce(response({ error: { code: "NOT_FOUND" } }, 404))
      .mockResolvedValueOnce(
        response({
          message: "The synthetic support inquiry was recorded.",
          reference: "S-20261120-003",
          submitted_at: "2026-11-20T12:15:00Z",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    renderInquiry();
    startForm();

    await openReview();
    fireEvent.click(screen.getByLabelText("I confirm this synthetic support inquiry."));
    fireEvent.click(screen.getByRole("button", { name: "Confirm support inquiry" }));
    await screen.findByRole("button", { name: "Check inquiry status" });
    fireEvent.click(screen.getByRole("button", { name: "Check inquiry status" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("not been confirmed");
    fireEvent.click(screen.getByRole("button", { name: "Retry inquiry safely" }));

    expect(await screen.findByText("Reference: S-20261120-003")).toBeInTheDocument();
    const firstSubmission = JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body));
    const retrySubmission = JSON.parse(String(fetchMock.mock.calls[3]?.[1]?.body));
    expect(retrySubmission.operation_id).toBe(firstSubmission.operation_id);
  });

  it("clears review state when the guest conversation is replaced", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(reviewResponse())));
    const view = render(
      <SupportInquiry
        key="guest-a"
        description="We can prepare a synthetic inquiry."
        title="Need support?"
      />,
    );
    startForm();
    await openReview();

    view.rerender(
      <SupportInquiry
        key="guest-b"
        description="We can prepare a synthetic inquiry."
        title="Need support?"
      />,
    );

    expect(screen.getByRole("button", { name: "Start support inquiry" })).toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });
});
