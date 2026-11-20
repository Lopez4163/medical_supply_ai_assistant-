import type { components } from "./generated";

export type SessionBootstrapResponse = components["schemas"]["SessionBootstrapResponse"];
export type ConversationHistoryResponse = components["schemas"]["ConversationHistoryResponse"];
export type ConversationMessagePublic = components["schemas"]["ConversationMessagePublic"];
export type ChatTurnRequest = components["schemas"]["ChatTurnRequest"];
export type ChatTurnResponse = components["schemas"]["ChatTurnResponse"];

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
