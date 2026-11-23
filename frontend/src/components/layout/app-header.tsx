import { DemoDisclosure } from "./demo-disclosure";

type AppHeaderProps = {
  quoteLineCount: number;
};

export function AppHeader({ quoteLineCount }: AppHeaderProps) {
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
        <button
          aria-label={`Quotation: ${quoteLineCount} line items`}
          className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm"
          disabled
          type="button"
        >
          Quotation <span aria-hidden="true">({quoteLineCount})</span>
        </button>
      </div>
    </header>
  );
}
