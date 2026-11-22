"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useMemo, useState } from "react";

import {
  ApiClientError,
  getCurrentConversation,
  sendChatMessage,
  type ConversationMessagePublic,
} from "@/lib/api/client";
import { queryKeys } from "@/lib/query/query-keys";

export type PendingChatMessage = {
  conversationId: string;
  clientMessageId: string;
  text: string;
  cursor?: string;
};

export type ChatRecoveryError = {
  conversationId: string;
  message: string;
  canRetry: boolean;
};

type UseChatOptions = {
  conversationId: string;
};

function createClientMessageId(): string {
  return crypto.randomUUID();
}

function appendCommittedMessages(
  messages: ConversationMessagePublic[],
  incoming: ConversationMessagePublic[],
): ConversationMessagePublic[] {
  const byId = new Map(messages.map((message) => [message.id, message]));
  for (const message of incoming) {
    byId.set(message.id, message);
  }
  return [...byId.values()].sort((left, right) => left.ordinal - right.ordinal);
}

function toRecoveryError(error: unknown, conversationId: string): ChatRecoveryError {
  if (error instanceof ApiClientError && error.status === 401) {
    return {
      conversationId,
      message: "Your guest session expired. Refresh to start a new session.",
      canRetry: false,
    };
  }
  if (error instanceof ApiClientError && [400, 422].includes(error.status)) {
    return {
      conversationId,
      message: "The message was not accepted. Edit it and send a new message.",
      canRetry: false,
    };
  }
  if (error instanceof ApiClientError && error.status === 403) {
    return {
      conversationId,
      message: "This message was blocked by a security check. Refresh before trying again.",
      canRetry: false,
    };
  }
  if (error instanceof ApiClientError && error.status === 404) {
    return {
      conversationId,
      message: "The conversation is unavailable. Refresh to restore your current session.",
      canRetry: false,
    };
  }
  if (error instanceof ApiClientError && error.status === 409) {
    return {
      conversationId,
      message: "The conversation changed. Refresh the conversation before sending another message.",
      canRetry: false,
    };
  }
  if (error instanceof ApiClientError && error.status === 503) {
    return {
      conversationId,
      message: "The chat service is unavailable. Try a new message later.",
      canRetry: false,
    };
  }
  return {
    conversationId,
    message:
      "We could not confirm whether your message was recorded. Retry safely to reconcile it.",
    canRetry: true,
  };
}

export function useChat({ conversationId }: UseChatOptions) {
  const queryClient = useQueryClient();
  const [pendingMessage, setPendingMessage] = useState<PendingChatMessage | null>(null);
  const [recoveryError, setRecoveryError] = useState<ChatRecoveryError | null>(null);
  const historyQuery = useQuery({
    queryKey: queryKeys.conversation(conversationId),
    queryFn: () => getCurrentConversation(),
    enabled: true,
  });

  const mutation = useMutation({
    mutationFn: (message: PendingChatMessage) =>
      sendChatMessage({
        client_message_id: message.clientMessageId,
        text: message.text,
        cursor: message.cursor,
      }),
    onSuccess: async (response, operation) => {
      queryClient.setQueryData(
        queryKeys.conversation(operation.conversationId),
        (current: { messages: ConversationMessagePublic[] } | undefined) => ({
          conversation_id: response.conversation_id,
          messages: appendCommittedMessages(current?.messages ?? [], [
            response.user_message,
            response.assistant_message,
          ]),
        }),
      );
      setPendingMessage(null);
      setRecoveryError(null);
      if (response.draft_changed) {
        await queryClient.invalidateQueries({ queryKey: queryKeys.draftQuote(conversationId) });
      }
    },
    onError: (error, operation) => {
      const recovery = toRecoveryError(error, operation.conversationId);
      if (!recovery.canRetry) {
        setPendingMessage(null);
      }
      setRecoveryError(recovery);
    },
  });

  const sendMessage = useCallback(
    (text: string, cursor?: string) => {
      const normalizedText = text.trim();
      if (!normalizedText || mutation.isPending || pendingMessage) {
        return;
      }
      const message = {
        conversationId,
        clientMessageId: createClientMessageId(),
        text: normalizedText,
        cursor,
      };
      setPendingMessage(message);
      setRecoveryError(null);
      mutation.mutate(message);
    },
    [conversationId, mutation, pendingMessage],
  );

  const retry = useCallback(() => {
    if (!pendingMessage || !recoveryError?.canRetry || mutation.isPending) {
      return;
    }
    setRecoveryError(null);
    mutation.mutate(pendingMessage);
  }, [mutation, pendingMessage, recoveryError]);

  const showMore = useCallback(
    (cursor: string) => {
      sendMessage("show more", cursor);
    },
    [sendMessage],
  );

  const messages = useMemo(() => historyQuery.data?.messages ?? [], [historyQuery.data]);
  return {
    messages,
    pendingMessage,
    isRestoring: historyQuery.isPending,
    restoreError: historyQuery.error ? toRecoveryError(historyQuery.error, conversationId) : null,
    isSending: mutation.isPending,
    recoveryError,
    sendMessage,
    showMore,
    retry,
    refreshHistory: historyQuery.refetch,
  };
}
