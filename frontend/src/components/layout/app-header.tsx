import type { ReactNode } from "react";

import { DemoDisclosure } from "./demo-disclosure";

type AppHeaderProps = {
  quotationControl?: ReactNode;
};

export function AppHeader({ quotationControl }: AppHeaderProps) {
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-4 px-4 py-4 sm:px-6">
        <div>
          <p className="font-semibold tracking-tight text-sky-800">BioMedicHospicare</p>
          <h1 className="text-sm text-slate-700">AI Supply Assistant</h1>
        </div>
        <div className="max-w-sm text-right">
          <DemoDisclosure />
        </div>
        {quotationControl}
      </div>
    </header>
  );
}
