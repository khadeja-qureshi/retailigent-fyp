"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { supabase } from "@/lib/supabase/client";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

type AnalyticsSource = {
  name: string;
  record_count: number;
};

type AnalyticsAnswer = {
  answer: string;
  data_status: "available" | "empty" | "unavailable";
  sources: AnalyticsSource[];
};

const SUGGESTED_QUESTIONS = [
  "Which products or variants have the most unmet demand?",
  "Summarize inventory availability across branches.",
  "What should staff know about unavailable product searches?",
  "What information is currently missing from the analytics data?",
];

async function askAnalytics(question: string): Promise<AnalyticsAnswer> {
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.access_token) {
    throw new Error("Please sign in with an authorized staff account.");
  }

  const response = await fetch(`${API_URL}/api/v1/analytics/ask`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${session.access_token}`,
    },
    body: JSON.stringify({ question }),
    cache: "no-store",
  });

  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    const detail =
      payload && typeof payload.detail === "string"
        ? payload.detail
        : `The analytics request failed (${response.status}).`;

    throw new Error(detail);
  }

  return payload as AnalyticsAnswer;
}

function statusLabel(status: AnalyticsAnswer["data_status"]): string {
  switch (status) {
    case "available":
      return "Data retrieved";
    case "empty":
      return "No records returned";
    case "unavailable":
      return "Data unavailable";
  }
}

export default function AdminAskPage() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<AnalyticsAnswer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmedQuestion = question.trim();

    if (!trimmedQuestion) {
      setError("Enter a question to continue.");
      return;
    }

    if (trimmedQuestion.length > 1000) {
      setError("Questions must be 1,000 characters or fewer.");
      return;
    }

    setLoading(true);
    setError(null);
    setAnswer(null);

    try {
      const result = await askAnalytics(trimmedQuestion);
      setAnswer(result);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "The analytics assistant could not answer right now.",
      );
    } finally {
      setLoading(false);
    }
  }

  function handleSuggestedQuestion(value: string) {
    setQuestion(value);
    setError(null);
  }

  return (
    <main className="min-h-screen bg-[#fffaf7] px-4 py-6 text-[#2c1c20] sm:px-6 sm:py-10">
      <div className="mx-auto max-w-4xl">
        <Link
          href="/admin"
          className="inline-flex min-h-10 items-center text-sm font-semibold text-[#7f2a3c] hover:underline"
        >
          â† Back to staff workspace
        </Link>

        <header className="mt-6">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#7f2a3c]">
            Retailigent Â· Staff tools
          </p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">
            Ask Analytics
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-[#756369] sm:text-base">
            Ask questions about recorded unmet demand and branch inventory.
            Answers are based on retrieved analytics data, not assumptions.
          </p>
        </header>

        <section className="mt-8 rounded-2xl border border-[#dccbc4] bg-white p-4 shadow-sm sm:p-6">
          <form onSubmit={handleSubmit}>
            <label
              htmlFor="analytics-question"
              className="block text-sm font-semibold"
            >
              What would you like to know?
            </label>

            <textarea
              id="analytics-question"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              maxLength={1000}
              rows={4}
              placeholder="For example: Which variants have repeated unavailable searches?"
              className="mt-3 w-full resize-y rounded-xl border border-[#dccbc4] bg-white p-3 text-sm leading-6 outline-none transition placeholder:text-[#9b8b90] focus:border-[#7f2a3c] focus:ring-2 focus:ring-[#7f2a3c]/15"
              disabled={loading}
            />

            <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
              <p className="text-xs text-[#756369]">
                {question.length}/1,000 characters
              </p>

              <button
                type="submit"
                disabled={loading || !question.trim()}
                className="inline-flex min-h-11 items-center justify-center rounded-xl bg-[#7f2a3c] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#652131] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? "Analyzingâ€¦" : "Ask analytics â†’"}
              </button>
            </div>
          </form>

          <div className="mt-6 border-t border-[#eee2dd] pt-5">
            <h2 className="text-sm font-semibold">Suggested questions</h2>
            <div className="mt-3 flex flex-wrap gap-2">
              {SUGGESTED_QUESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => handleSuggestedQuestion(suggestion)}
                  disabled={loading}
                  className="rounded-full border border-[#dccbc4] px-3 py-2 text-left text-xs leading-5 text-[#5e4a50] transition hover:border-[#7f2a3c] hover:bg-[#fff4f2] disabled:opacity-50 sm:text-sm"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        </section>

        {error && (
          <section
            role="alert"
            className="mt-5 rounded-xl border border-red-200 bg-red-50 p-4 text-sm leading-6 text-red-800"
          >
            <p className="font-semibold">Could not complete the request</p>
            <p className="mt-1">{error}</p>
          </section>
        )}

        {loading && (
          <section
            role="status"
            className="mt-5 rounded-xl border border-[#dccbc4] bg-white p-5 text-sm text-[#756369]"
          >
            Retrieving analytics records and preparing your answerâ€¦
          </section>
        )}

        {answer && (
          <section
            aria-live="polite"
            className="mt-5 rounded-2xl border border-[#dccbc4] bg-white p-5 shadow-sm sm:p-6"
          >
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-lg font-bold">Analytics response</h2>
              <span
                className={`rounded-full px-3 py-1 text-xs font-semibold ${
                  answer.data_status === "available"
                    ? "bg-emerald-50 text-emerald-800"
                    : answer.data_status === "empty"
                      ? "bg-amber-50 text-amber-800"
                      : "bg-red-50 text-red-800"
                }`}
              >
                {statusLabel(answer.data_status)}
              </span>
            </div>

            <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-[#45353a]">
              {answer.answer}
            </p>

            {answer.data_status === "empty" && (
              <p className="mt-4 rounded-xl bg-amber-50 p-3 text-xs leading-5 text-amber-900">
                An empty result does not prove that demand or inventory is
                zero. It means the queried analytics views returned no records.
              </p>
            )}

            {answer.sources.length > 0 && (
              <div className="mt-6 border-t border-[#eee2dd] pt-4">
                <h3 className="text-sm font-semibold">Retrieved data sources</h3>
                <ul className="mt-3 space-y-2">
                  {answer.sources.map((source) => (
                    <li
                      key={source.name}
                      className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-[#fffaf7] px-3 py-3 text-sm"
                    >
                      <span className="break-words text-[#5e4a50]">
                        {source.name.replaceAll("_", " ")}
                      </span>
                      <span className="font-semibold tabular-nums">
                        {new Intl.NumberFormat().format(source.record_count)}{" "}
                        records
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        )}

        <nav className="mt-8 flex flex-wrap gap-3 border-t border-[#dccbc4] pt-5 text-sm font-semibold">
          <Link
            href="/admin/analytics"
            className="rounded-lg px-2 py-2 text-[#7f2a3c] hover:underline"
          >
            View analytics dashboard â†’
          </Link>
          <Link
            href="/admin/tickets"
            className="rounded-lg px-2 py-2 text-[#7f2a3c] hover:underline"
          >
            Review support tickets â†’
          </Link>
          <Link
            href="/admin/feedback"
            className="rounded-lg px-2 py-2 text-[#7f2a3c] hover:underline"
          >
            Review feedback â†’
          </Link>
        </nav>
      </div>
    </main>
  );
}
