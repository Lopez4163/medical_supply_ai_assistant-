"use client";

import { useCallback, useState } from "react";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  ApiClientError,
  addQuoteLine,
  deleteQuoteLine,
  getDraftQuote,
  updateQuoteLine,
  type AddQuoteLineRequest,
  type DeleteQuoteLineRequest,
  type DraftQuotePublic,
  type UpdateQuoteLineRequest,
} from "@/lib/api/client";
import { queryKeys } from "@/lib/query/query-keys";

type DraftOperation =
  | { kind: "add"; request: AddQuoteLineRequest }
  | { kind: "update"; lineId: string; request: UpdateQuoteLineRequest }
  | { kind: "remove"; lineId: string; request: DeleteQuoteLineRequest };

function isDefiniteFailure(error: unknown): boolean {
  return error instanceof ApiClientError && [400, 401, 403, 404, 409, 422].includes(error.status);
}

export function useDraftQuote(conversationId: string) {
  const queryClient = useQueryClient();
  const key = queryKeys.draftQuote(conversationId);
  const [retryOperation, setRetryOperation] = useState<DraftOperation | null>(null);
  const draftQuery = useQuery({
    queryKey: key,
    queryFn: ({ signal }) => getDraftQuote(signal),
  });
  const refreshDraft = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: key });
  }, [key, queryClient]);
  const mutation = useMutation({
    mutationFn: async (operation: DraftOperation): Promise<DraftQuotePublic> => {
      switch (operation.kind) {
        case "add":
          return addQuoteLine(operation.request);
        case "update":
          return updateQuoteLine(operation.lineId, operation.request);
        case "remove":
          return deleteQuoteLine(operation.lineId, operation.request);
      }
    },
    onSuccess: async (draft) => {
      setRetryOperation(null);
      queryClient.setQueryData(key, { draft });
      await refreshDraft();
    },
    onError: (error, operation) => {
      if (error instanceof ApiClientError && error.status === 409) {
        void refreshDraft();
      }
      setRetryOperation(isDefiniteFailure(error) ? null : operation);
    },
  });
  const expectedVersion = draftQuery.data?.draft?.version ?? 0;
  const addLine = useCallback(
    (sku: string, quantity: number) => {
      if (draftQuery.isPending || !draftQuery.data) return;
      mutation.mutate({
        kind: "add",
        request: {
          expected_version: expectedVersion,
          operation_id: crypto.randomUUID(),
          quantity,
          sku,
        },
      });
    },
    [draftQuery.data, draftQuery.isPending, expectedVersion, mutation],
  );
  const updateLine = useCallback(
    (lineId: string, quantity: number) => {
      mutation.mutate({
        kind: "update",
        lineId,
        request: {
          expected_version: expectedVersion,
          mode: "replace",
          operation_id: crypto.randomUUID(),
          quantity,
        },
      });
    },
    [expectedVersion, mutation],
  );
  const removeLine = useCallback(
    (lineId: string) => {
      mutation.mutate({
        kind: "remove",
        lineId,
        request: { expected_version: expectedVersion, operation_id: crypto.randomUUID() },
      });
    },
    [expectedVersion, mutation],
  );
  const retryLastOperation = useCallback(() => {
    if (retryOperation) mutation.mutate(retryOperation);
  }, [mutation, retryOperation]);

  return {
    addLine,
    draft: draftQuery.data?.draft ?? null,
    draftQuery,
    error: mutation.error,
    isPending: draftQuery.isPending || mutation.isPending,
    refreshDraft,
    removeLine,
    retryLastOperation,
    retryOperation,
    updateLine,
  };
}

export type DraftQuoteController = ReturnType<typeof useDraftQuote>;
