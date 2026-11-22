import { useEffect, useRef } from "react";

import type { ConversationMessagePublic } from "@/lib/api/client";
import type { DraftQuoteController } from "@/features/quotation/use-draft-quote";

import { StructuredElements } from "./structured-elements";
import type { PendingChatMessage } from "./use-chat";

type MessageListProps = {
  conversationId: string;
  messages: ConversationMessagePublic[];
  pendingMessage: PendingChatMessage | null;
  onShowMore: (cursor: string) => void;
  quotationController?: DraftQuoteController;
};

function timestamp(value: string): string {
  return new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }).format(
    new Date(value),
  );
}

export function MessageList({
  conversationId,
  messages,
  onShowMore,
  pendingMessage,
  quotationController,
}: MessageListProps) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: "end" });
  }, [messages, pendingMessage]);

  return (
    <div
      aria-label="Conversation messages"
      aria-live="polite"
      aria-relevant="additions text"
      className="mx-auto w-full max-w-3xl space-y-4"
      role="log"
    >
      {messages.map((message) => (
        <article
          aria-label={`${message.role} message`}
          className={
            message.role === "user"
              ? "ml-auto max-w-xl rounded-xl bg-sky-700 p-4 text-white"
              : "max-w-xl rounded-xl border border-slate-200 bg-white p-4 text-slate-800 shadow-sm"
          }
          key={message.id}
        >
          <p className="whitespace-pre-wrap leading-7">{message.text}</p>
          {message.role === "assistant" ? (
            <StructuredElements
              conversationId={conversationId}
              elements={message.elements}
              onShowMore={onShowMore}
              quotationController={quotationController}
            />
          ) : null}
          <time
            aria-label={`Sent at ${timestamp(message.created_at)}`}
            className={
              message.role === "user"
                ? "mt-2 block text-xs text-sky-100"
                : "mt-2 block text-xs text-slate-500"
            }
            dateTime={message.created_at}
          >
            {timestamp(message.created_at)}
          </time>
        </article>
      ))}
      {pendingMessage ? (
        <article
          aria-label="user message sending"
          className="ml-auto max-w-xl rounded-xl bg-sky-700 p-4 text-white"
        >
          <p className="whitespace-pre-wrap leading-7">{pendingMessage.text}</p>
          <p className="mt-2 text-xs text-sky-100">Sending…</p>
        </article>
      ) : null}
      <div ref={endRef} />
    </div>
  );
}
