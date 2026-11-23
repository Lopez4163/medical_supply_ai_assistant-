"use client";

import { AppShell } from "@/components/layout/app-shell";
import { useSessionBootstrap } from "@/features/session/use-session-bootstrap";

export default function HomePage() {
  return <AppShell sessionState={useSessionBootstrap()} />;
}
