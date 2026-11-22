export const queryKeys = {
  conversation: (conversationId: string) => ["conversation", conversationId] as const,
  product: (conversationId: string, sku: string) => ["product", conversationId, sku] as const,
  draftQuote: (conversationId: string) => ["draft-quote", conversationId] as const,
};
