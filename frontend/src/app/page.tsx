export default function HomePage() {
  return (
    <main className="min-h-screen bg-slate-50 px-6 py-16 text-slate-900 sm:px-10">
      <section className="mx-auto max-w-2xl rounded-2xl border border-slate-200 bg-white p-8 shadow-sm sm:p-12">
        <p className="text-sm font-semibold tracking-wide text-sky-700">BioMedicHospicare</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">
          AI Supply Assistant
        </h1>
        <p className="mt-5 text-lg leading-8 text-slate-700">
          A thoughtful assistant experience for exploring medical-supply inquiries is being
          prepared.
        </p>
        <p className="mt-6 rounded-lg bg-sky-50 p-4 text-sm leading-6 text-slate-700">
          This is a Queens Tech Bros synthetic-data portfolio demonstration. It does not process
          payments, create commercial orders, or connect inquiries to real business operations.
        </p>
      </section>
    </main>
  );
}
