import type { SessionBootstrapState } from "@/features/session/use-session-bootstrap";

import { ChatComposer } from "./chat-composer";
import { MessageList } from "./message-list";
import { useChat } from "./use-chat";

type ChatInterfaceProps = {
  sessionState: SessionBootstrapState;
};

type ActiveChatProps = {
  conversationId: string;
};

function ActiveChat({ conversationId }: ActiveChatProps) {
  const chat = useChat({ conversationId });

  return (
    <>
      <section
        aria-live="polite"
        className="mx-auto flex w-full max-w-3xl flex-1 items-center px-4 py-8 sm:px-6"
      >
        {chat.isRestoring ? (
          <p role="status" className="text-sm text-slate-600">
            Restoring your conversation…
          </p>
        ) : null}
        {chat.restoreError ? (
          <div
            role="alert"
            className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-800"
          >
            <p>{chat.restoreError.message}</p>
            <button
              className="mt-2 underline"
              onClick={() => void chat.refreshHistory()}
              type="button"
            >
              Try restoring again
            </button>
          </div>
        ) : null}
        {!chat.isRestoring && !chat.restoreError ? (
          <MessageList messages={chat.messages} pendingMessage={chat.pendingMessage} />
        ) : null}
      </section>
      {chat.recoveryError ? (
        <div className="mx-auto w-full max-w-3xl px-4 pb-2">
          <div
            role="alert"
            className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800"
          >
            <p>{chat.recoveryError.message}</p>
            {chat.recoveryError.canRetry ? (
              <button
                className="mt-2 underline"
                disabled={chat.isSending}
                onClick={chat.retry}
                type="button"
              >
                Retry message
              </button>
            ) : null}
          </div>
        </div>
      ) : null}
      <ChatComposer
        disabled={chat.isRestoring || Boolean(chat.restoreError) || Boolean(chat.pendingMessage)}
        isSending={chat.isSending}
        onSend={chat.sendMessage}
      />
    </>
  );
}

export function ChatInterface({ sessionState }: ChatInterfaceProps) {
  return (
    <main aria-label="Conversation" className="flex min-h-0 flex-1 flex-col">
      {sessionState.status === "loading" ? (
        <section className="mx-auto flex w-full max-w-3xl flex-1 items-center px-4 py-8 sm:px-6">
          <p role="status" className="text-sm text-slate-600">
            Starting your guest session…
          </p>
        </section>
      ) : null}
      {sessionState.status === "error" ? (
        <>
          <section className="mx-auto flex w-full max-w-3xl flex-1 items-center px-4 py-8 sm:px-6">
            <p
              role="alert"
              className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-800"
            >
              {sessionState.message}
            </p>
          </section>
          <ChatComposer disabled isSending={false} onSend={() => undefined} />
        </>
      ) : null}
      {sessionState.status === "ready" ? (
        <ActiveChat
          key={sessionState.session.conversation_id}
          conversationId={sessionState.session.conversation_id}
        />
      ) : null}
    </main>
  );
}
