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

import type {
  ConversationSummary,
} from "@/lib/chat-types";


const SUGGESTIONS = [
  "Show me black kurtas",
  "Do you have the second one in stock?",
  "Add the first one to my cart",
  "Notify me if the first one gets 20% off",
];


function conversationLabel(
  conversation:
    ConversationSummary
) {
  const title =
    conversation
      .title
      ?.trim();

  if (title) {
    return title;
  }

  return (
    "Untitled conversation"
  );
}


function conversationDate(
  value:
    | string
    | null
    | undefined
) {
  if (!value) {
    return "";
  }

  const date =
    new Date(
      value
    );

  if (
    Number.isNaN(
      date.getTime()
    )
  ) {
    return "";
  }

  return (
    date.toLocaleDateString(
      undefined,
      {
        month:
          "short",

        day:
          "numeric",
      }
    )
  );
}


export default function ChatWindow() {
  const {
    messages,

    conversationId,

    conversations,

    isSending,

    isHistoryLoading,

    error,

    sendMessage,

    stop,

    newConversation,

    loadConversation,
  } =
    useChat();


  const [
    input,
    setInput,
  ] =
    useState("");


  const bottomRef =
    useRef<
      HTMLDivElement
      | null
    >(null);


  const textareaRef =
    useRef<
      HTMLTextAreaElement
      | null
    >(null);


  useEffect(() => {
    bottomRef.current
      ?.scrollIntoView({
        behavior:
          "smooth",

        block:
          "end",
      });
  }, [
    messages,
  ]);


  const hasStreamingAssistant =
    messages.some(
      (
        message
      ) =>
        message.role
        === "assistant"
        &&
        message
          .isStreaming
    );


  const isBusy =
    isSending
    ||
    isHistoryLoading;


  async function submitMessage(
    rawMessage: string
  ) {
    const message =
      rawMessage.trim();

    if (
      !message
      ||
      isBusy
    ) {
      return;
    }

    setInput("");

    await (
      sendMessage(
        message
      )
    );

    textareaRef.current
      ?.focus();
  }


  function handleSubmit(
    event:
      FormEvent
  ) {
    event.preventDefault();

    void (
      submitMessage(
        input
      )
    );
  }


  function handleKeyDown(
    event:
      KeyboardEvent<
        HTMLTextAreaElement
      >
  ) {
    if (
      event.key
      === "Enter"
      &&
      !event.shiftKey
    ) {
      event.preventDefault();

      void (
        submitMessage(
          input
        )
      );
    }
  }


  return (
    <main className="retailigent-chat min-h-[calc(100vh-3.5rem)] bg-[#f1e6de] text-[#2c1c20]">
      <div className="mx-auto flex w-full max-w-[1500px] flex-col lg:min-h-[calc(100vh-3.5rem)] lg:flex-row">

        <aside className="border-b border-[#6a2232] bg-[#7f2a3c] text-[#f1e6de] lg:w-72 lg:shrink-0 lg:border-b-0 lg:border-r">
          <div className="p-4 lg:sticky lg:top-0 lg:max-h-[calc(100vh-3.5rem)] lg:overflow-y-auto">
            <button
              type="button"
              disabled={
                isBusy
              }
              onClick={() => {
                void (
                  newConversation()
                  .then(
                    (
                      success
                    ) => {
                      if (
                        success
                      ) {
                        setInput(
                          ""
                        );
                      }

                      textareaRef
                        .current
                        ?.focus();
                    }
                  )
                );
              }}
              className="w-full rounded-xl bg-[#ce4d42] px-4 py-3 text-left text-sm font-semibold text-white shadow-sm transition hover:bg-[#ad3d34] disabled:cursor-not-allowed disabled:opacity-50"
            >
              + New conversation
            </button>

            <div className="mt-6">
              <p className="px-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#e9d0c8]">
                Recent conversations
              </p>

              {
                isHistoryLoading
                ? (
                  <p className="px-2 py-4 text-sm text-[#e9d0c8]">
                    Loading...
                  </p>
                )
                : (
                  <div className="mt-2 space-y-1">
                    {
                      conversations
                        .length
                      === 0
                        ? (
                          <p className="px-2 py-4 text-sm text-[#e9d0c8]">
                            Your previous chats will appear here.
                          </p>
                        )
                        : (
                          conversations
                            .map(
                              (
                                conversation
                              ) => {
                                const active =
                                  conversation
                                    .id
                                  ===
                                  conversationId;

                                return (
                                  <button
                                    key={
                                      conversation
                                        .id
                                    }
                                    type="button"
                                    disabled={
                                      isBusy
                                    }
                                    onClick={() => {
                                      void (
                                        loadConversation(
                                          conversation
                                            .id
                                        )
                                      );
                                    }}
                                    className={
                                      (
                                        "w-full rounded-xl "
                                        + "px-3 py-2.5 "
                                        + "text-left transition "
                                      )
                                      +
                                      (
                                        active
                                          ? (
                                            "bg-[#7779de] text-white shadow-sm "
                                            + "text-white"
                                          )
                                          : (
                                            "text-[#f1e6de] "
                                            + "hover:bg-white/10"
                                          )
                                      )
                                    }
                                  >
                                    <div className="truncate text-sm font-medium">
                                      {
                                        conversationLabel(
                                          conversation
                                        )
                                      }
                                    </div>

                                    <div className="mt-1 text-[11px] text-[#e4c9c1]">
                                      {
                                        conversationDate(
                                          conversation
                                            .updated_at
                                          ??
                                          conversation
                                            .created_at
                                        )
                                      }
                                    </div>
                                  </button>
                                );
                              }
                            )
                        )
                    }
                  </div>
                )
              }
            </div>
          </div>
        </aside>


        <section className="flex min-w-0 flex-1 flex-col">
          <header className="border-b border-[#dccbc4] bg-[#fffaf7]/90 px-5 py-5 backdrop-blur sm:px-8">
            <div className="mx-auto max-w-5xl">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[#7f2a3c]">
                Retailigent
              </p>

              <h1 className="mt-1 text-2xl font-bold text-[#2c1c20] sm:text-3xl">
                Shopping Assistant
              </h1>

              <p className="mt-2 max-w-3xl text-sm leading-6 text-[#756369]">
                Search products, check live stock,
                manage your cart and Smart Cart,
                or complete a mock purchase using
                natural language.
              </p>
            </div>
          </header>


          <section className="flex-1 px-4 sm:px-8">
            <div className="mx-auto flex min-h-[55vh] max-w-5xl flex-col py-6">
              {
                messages.length
                === 0
                  ? (
                    <div className="my-auto py-12 text-center">
                      <div className="mx-auto max-w-2xl">
                        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-[#7f2a3c] text-lg font-bold text-[#f1e6de] shadow-sm">
                          R
                        </div>

                        <h2 className="mt-5 text-2xl font-bold">
                          What are you looking for today?
                        </h2>

                        <p className="mt-3 text-[#756369]">
                          Speak naturally in English,
                          Roman Urdu, or mix both.
                        </p>

                        <div className="mt-8 grid gap-3 sm:grid-cols-2">
                          {
                            SUGGESTIONS
                              .map(
                                (
                                  suggestion
                                ) => (
                                  <button
                                    key={
                                      suggestion
                                    }
                                    type="button"
                                    disabled={
                                      isBusy
                                    }
                                    onClick={() => {
                                      void (
                                        submitMessage(
                                          suggestion
                                        )
                                      );
                                    }}
                                    className="rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-4 text-left text-sm text-[#2c1c20] shadow-sm transition hover:-translate-y-0.5 hover:border-[#ce4d42] hover:shadow-md disabled:opacity-50"
                                  >
                                    {
                                      suggestion
                                    }
                                  </button>
                                )
                              )
                          }
                        </div>
                      </div>
                    </div>
                  )
                  : (
                    <div className="space-y-5">
                      {
                        messages.map(
                          (
                            message
                          ) => (
                            <MessageBubble
                              key={
                                message.id
                              }
                              message={
                                message
                              }
                            />
                          )
                        )
                      }

                      {
                        isSending
                        &&
                        !hasStreamingAssistant
                        && (
                          <div className="flex justify-start">
                            <div className="rounded-2xl rounded-bl-md border border-[#dccbc4] bg-[#fffaf7] px-4 py-3 text-sm text-[#756369] shadow-sm">
                              <span className="animate-pulse">
                                Retailigent is working...
                              </span>
                            </div>
                          </div>
                        )
                      }
                    </div>
                  )
              }


              {
                error
                && (
                  <div className="mt-5 rounded-xl border border-[#e4aaa3] bg-[#fff2ef] px-4 py-3 text-sm text-[#9b352e]">
                    {
                      error
                    }
                  </div>
                )
              }


              <div
                ref={
                  bottomRef
                }
                aria-hidden="true"
              />
            </div>
          </section>


          <div className="sticky bottom-0 border-t border-[#dccbc4] bg-[#f1e6de]/95 px-4 py-4 backdrop-blur sm:px-8">
            <div className="mx-auto max-w-5xl">
              <form
                onSubmit={
                  handleSubmit
                }
                className="rounded-2xl border border-[#d4c0b8] bg-[#fffaf7] p-2 shadow-lg shadow-[#7f2a3c]/5"
              >
                <textarea
                  ref={
                    textareaRef
                  }
                  value={
                    input
                  }
                  disabled={
                    isBusy
                  }
                  onChange={(
                    event
                  ) => {
                    setInput(
                      event
                        .target
                        .value
                    );
                  }}
                  onKeyDown={
                    handleKeyDown
                  }
                  rows={2}
                  placeholder="Ask Retailigent anything..."
                  className="min-h-14 w-full resize-none bg-transparent px-3 py-2 text-sm text-[#2c1c20] outline-none placeholder:text-[#a28e93] disabled:opacity-60"
                />

                <div className="flex items-center justify-between gap-3 px-2 pb-1">
                  <div className="min-w-0">
                    <p className="text-xs text-[#8c777c]">
                      Enter to send · Shift+Enter for a new line
                    </p>

                    {
                      conversationId
                      && (
                        <p className="mt-1 truncate text-[10px] text-[#ad999e]">
                          Conversation:{" "}
                          {
                            conversationId
                          }
                        </p>
                      )
                    }
                  </div>

                  {
                    isSending
                      ? (
                        <button
                          type="button"
                          onClick={
                            stop
                          }
                          className="shrink-0 rounded-xl border border-[#7f2a3c] px-4 py-2 text-sm font-medium text-[#7f2a3c] transition hover:bg-[#f5e8e5]"
                        >
                          Stop
                        </button>
                      )
                      : (
                        <button
                          type="submit"
                          disabled={
                            !input.trim()
                            ||
                            isHistoryLoading
                          }
                          className="shrink-0 rounded-xl bg-[#ce4d42] px-5 py-2 text-sm font-semibold text-white transition hover:bg-[#ad3d34] disabled:cursor-not-allowed disabled:opacity-40"
                        >
                          Send
                        </button>
                      )
                  }
                </div>
              </form>

              <p className="mt-2 text-center text-xs text-[#8c777c]">
                Product, stock, pricing and purchase
                results are validated by Retailigent
                backend services.
              </p>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}