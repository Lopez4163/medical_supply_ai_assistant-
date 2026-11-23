"use client";

import { useEffect, useState } from "react";

import {
  ApiClientError,
  bootstrapGuestSession,
  type SessionBootstrapResponse,
} from "@/lib/api/client";

export type SessionBootstrapState =
  | { status: "loading" }
  | { status: "ready"; session: SessionBootstrapResponse }
  | { status: "error"; message: string };

export function useSessionBootstrap(): SessionBootstrapState {
  const [state, setState] = useState<SessionBootstrapState>({ status: "loading" });

  useEffect(() => {
    const controller = new AbortController();

    void bootstrapGuestSession(controller.signal)
      .then((session) => setState({ status: "ready", session }))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        setState({
          status: "error",
          message:
            error instanceof ApiClientError && error.status === 401
              ? "Your guest session expired. Refresh to start a new session."
              : "We could not start a guest session. Refresh to try again.",
        });
      });

    return () => controller.abort();
  }, []);

  return state;
}
