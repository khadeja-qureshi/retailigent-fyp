"use client";

import {
  FormEvent,
  useState,
} from "react";

import Link from "next/link";

import {
  supabase,
} from "@/lib/supabase/client";


const API_URL =
  process.env.NEXT_PUBLIC_API_URL
  ??
  "http://127.0.0.1:8000";


type AnalyticsSource = {
  name: string;
  record_count: number;
};


type AnalyticsAnswer = {
  answer: string;

  data_status:
    | "available"
    | "empty"
    | "unavailable";

  sources: AnalyticsSource[];
};


const SUGGESTED_QUESTIONS = [
  "Which products or variants have the most unmet demand?",
  "Summarize inventory availability across branches.",
  "What should staff know about unavailable product searches?",
  "What information is currently missing from the analytics data?",
];


async function askAnalytics(
  question: string
): Promise<AnalyticsAnswer> {

  const {
    data: {
      session,
    },
  } =
    await supabase.auth
      .getSession();


  if (!session?.access_token) {
    throw new Error(
      "Please sign in with an authorized staff account."
    );
  }


  const response =
    await fetch(
      `${API_URL}/api/v1/analytics/ask`,
      {
        method: "POST",

        headers: {
          "Content-Type":
            "application/json",

          Authorization:
            `Bearer ${session.access_token}`,
        },

        body:
          JSON.stringify({
            question,
          }),

        cache:
          "no-store",
      }
    );


  const payload =
    await response
      .json()
      .catch(
        () => null
      );


  if (!response.ok) {
    const detail =
      payload
      &&
      typeof payload.detail
      === "string"
        ? payload.detail
        : (
          "The analytics request failed "
          +
          `(${response.status}).`
        );


    throw new Error(
      detail
    );
  }


  return payload as AnalyticsAnswer;
}


function statusLabel(
  status:
    AnalyticsAnswer[
      "data_status"
    ]
): string {

  switch (status) {
    case "available":
      return "Data retrieved";

    case "empty":
      return "No records returned";

    case "unavailable":
      return "Data unavailable";
  }
}


function statusClasses(
  status:
    AnalyticsAnswer[
      "data_status"
    ]
): string {

  if (
    status === "available"
  ) {
    return (
      "border-emerald-200 "
      +
      "bg-emerald-50 "
      +
      "text-emerald-800"
    );
  }


  if (
    status === "empty"
  ) {
    return (
      "border-amber-200 "
      +
      "bg-amber-50 "
      +
      "text-amber-800"
    );
  }


  return (
    "border-red-200 "
    +
    "bg-red-50 "
    +
    "text-red-800"
  );
}


function SparkIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      className="h-5 w-5"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 3l1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6L12 3z"
      />

      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M19 15l.9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9L19 15z"
      />
    </svg>
  );
}


function DataIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      className="h-5 w-5"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
    >
      <ellipse
        cx="12"
        cy="5"
        rx="7"
        ry="3"
      />

      <path d="M5 5v6c0 1.7 3.1 3 7 3s7-1.3 7-3V5" />

      <path d="M5 11v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" />
    </svg>
  );
}


export default function AdminAskPage() {
  const [
    question,
    setQuestion,
  ] =
    useState("");

  const [
    answer,
    setAnswer,
  ] =
    useState<
      AnalyticsAnswer
      | null
    >(null);

  const [
    error,
    setError,
  ] =
    useState<
      string
      | null
    >(null);

  const [
    loading,
    setLoading,
  ] =
    useState(false);


  async function submitQuestion(
    value: string
  ) {
    const trimmedQuestion =
      value.trim();


    if (!trimmedQuestion) {
      setError(
        "Enter a question to continue."
      );

      return;
    }


    if (
      trimmedQuestion.length
      > 1000
    ) {
      setError(
        "Questions must be 1,000 characters or fewer."
      );

      return;
    }


    setQuestion(
      trimmedQuestion
    );

    setLoading(
      true
    );

    setError(
      null
    );

    setAnswer(
      null
    );


    try {
      const result =
        await askAnalytics(
          trimmedQuestion
        );


      setAnswer(
        result
      );

    } catch (
      caught
    ) {
      setError(
        caught instanceof Error
          ? caught.message
          : (
            "The analytics assistant "
            +
            "could not answer right now."
          )
      );

    } finally {
      setLoading(
        false
      );
    }
  }


  async function handleSubmit(
    event:
      FormEvent<
        HTMLFormElement
      >
  ) {
    event.preventDefault();

    await submitQuestion(
      question
    );
  }


  async function handleSuggestedQuestion(
    value: string
  ) {
    setQuestion(
      value
    );

    setError(
      null
    );

    await submitQuestion(
      value
    );
  }


  return (
    <main className="min-h-screen bg-[#f8f5f3] px-4 py-8 text-[#332e34] sm:px-6 lg:px-8">

      <div className="mx-auto w-full max-w-6xl">

        {/* Hero */}
        <section className="overflow-hidden rounded-3xl border border-[#ded8e2] bg-white shadow-sm">

          <div className="bg-gradient-to-r from-[#332e34] via-[#463b43] to-[#684753] px-6 py-8 text-white sm:px-8 lg:px-10">

            <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">

              <div className="max-w-3xl">

                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#c9c9ff]">
                  Retailigent · Staff Analytics
                </p>


                <h1 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">
                  Ask Analytics
                </h1>


                <p className="mt-3 max-w-2xl text-sm leading-6 text-white/70 sm:text-base">
                  Ask questions about unmet demand,
                  branch inventory, and operational
                  analytics. Answers are grounded in
                  retrieved Retailigent data.
                </p>

              </div>


              <Link
                href="/admin/analytics"
                className="inline-flex min-h-11 items-center justify-center rounded-xl border border-white/20 bg-white/10 px-4 text-sm font-semibold text-white transition hover:bg-white/20"
              >
                View analytics dashboard →
              </Link>

            </div>

          </div>


          <div className="grid gap-4 border-t border-[#eee8ef] bg-white px-6 py-4 text-sm text-[#716a73] sm:grid-cols-2 sm:px-8 lg:px-10">

            <div className="flex items-center gap-2">
              <DataIcon />

              <span>
                Uses retrieved analytics records
              </span>
            </div>


            <div className="flex items-center gap-2 sm:justify-end">
              <SparkIcon />

              <span>
                No unsupported assumptions
              </span>
            </div>

          </div>

        </section>


        <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">

          {/* Ask panel */}
          <section className="rounded-3xl border border-[#ded8e2] bg-white p-5 shadow-sm sm:p-7">

            <div className="flex items-start gap-3">

              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-[#7779de]/10 text-[#6667d9]">
                <SparkIcon />
              </span>


              <div>
                <h2 className="text-xl font-bold">
                  Ask a staff analytics question
                </h2>

                <p className="mt-1 text-sm leading-6 text-[#716a73]">
                  Ask about demand, inventory,
                  unavailable searches, and other
                  recorded operational data.
                </p>
              </div>

            </div>


            <form
              onSubmit={
                handleSubmit
              }
              className="mt-6"
            >

              <label
                htmlFor="analytics-question"
                className="sr-only"
              >
                Analytics question
              </label>


              <textarea
                id="analytics-question"
                value={
                  question
                }
                onChange={
                  (
                    event
                  ) => {
                    setQuestion(
                      event.target.value
                    );

                    if (error) {
                      setError(
                        null
                      );
                    }
                  }
                }
                maxLength={
                  1000
                }
                rows={
                  6
                }
                placeholder="For example: Which products or variants have the most unmet demand?"
                className="w-full resize-y rounded-2xl border border-[#ded8e2] bg-[#fcfbfc] p-4 text-sm leading-6 text-[#332e34] outline-none transition placeholder:text-[#a39ba4] focus:border-[#7779de] focus:bg-white focus:ring-4 focus:ring-[#7779de]/10"
                disabled={
                  loading
                }
              />


              <div className="mt-3 flex flex-wrap items-center justify-between gap-3">

                <p className="text-xs text-[#8a828b]">
                  {
                    question.length
                  }
                  /1,000 characters
                </p>


                <button
                  type="submit"
                  disabled={
                    loading
                    ||
                    !question.trim()
                  }
                  className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-[#7779de] px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-[#6667ca] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {
                    loading
                      ? (
                        <>
                          <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                          Analyzing…
                        </>
                      )
                      : (
                        <>
                          <SparkIcon />
                          Ask analytics →
                        </>
                      )
                  }
                </button>

              </div>

            </form>


            {
              error
              && (
                <div
                  role="alert"
                  className="mt-5 rounded-2xl border border-red-200 bg-red-50 p-4"
                >
                  <p className="text-sm font-semibold text-red-800">
                    Could not complete the request
                  </p>

                  <p className="mt-1 text-sm leading-6 text-red-700">
                    {
                      error
                    }
                  </p>
                </div>
              )
            }


            {
              loading
              && (
                <div
                  role="status"
                  className="mt-5 flex items-center gap-3 rounded-2xl border border-[#ded8e2] bg-[#faf8fa] p-4 text-sm text-[#716a73]"
                >
                  <span className="h-5 w-5 animate-spin rounded-full border-2 border-[#7779de]/20 border-t-[#7779de]" />

                  <span>
                    Retrieving analytics records
                    and preparing your answer…
                  </span>
                </div>
              )
            }


            {
              answer
              && (
                <section
                  aria-live="polite"
                  className="mt-6 overflow-hidden rounded-2xl border border-[#ded8e2] bg-[#fcfbfc]"
                >

                  <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#eee8ef] bg-white px-5 py-4">

                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#7779de]">
                        Analytics Agent
                      </p>

                      <h2 className="mt-1 text-lg font-bold">
                        Response
                      </h2>
                    </div>


                    <span
                      className={
                        (
                          "rounded-full border "
                          +
                          "px-3 py-1.5 "
                          +
                          "text-xs font-semibold "
                        )
                        +
                        statusClasses(
                          answer.data_status
                        )
                      }
                    >
                      {
                        statusLabel(
                          answer.data_status
                        )
                      }
                    </span>

                  </div>


                  <div className="px-5 py-5">

                    <p className="whitespace-pre-wrap text-sm leading-7 text-[#45353a]">
                      {
                        answer.answer
                      }
                    </p>


                    {
                      answer.data_status
                      === "empty"
                      && (
                        <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs leading-5 text-amber-900">
                          An empty result does not
                          prove that demand or
                          inventory is zero. It means
                          the queried analytics views
                          returned no records.
                        </div>
                      )
                    }


                    {
                      answer.sources.length
                      > 0
                      && (
                        <div className="mt-6 border-t border-[#eee8ef] pt-5">

                          <h3 className="text-sm font-semibold">
                            Retrieved data sources
                          </h3>


                          <div className="mt-3 grid gap-2">

                            {
                              answer.sources.map(
                                (
                                  source
                                ) => (
                                  <div
                                    key={
                                      source.name
                                    }
                                    className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#eee8ef] bg-white px-4 py-3 text-sm"
                                  >
                                    <span className="break-words capitalize text-[#5e4a50]">
                                      {
                                        source.name
                                          .replaceAll(
                                            "_",
                                            " "
                                          )
                                      }
                                    </span>

                                    <span className="rounded-full bg-[#f4f1f5] px-3 py-1 text-xs font-semibold tabular-nums text-[#4f4851]">
                                      {
                                        new Intl.NumberFormat()
                                          .format(
                                            source.record_count
                                          )
                                      }
                                      {" "}
                                      records
                                    </span>
                                  </div>
                                )
                              )
                            }

                          </div>

                        </div>
                      )
                    }

                  </div>

                </section>
              )
            }

          </section>


          {/* Suggested questions */}
          <aside className="h-fit rounded-3xl border border-[#ded8e2] bg-white p-5 shadow-sm sm:p-6">

            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#7779de]">
              Quick prompts
            </p>


            <h2 className="mt-2 text-xl font-bold">
              Suggested questions
            </h2>


            <p className="mt-2 text-sm leading-6 text-[#716a73]">
              Use one of these to quickly test the
              Analytics Agent against your current
              staff data.
            </p>


            <div className="mt-5 grid gap-3">

              {
                SUGGESTED_QUESTIONS.map(
                  (
                    suggestion,
                    index
                  ) => (
                    <button
                      key={
                        suggestion
                      }
                      type="button"
                      disabled={
                        loading
                      }
                      onClick={() => {
                        void handleSuggestedQuestion(
                          suggestion
                        );
                      }}
                      className="group rounded-2xl border border-[#ded8e2] bg-[#fcfbfc] p-4 text-left transition hover:border-[#7779de]/50 hover:bg-[#f7f6ff] disabled:cursor-not-allowed disabled:opacity-50"
                    >

                      <div className="flex items-start gap-3">

                        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-[#7779de]/10 text-xs font-bold text-[#6667d9]">
                          {
                            index + 1
                          }
                        </span>


                        <div className="min-w-0">

                          <p className="text-sm font-medium leading-6 text-[#453e46]">
                            {
                              suggestion
                            }
                          </p>


                          <p className="mt-2 text-xs font-semibold text-[#7779de] opacity-0 transition group-hover:opacity-100">
                            Ask this question →
                          </p>

                        </div>

                      </div>

                    </button>
                  )
                )
              }

            </div>


            <div className="mt-6 border-t border-[#eee8ef] pt-5">

              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#8a828b]">
                Staff tools
              </p>


              <div className="mt-3 grid gap-2">

                <Link
                  href="/admin/analytics"
                  className="rounded-xl px-3 py-2.5 text-sm font-medium text-[#5a535b] transition hover:bg-[#f4f1f5] hover:text-[#6667d9]"
                >
                  Analytics dashboard →
                </Link>


                <Link
                  href="/admin/tickets"
                  className="rounded-xl px-3 py-2.5 text-sm font-medium text-[#5a535b] transition hover:bg-[#f4f1f5] hover:text-[#6667d9]"
                >
                  Support tickets →
                </Link>


                <Link
                  href="/admin/feedback"
                  className="rounded-xl px-3 py-2.5 text-sm font-medium text-[#5a535b] transition hover:bg-[#f4f1f5] hover:text-[#6667d9]"
                >
                  Feedback review →
                </Link>

              </div>

            </div>

          </aside>

        </div>

      </div>

    </main>
  );
}