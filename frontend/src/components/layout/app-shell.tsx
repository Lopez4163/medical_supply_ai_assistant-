import type { SessionBootstrapState } from "@/features/session/use-session-bootstrap";

import { ChatInterface } from "@/features/chat/chat-interface";

import { AppHeader } from "./app-header";

type AppShellProps = {
  sessionState: SessionBootstrapState;
};

export function AppShell({ sessionState }: AppShellProps) {
  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900">
      <AppHeader quoteLineCount={0} />
      <ChatInterface sessionState={sessionState} />
    </div>
  );
}
