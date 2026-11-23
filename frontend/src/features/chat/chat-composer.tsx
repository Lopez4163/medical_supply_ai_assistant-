import { FormEvent, KeyboardEvent, useState } from "react";

type ChatComposerProps = {
  disabled: boolean;
  isSending: boolean;
  onSend: (text: string) => void;
};

export function ChatComposer({ disabled, isSending, onSend }: ChatComposerProps) {
  const [text, setText] = useState("");

  function submit(): void {
    if (!text.trim() || disabled || isSending) {
      return;
    }
    onSend(text);
    setText("");
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    submit();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>): void {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <form
      aria-label="Message composer"
      className="border-t border-slate-200 bg-white p-4"
      onSubmit={handleSubmit}
    >
      <label className="sr-only" htmlFor="chat-message">
        Message the AI Supply Assistant
      </label>
      <div className="mx-auto flex max-w-3xl gap-3">
        <textarea
          className="min-h-12 flex-1 resize-none rounded-md border border-slate-300 bg-slate-50 px-3 py-2 text-sm text-slate-700"
          disabled={disabled || isSending}
          id="chat-message"
          onChange={(event) => setText(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about synthetic medical supplies…"
          rows={1}
          value={text}
        />
        <button
          className="rounded-md bg-sky-700 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-300"
          disabled={disabled || isSending || !text.trim()}
          type="submit"
        >
          {isSending ? "Sending…" : "Send"}
        </button>
      </div>
    </form>
  );
}
