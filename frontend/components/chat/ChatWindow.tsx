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

  return "Untitled conversation";
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

  return date.toLocaleDateString(
    undefined,
    {
      month:
        "short",

      day:
        "numeric",
    }
  );
}


interface ConversationHistoryProps {
  conversations:
    ConversationSummary[];

  conversationId:
    string | null;

  isBusy:
    boolean;

  isHistoryLoading:
    boolean;

  onNew:
    () => void;

  onSelect:
    (
      conversationId: string
    ) => void;

  onClose?:
    () => void;
}


function ConversationHistory({
  conversations,
  conversationId,
  isBusy,
  isHistoryLoading,
  onNew,
  onSelect,
  onClose,
}: ConversationHistoryProps) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-white/60">
          Conversations
        </p>

        {
          onClose
          && (
            <button
              type="button"
              onClick={
                onClose
              }
              aria-label="Close conversation history"
              className="flex h-9 w-9 items-center justify-center rounded-xl text-white/80 transition hover:bg-white/10 hover:text-white lg:hidden"
            >
              <svg
                viewBox="0 0 24 24"
                aria-hidden="true"
                className="h-5 w-5"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path
                  strokeLinecap="round"
                  d="M6 6l12 12M18 6L6 18"
                />
              </svg>
            </button>
          )
        }
      </div>


      <button
        type="button"
        disabled={
          isBusy
        }
        onClick={
          onNew
        }
        className="mt-4 w-full rounded-xl bg-[#ce4d42] px-4 py-3 text-left text-sm font-semibold text-white shadow-sm transition hover:bg-[#ad3d34] disabled:cursor-not-allowed disabled:opacity-50"
      >
        + New conversation
      </button>


      <div className="mt-6 min-h-0 flex-1">
        <p className="px-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-white/55">
          Recent conversations
        </p>

        {
          isHistoryLoading
            ? (
              <p className="px-2 py-4 text-sm text-white/60">
                Loading...
              </p>
            )
            : (
              <div className="mt-2 space-y-1">
                {
                  conversations.length
                  === 0
                    ? (
                      <p className="px-2 py-4 text-sm leading-6 text-white/60">
                        Your previous chats will appear here.
                      </p>
                    )
                    : (
                      conversations.map(
                        (
                          conversation
                        ) => {
                          const active =
                            conversation.id
                            ===
                            conversationId;

                          return (
                            <button
                              key={
                                conversation.id
                              }
                              type="button"
                              disabled={
                                isBusy
                              }
                              onClick={() => {
                                onSelect(
                                  conversation.id
                                );
                              }}
                              className={
                                (
                                  "w-full rounded-xl "
                                  +
                                  "px-3 py-3 "
                                  +
                                  "text-left transition "
                                )
                                +
                                (
                                  active
                                    ? (
                                      "bg-[#7779de] "
                                      +
                                      "text-white "
                                      +
                                      "shadow-sm"
                                    )
                                    : (
                                      "text-white/85 "
                                      +
                                      "hover:bg-white/10"
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

                              <div className="mt-1 text-[11px] text-white/55">
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
  );
}


export default function ChatWindow() {
  const {
    messages,

    conversationId,

    conversations,

    isSending,

    isHistoryLoading,

    isRestoringConversation,

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


  const [
    historyOpen,
    setHistoryOpen,
  ] =
    useState(false);


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


  useEffect(() => {
    if (!historyOpen) {
      return;
    }

    const previousOverflow =
      document.body.style.overflow;

    document.body.style.overflow =
      "hidden";


    return () => {
      document.body.style.overflow =
        previousOverflow;
    };
  }, [
    historyOpen,
  ]);


  const hasStreamingAssistant =
    messages.some(
      (
        message
      ) =>
        message.role
        === "assistant"
        &&
        message.isStreaming
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

    await sendMessage(
      message
    );

    textareaRef.current
      ?.focus();
  }


  async function handleNewConversation() {
    const success =
      await newConversation();

    if (success) {
      setInput("");
      setHistoryOpen(false);
    }

    textareaRef.current
      ?.focus();
  }


  async function handleLoadConversation(
    selectedConversationId:
      string
  ) {
    await loadConversation(
      selectedConversationId
    );

    setHistoryOpen(false);
  }


  function handleSubmit(
    event:
      FormEvent
  ) {
    event.preventDefault();

    void submitMessage(
      input
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

      void submitMessage(
        input
      );
    }
  }


  return (
    <main className="retailigent-chat min-h-[calc(100dvh-4rem)] overflow-x-hidden bg-[#f1e6de] text-[#2c1c20]">
      <div className="mx-auto flex min-h-[calc(100dvh-4rem)] w-full max-w-[1500px]">

        <aside className="hidden w-72 shrink-0 border-r border-white/10 bg-[#7f2a3c] text-[#f1e6de] lg:block">
          <div className="sticky top-16 h-[calc(100dvh-4rem)] overflow-y-auto p-4">
            <ConversationHistory
              conversations={
                conversations
              }
              conversationId={
                conversationId
              }
              isBusy={
                isBusy
              }
              isHistoryLoading={
                isHistoryLoading
              }
              onNew={() => {
                void handleNewConversation();
              }}
              onSelect={(
                selectedConversationId
              ) => {
                void handleLoadConversation(
                  selectedConversationId
                );
              }}
            />
          </div>
        </aside>


        {
          historyOpen
          && (
            <div className="fixed inset-x-0 bottom-0 top-16 z-40 lg:hidden">
              <button
                type="button"
                aria-label="Close conversation history"
                onClick={() => {
                  setHistoryOpen(
                    false
                  );
                }}
                className="absolute inset-0 bg-black/40 backdrop-blur-[2px]"
              />

              <aside className="relative h-full w-[min(88vw,22rem)] overflow-y-auto bg-[#7f2a3c] p-4 text-[#f1e6de] shadow-2xl">
                <ConversationHistory
                  conversations={
                    conversations
                  }
                  conversationId={
                    conversationId
                  }
                  isBusy={
                    isBusy
                  }
                  isHistoryLoading={
                    isHistoryLoading
                  }
                  onNew={() => {
                    void handleNewConversation();
                  }}
                  onSelect={(
                    selectedConversationId
                  ) => {
                    void handleLoadConversation(
                      selectedConversationId
                    );
                  }}
                  onClose={() => {
                    setHistoryOpen(
                      false
                    );
                  }}
                />
              </aside>
            </div>
          )
        }


        <section className="flex min-w-0 flex-1 flex-col">
          <header className="border-b border-[#dccbc4] bg-[#fffaf7]/90 px-4 py-4 backdrop-blur sm:px-6 sm:py-5 lg:px-8">
            <div className="mx-auto max-w-5xl">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#7f2a3c] sm:text-xs">
                    Retailigent
                  </p>

                  <h1 className="mt-1 text-2xl font-bold text-[#2c1c20] sm:text-3xl">
                    Shopping Assistant
                  </h1>
                </div>


                <div className="flex shrink-0 items-center gap-2 lg:hidden">
                  <button
                    type="button"
                    onClick={() => {
                      setHistoryOpen(
                        true
                      );
                    }}
                    className="flex min-h-11 items-center gap-2 rounded-xl border border-[#dccbc4] bg-white px-3 text-sm font-medium text-[#2c1c20] shadow-sm"
                  >
                    <svg
                      viewBox="0 0 24 24"
                      aria-hidden="true"
                      className="h-4 w-4"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.8"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M4 6h16M4 12h10M4 18h7"
                      />
                    </svg>

                    <span className="hidden min-[400px]:inline">
                      Chats
                    </span>
                  </button>

                  <button
                    type="button"
                    disabled={
                      isBusy
                    }
                    onClick={() => {
                      void handleNewConversation();
                    }}
                    aria-label="New conversation"
                    className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#ce4d42] text-xl font-medium text-white shadow-sm transition hover:bg-[#ad3d34] disabled:opacity-50"
                  >
                    +
                  </button>
                </div>
              </div>


              <p className="mt-2 hidden max-w-3xl text-sm leading-6 text-[#756369] sm:block">
                Search products, check live stock,
                manage your cart and Smart Cart,
                or complete a mock purchase using
                natural language.
              </p>
            </div>
          </header>


          <section className="min-h-0 flex-1 px-3 sm:px-6 lg:px-8">
            <div className="mx-auto flex min-h-[50vh] max-w-5xl flex-col py-4 sm:py-6">
              {
                isRestoringConversation
                  ? (
                    <div className="my-auto py-12 text-center text-sm text-[#ad999e]">
                      Restoring your conversation...
                    </div>
                  )
                  : messages.length === 0
                  ? (
                    <div className="my-auto py-8 text-center sm:py-12">
                      <div className="mx-auto max-w-2xl">
                        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-[#7f2a3c] text-lg font-bold text-[#f1e6de] shadow-sm">
                          R
                        </div>

                        <h2 className="mt-5 text-xl font-bold sm:text-2xl">
                          What are you looking for today?
                        </h2>

                        <p className="mt-3 text-sm leading-6 text-[#756369] sm:text-base">
                          Speak naturally in English,
                          Roman Urdu, or mix both.
                        </p>


                        <div className="mt-6 grid gap-2.5 sm:mt-8 sm:grid-cols-2 sm:gap-3">
                          {
                            SUGGESTIONS.map(
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
                                    void submitMessage(
                                      suggestion
                                    );
                                  }}
                                  className="min-h-12 rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-3.5 text-left text-sm leading-5 text-[#2c1c20] shadow-sm transition hover:-translate-y-0.5 hover:border-[#ce4d42] hover:shadow-md disabled:opacity-50 sm:p-4"
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
                    <div className="space-y-4 sm:space-y-5">
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
                            <div className="max-w-[92%] rounded-2xl rounded-bl-md border border-[#dccbc4] bg-[#fffaf7] px-4 py-3 text-sm text-[#756369] shadow-sm sm:max-w-md">
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


          <div className="sticky bottom-0 z-20 border-t border-[#dccbc4] bg-[#f1e6de]/95 px-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-3 backdrop-blur sm:px-6 sm:py-4 lg:px-8">
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
                      event.target.value
                    );
                  }}
                  onKeyDown={
                    handleKeyDown
                  }
                  rows={2}
                  placeholder="Ask Retailigent anything..."
                  className="min-h-14 w-full resize-none bg-transparent px-3 py-2 text-base text-[#2c1c20] outline-none placeholder:text-[#a28e93] disabled:opacity-60 sm:text-sm"
                />


                <div className="flex items-end justify-between gap-2 px-2 pb-1">
                  <div className="min-w-0 flex-1">
                    <p className="hidden text-xs text-[#8c777c] sm:block">
                      Enter to send · Shift+Enter for a new line
                    </p>

                    {
                      conversationId
                      && (
                        <p className="hidden truncate text-[10px] text-[#ad999e] sm:mt-1 sm:block">
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
                          className="min-h-11 shrink-0 rounded-xl border border-[#7f2a3c] px-4 py-2 text-sm font-medium text-[#7f2a3c] transition hover:bg-[#f5e8e5]"
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
                          className="min-h-11 shrink-0 rounded-xl bg-[#ce4d42] px-5 py-2 text-sm font-semibold text-white transition hover:bg-[#ad3d34] disabled:cursor-not-allowed disabled:opacity-40"
                        >
                          Send
                        </button>
                      )
                  }
                </div>
              </form>


              <p className="mt-2 hidden text-center text-xs text-[#8c777c] sm:block">
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