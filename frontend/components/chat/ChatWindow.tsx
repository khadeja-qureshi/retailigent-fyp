"use client";

import {
  FormEvent,
  KeyboardEvent,
  useEffect,
  useRef,
  useState,
} from "react";

import MessageBubble from "@/components/chat/MessageBubble";

import {
  useChat,
} from "@/lib/useChat";


const SUGGESTIONS = [
  "Show me black kurtas",
  "Do you have the second one in stock?",
  "Add the first one to my cart",
  "Notify me if the first one gets 20% off",
];


export default function ChatWindow() {
  const {
    messages,
    conversationId,
    isSending,
    error,
    sendMessage,
    stop,
    newConversation,
  } = useChat();

  const [
    input,
    setInput,
  ] = useState("");

  const bottomRef =
    useRef<HTMLDivElement | null>(
      null
    );

  const textareaRef =
    useRef<HTMLTextAreaElement | null>(
      null
    );


  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "end",
    });
  }, [messages]);


  const hasStreamingAssistant =
    messages.some(
      (message) =>
        message.role ===
          "assistant" &&
        message.isStreaming
    );


  async function submitMessage(
    rawMessage: string
  ) {
    const message =
      rawMessage.trim();

    if (
      !message ||
      isSending
    ) {
      return;
    }

    setInput("");

    await sendMessage(
      message
    );

    textareaRef.current?.focus();
  }


  function handleSubmit(
    event: FormEvent
  ) {
    event.preventDefault();

    void submitMessage(
      input
    );
  }


  function handleKeyDown(
    event:
      KeyboardEvent<HTMLTextAreaElement>
  ) {
    if (
      event.key === "Enter" &&
      !event.shiftKey
    ) {
      event.preventDefault();

      void submitMessage(
        input
      );
    }
  }


  return (
    <main className="mx-auto flex min-h-[calc(100vh-5rem)] w-full max-w-6xl flex-col px-4 py-6 sm:px-6">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-neutral-800 pb-5">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-neutral-500">
            Retailigent
          </p>

          <h1 className="mt-1 text-2xl font-semibold">
            Shopping Assistant
          </h1>

          <p className="mt-1 text-sm text-neutral-400">
            Search products, check live
            stock, manage your cart and
            Smart Cart, or make a mock
            purchase through chat.
          </p>
        </div>

        <button
          type="button"
          disabled={isSending}
          onClick={() => {
            newConversation();

            setInput("");

            textareaRef.current?.focus();
          }}
          className="rounded-xl border border-neutral-700 px-4 py-2 text-sm text-neutral-300 transition hover:bg-neutral-900 disabled:cursor-not-allowed disabled:opacity-50"
        >
          New conversation
        </button>
      </header>


      <section className="flex-1 overflow-hidden">
        <div className="mx-auto flex min-h-[55vh] max-w-4xl flex-col py-6">
          {messages.length === 0 ? (
            <div className="my-auto py-12 text-center">
              <div className="mx-auto max-w-2xl">
                <h2 className="text-2xl font-semibold">
                  What are you looking
                  for today?
                </h2>

                <p className="mt-3 text-neutral-400">
                  You can speak naturally
                  in English, Roman Urdu,
                  or mix both.
                </p>

                <div className="mt-8 grid gap-3 sm:grid-cols-2">
                  {SUGGESTIONS.map(
                    (suggestion) => (
                      <button
                        key={suggestion}
                        type="button"
                        disabled={
                          isSending
                        }
                        onClick={() => {
                          void submitMessage(
                            suggestion
                          );
                        }}
                        className="rounded-2xl border border-neutral-800 bg-neutral-950 p-4 text-left text-sm text-neutral-300 transition hover:border-neutral-700 hover:bg-neutral-900 disabled:opacity-50"
                      >
                        {suggestion}
                      </button>
                    )
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-5">
              {messages.map(
                (message) => (
                  <MessageBubble
                    key={message.id}
                    message={message}
                  />
                )
              )}

              {isSending &&
                !hasStreamingAssistant && (
                  <div className="flex justify-start">
                    <div className="rounded-2xl rounded-bl-md border border-neutral-800 bg-neutral-950 px-4 py-3 text-sm text-neutral-400">
                      <span className="animate-pulse">
                        Retailigent is
                        working...
                      </span>
                    </div>
                  </div>
                )}
            </div>
          )}

          {error && (
            <div className="mt-5 rounded-xl border border-red-900 bg-red-950/30 px-4 py-3 text-sm text-red-300">
              {error}
            </div>
          )}

          <div
            ref={bottomRef}
            aria-hidden="true"
          />
        </div>
      </section>


      <div className="sticky bottom-0 border-t border-neutral-800 bg-black/95 py-4 backdrop-blur">
        <div className="mx-auto max-w-4xl">
          <form
            onSubmit={handleSubmit}
            className="rounded-2xl border border-neutral-700 bg-neutral-950 p-2"
          >
            <textarea
              ref={textareaRef}
              value={input}
              disabled={isSending}
              onChange={(event) => {
                setInput(
                  event.target.value
                );
              }}
              onKeyDown={
                handleKeyDown
              }
              rows={2}
              placeholder="Ask Retailigent anything..."
              className="min-h-14 w-full resize-none bg-transparent px-3 py-2 text-sm text-white outline-none placeholder:text-neutral-600 disabled:opacity-60"
            />

            <div className="flex items-center justify-between gap-3 px-2 pb-1">
              <div className="min-w-0">
                <p className="text-xs text-neutral-600">
                  Enter to send ·
                  Shift+Enter for a new
                  line
                </p>

                {conversationId && (
                  <p className="mt-1 truncate text-[10px] text-neutral-700">
                    Conversation:{" "}
                    {conversationId}
                  </p>
                )}
              </div>

              {isSending ? (
                <button
                  type="button"
                  onClick={stop}
                  className="shrink-0 rounded-xl border border-neutral-700 px-4 py-2 text-sm hover:bg-neutral-900"
                >
                  Stop
                </button>
              ) : (
                <button
                  type="submit"
                  disabled={
                    !input.trim()
                  }
                  className="shrink-0 rounded-xl bg-white px-5 py-2 text-sm font-medium text-black transition hover:bg-neutral-200 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Send
                </button>
              )}
            </div>
          </form>

          <p className="mt-2 text-center text-xs text-neutral-600">
            Stock, pricing and purchase
            results come from Retailigent
            backend services rather than
            being invented by the chat UI.
          </p>
        </div>
      </div>
    </main>
  );
}