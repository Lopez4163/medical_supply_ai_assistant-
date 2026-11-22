import type { components } from "./generated";

export type SessionBootstrapResponse = components["schemas"]["SessionBootstrapResponse"];
export type ConversationHistoryResponse = components["schemas"]["ConversationHistoryResponse"];
export type ConversationMessagePublic = components["schemas"]["ConversationMessagePublic"];
export type ChatTurnRequest = components["schemas"]["ChatTurnRequest"];
export type ChatTurnResponse = components["schemas"]["ChatTurnResponse"];
export type ProductCardPublic = components["schemas"]["ProductCardPublic"];
export type ProductDetailPublic = components["schemas"]["ProductDetailPublic"];
export type DraftQuoteResponse = components["schemas"]["DraftQuoteResponse"];
export type DraftQuotePublic = components["schemas"]["DraftQuotePublic"];
export type AddQuoteLineRequest = components["schemas"]["AddQuoteLineRequest"];
export type UpdateQuoteLineRequest = components["schemas"]["UpdateQuoteLineRequest"];
export type DeleteQuoteLineRequest = components["schemas"]["DeleteQuoteLineRequest"];
export type QuoteReviewRequest = components["schemas"]["QuoteReviewRequest"];
export type QuoteReviewPublic = components["schemas"]["QuoteReviewPublic"];
export type QuoteSubmitRequest = components["schemas"]["QuoteSubmitRequest"];
export type QuoteSubmissionPublic = components["schemas"]["QuoteSubmissionPublic"];
export type SupportReviewRequest = components["schemas"]["SupportReviewRequest"];
export type SupportReviewPublic = components["schemas"]["SupportReviewPublic"];
export type SupportSubmitRequest = components["schemas"]["SupportSubmitRequest"];
export type SupportInquiryPublic = components["schemas"]["SupportInquiryPublic"];

export class ApiClientError extends Error {
  public constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiClientError";
  }
}

function apiUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
}

async function requestJson<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetch(`${apiUrl()}${path}`, {
    credentials: "include",
    ...init,
  });

  if (!response.ok) {
    throw new ApiClientError("The API request could not be completed.", response.status);
  }

  return (await response.json()) as T;
}

export async function bootstrapGuestSession(
  signal?: AbortSignal,
): Promise<SessionBootstrapResponse> {
  return requestJson<SessionBootstrapResponse>("/sessions", {
    method: "POST",
    signal,
  });
}

export async function getCurrentConversation(
  signal?: AbortSignal,
): Promise<ConversationHistoryResponse> {
  return requestJson<ConversationHistoryResponse>("/conversations/current", {
    method: "GET",
    signal,
  });
}

export async function getProduct(sku: string, signal?: AbortSignal): Promise<ProductDetailPublic> {
  return requestJson<ProductDetailPublic>(`/products/${encodeURIComponent(sku)}`, {
    method: "GET",
    signal,
  });
}

export async function getDraftQuote(signal?: AbortSignal): Promise<DraftQuoteResponse> {
  return requestJson<DraftQuoteResponse>("/quotations/draft", { method: "GET", signal });
}

export async function addQuoteLine(request: AddQuoteLineRequest): Promise<DraftQuotePublic> {
  return requestJson<DraftQuotePublic>("/quotations/draft/lines", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export async function updateQuoteLine(
  lineId: string,
  request: UpdateQuoteLineRequest,
): Promise<DraftQuotePublic> {
  return requestJson<DraftQuotePublic>(`/quotations/draft/lines/${encodeURIComponent(lineId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export async function deleteQuoteLine(
  lineId: string,
  request: DeleteQuoteLineRequest,
): Promise<DraftQuotePublic> {
  return requestJson<DraftQuotePublic>(`/quotations/draft/lines/${encodeURIComponent(lineId)}`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export async function reviewQuote(request: QuoteReviewRequest): Promise<QuoteReviewPublic> {
  return requestJson<QuoteReviewPublic>("/quotations/draft/review", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export async function submitQuote(request: QuoteSubmitRequest): Promise<QuoteSubmissionPublic> {
  return requestJson<QuoteSubmissionPublic>("/quotations/submissions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export async function reconcileQuote(operationId: string): Promise<QuoteSubmissionPublic> {
  return requestJson<QuoteSubmissionPublic>(`/quotations/submissions/reconcile/${operationId}`, {
    method: "GET",
  });
}

export async function reviewSupport(request: SupportReviewRequest): Promise<SupportReviewPublic> {
  return requestJson<SupportReviewPublic>("/support/review", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export async function submitSupport(request: SupportSubmitRequest): Promise<SupportInquiryPublic> {
  return requestJson<SupportInquiryPublic>("/support/inquiries", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export async function reconcileSupport(operationId: string): Promise<SupportInquiryPublic> {
  return requestJson<SupportInquiryPublic>(`/support/inquiries/reconcile/${operationId}`, {
    method: "GET",
  });
}

export async function sendChatMessage(
  request: ChatTurnRequest,
  signal?: AbortSignal,
): Promise<ChatTurnResponse> {
  return requestJson<ChatTurnResponse>("/chat/messages", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal,
  });
}
