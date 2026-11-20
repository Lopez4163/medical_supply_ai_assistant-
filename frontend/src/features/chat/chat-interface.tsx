import type { SessionBootstrapState } from "@/features/session/use-session-bootstrap";

import { ChatComposer } from "./chat-composer";

type ChatInterfaceProps = {
  sessionState: SessionBootstrapState;
};

export function ChatInterface({ sessionState }: ChatInterfaceProps) {
  return (
    <main aria-label="Conversation" className="flex min-h-0 flex-1 flex-col">
      <section
        aria-live="polite"
        className="mx-auto flex w-full max-w-3xl flex-1 items-center px-4 py-8 sm:px-6"
      >
        {sessionState.status === "loading" ? (
          <p role="status" className="text-sm text-slate-600">
            Starting your guest session…
          </p>
        ) : null}
        {sessionState.status === "error" ? (
          <p
            role="alert"
            className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-800"
          >
            {sessionState.message}
          </p>
        ) : null}
        {sessionState.status === "ready" ? (
          <article className="max-w-xl rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-sm font-medium text-sky-800">AI Supply Assistant</p>
            <p className="mt-2 leading-7 text-slate-800">{sessionState.session.welcome_message}</p>
            <p className="mt-3 text-sm text-slate-500">
              {sessionState.session.restored
                ? "Your guest session was restored."
                : "Your guest session is ready."}
            </p>
          </article>
        ) : null}
      </section>
      <ChatComposer />
    </main>
  );
}
