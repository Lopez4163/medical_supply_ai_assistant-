import type { SessionBootstrapState } from "@/features/session/use-session-bootstrap";
import type { DraftQuoteController } from "@/features/quotation/use-draft-quote";

import { ChatComposer } from "./chat-composer";
import { MessageList } from "./message-list";
import { useChat } from "./use-chat";

type ChatInterfaceProps = {
  draftController?: DraftQuoteController;
  sessionState: SessionBootstrapState;
};

type ActiveChatProps = {
  conversationId: string;
  draftController?: DraftQuoteController;
};

function ActiveChat({ conversationId, draftController }: ActiveChatProps) {
  const chat = useChat({ conversationId });

  return (
    <>
      <section
        aria-busy={chat.isRestoring}
        className="mx-auto flex w-full max-w-3xl flex-1 items-start px-4 py-6 sm:px-6 sm:py-8"
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
          <MessageList
            conversationId={conversationId}
            messages={chat.messages}
            onShowMore={chat.showMore}
            pendingMessage={chat.pendingMessage}
            quotationController={draftController}
          />
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

export function ChatInterface({ draftController, sessionState }: ChatInterfaceProps) {
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
          draftController={draftController}
        />
      ) : null}
    </main>
  );
}
