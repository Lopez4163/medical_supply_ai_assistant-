export function ChatComposer() {
  return (
    <form aria-label="Message composer" className="border-t border-slate-200 bg-white p-4">
      <label className="sr-only" htmlFor="chat-message">
        Message the AI Supply Assistant
      </label>
      <div className="mx-auto flex max-w-3xl gap-3">
        <textarea
          className="min-h-12 flex-1 resize-none rounded-md border border-slate-300 bg-slate-50 px-3 py-2 text-sm text-slate-700"
          disabled
          id="chat-message"
          placeholder="Chat sending will be available soon."
          rows={1}
        />
        <button
          className="rounded-md bg-sky-700 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-300"
          disabled
          type="submit"
        >
          Send
        </button>
      </div>
    </form>
  );
}
