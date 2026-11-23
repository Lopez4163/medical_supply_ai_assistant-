export const queryKeys = {
  conversation: (conversationId: string) => ["conversation", conversationId] as const,
  draftQuote: () => ["draft-quote"] as const,
};
