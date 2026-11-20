import type { components } from "./generated";

export type SessionBootstrapResponse = components["schemas"]["SessionBootstrapResponse"];

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

export async function bootstrapGuestSession(
  signal?: AbortSignal,
): Promise<SessionBootstrapResponse> {
  const response = await fetch(`${apiUrl()}/sessions`, {
    method: "POST",
    credentials: "include",
    signal,
  });

  if (!response.ok) {
    throw new ApiClientError("Unable to start a guest session.", response.status);
  }

  return (await response.json()) as SessionBootstrapResponse;
}
