import type { ReactNode } from "react";

import { DemoDisclosure } from "./demo-disclosure";

type AppHeaderProps = {
  quotationControl?: ReactNode;
};

export function AppHeader({ quotationControl }: AppHeaderProps) {
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-5xl flex-col gap-3 px-4 py-4 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between sm:gap-4 sm:px-6">
        <div className="flex-1">
          <p className="font-semibold tracking-tight text-sky-800">BioMedicHospicare</p>
          <h1 className="text-sm text-slate-700">AI Supply Assistant</h1>
        </div>
        <div className="order-3 max-w-sm text-left sm:order-none sm:text-right">
          <DemoDisclosure />
        </div>
        {quotationControl}
      </div>
    </header>
  );
}
