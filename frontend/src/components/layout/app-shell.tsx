import type { SessionBootstrapState } from "@/features/session/use-session-bootstrap";

import { ChatInterface } from "@/features/chat/chat-interface";
import { QuotationDrawer } from "@/features/quotation/quotation-drawer";
import { useDraftQuote } from "@/features/quotation/use-draft-quote";

import { AppHeader } from "./app-header";

type AppShellProps = {
  sessionState: SessionBootstrapState;
};

export function AppShell({ sessionState }: AppShellProps) {
  if (sessionState.status === "ready") {
    return <ReadyAppShell key={sessionState.session.conversation_id} sessionState={sessionState} />;
  }
  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900">
      <AppHeader />
      <ChatInterface sessionState={sessionState} />
    </div>
  );
}

function ReadyAppShell({
  sessionState,
}: {
  sessionState: Extract<SessionBootstrapState, { status: "ready" }>;
}) {
  const conversationId = sessionState.session.conversation_id;
  const draftController = useDraftQuote(conversationId);

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900">
      <AppHeader quotationControl={<QuotationDrawer controller={draftController} />} />
      <ChatInterface draftController={draftController} sessionState={sessionState} />
    </div>
  );
}
