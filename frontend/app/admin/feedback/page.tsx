"use client";

import { useCallback, useEffect, useState } from "react";
import { supabase } from "@/lib/supabase/client";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

const CATEGORIES = [
  "product",
  "service",
  "delivery",
  "store",
  "website",
  "agent",
  "general",
] as const;

const SENTIMENTS = ["positive", "neutral", "negative"] as const;

type Category = (typeof CATEGORIES)[number];
type Sentiment = (typeof SENTIMENTS)[number];

interface FeedbackRecord {
  id: string;
  customer_id?: string;
  conversation_id?: string | null;
  feedback_type?: string;
  rating?: number | null;
  message: string;
  ai_category?: string | null;
  ai_sentiment?: string | null;
  staff_category?: string | null;
  staff_sentiment?: string | null;
  classification_source?: string | null;
  created_at?: string | null;
}

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.access_token) {
    throw new Error("Sign in with an authorized staff account.");
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${session.access_token}`,
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
    },
  });

  if (!response.ok) {
    let message = "The feedback request failed.";
    try {
      const payload = await response.json();
      if (typeof payload.detail === "string") {
        message = payload.detail;
      }
    } catch {
      // Use the fallback message for non-JSON errors.
    }
    throw new Error(message);
  }

  return (await response.json()) as T;
}

function prettyDate(value?: string | null): string {
  if (!value) return "Date unavailable";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Date unavailable"
    : date.toLocaleString();
}

export default function AdminFeedbackPage() {
  const [items, setItems] = useState<FeedbackRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<
    Record<string, { category: Category; sentiment: Sentiment }>
  >({});
  const [notice, setNotice] = useState<string | null>(null);

  const loadQueue = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const result = await request<{
        feedback: FeedbackRecord[];
        count: number;
      }>("/api/v1/feedback/review-queue?limit=200");

      setItems(result.feedback);
      setDrafts(
        Object.fromEntries(
          result.feedback.map((item) => [
            item.id,
            {
              category: CATEGORIES.includes(item.ai_category as Category)
                ? (item.ai_category as Category)
                : "general",
              sentiment: SENTIMENTS.includes(item.ai_sentiment as Sentiment)
                ? (item.ai_sentiment as Sentiment)
                : "neutral",
            },
          ]),
        ),
      );
    } catch (caught) {
      setLoadError(
        caught instanceof Error
          ? caught.message
          : "The feedback review queue could not be loaded.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => {
      void loadQueue();
    });
  }, [loadQueue]);

  async function saveClassification(item: FeedbackRecord) {
    const draft = drafts[item.id];
    if (!draft || savingId) return;

    setSavingId(item.id);
    setLoadError(null);
    setNotice(null);

    try {
      await request<FeedbackRecord>(
        `/api/v1/feedback/${encodeURIComponent(item.id)}/classification`,
        {
          method: "PATCH",
          body: JSON.stringify({
            staff_category: draft.category,
            staff_sentiment: draft.sentiment,
          }),
        },
      );

      setItems((current) => current.filter((entry) => entry.id !== item.id));
      setNotice("Classification corrected. This item has been removed from the review queue.");
    } catch (caught) {
      setLoadError(
        caught instanceof Error
          ? caught.message
          : "The classification could not be updated.",
      );
    } finally {
      setSavingId(null);
    }
  }

  return (
    <main className="min-h-[calc(100dvh-4rem)] bg-[#f1e6de] px-4 py-6 text-[#2c1c20] sm:px-6 sm:py-8">
      <div className="mx-auto w-full max-w-5xl">
        <header className="rounded-3xl border border-[#dccbc4] bg-[#fffaf7] p-5 shadow-sm sm:p-8">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#7f2a3c]">
            Staff workspace
          </p>
          <h1 className="mt-2 text-3xl font-bold sm:text-4xl">
            Feedback review
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-[#756369]">
            Review feedback flagged by the classifier, check the original
            customer message, and correct the category or sentiment when needed.
            Access is enforced by the backend for staff and administrators.
          </p>
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <span className="rounded-full bg-[#f4ded8] px-3 py-1.5 text-sm font-semibold text-[#7f2a3c]">
              {items.length} awaiting review
            </span>
            <button
              type="button"
              onClick={() => void loadQueue()}
              disabled={loading}
              className="min-h-10 rounded-xl border border-[#dccbc4] px-4 py-2 text-sm font-semibold text-[#674f56] hover:bg-[#f7ece7] disabled:opacity-50"
            >
              {loading ? "Refreshing..." : "Refresh queue"}
            </button>
          </div>
        </header>

        {loadError && (
          <div role="alert" className="mt-5 rounded-2xl border border-[#e4aaa3] bg-[#fff2ef] px-4 py-3 text-sm text-[#9b352e]">
            {loadError}
          </div>
        )}
        {notice && (
          <div role="status" className="mt-5 rounded-2xl border border-[#b8d9bd] bg-white px-4 py-3 text-sm text-[#356b45]">
            {notice}
          </div>
        )}

        <section aria-label="Feedback requiring review" className="mt-6 space-y-4">
          {loading && items.length === 0 && (
            <p className="rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-5 text-sm text-[#756369]">
              Loading feedback review queue...
            </p>
          )}

          {!loading && !loadError && items.length === 0 && (
            <div className="rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-6">
              <h2 className="font-semibold">No feedback awaiting review</h2>
              <p className="mt-1 text-sm text-[#756369]">
                Flagged feedback will appear here when it is available.
              </p>
            </div>
          )}

          {items.map((item) => {
            const draft = drafts[item.id];
            return (
              <article
                key={item.id}
                className="rounded-3xl border border-[#dccbc4] bg-[#fffaf7] p-5 shadow-sm sm:p-6"
              >
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.15em] text-[#7f2a3c]">
                      {item.feedback_type ?? "general"} feedback
                    </p>
                    <p className="mt-1 text-xs text-[#8c777c]">
                      {prettyDate(item.created_at)}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2 text-xs">
                    <span className="rounded-full border border-[#e2d5cf] px-2.5 py-1">
                      AI: {item.ai_category ?? "unclassified"}
                    </span>
                    <span className="rounded-full border border-[#e2d5cf] px-2.5 py-1">
                      Sentiment: {item.ai_sentiment ?? "unknown"}
                    </span>
                    <span className="rounded-full border border-[#e2d5cf] px-2.5 py-1">
                      Source: {item.classification_source ?? "unknown"}
                    </span>
                  </div>
                </div>

                <blockquote className="mt-4 whitespace-pre-wrap break-words rounded-2xl bg-[#f7ece7] p-4 text-sm leading-6 text-[#674f56]">
                  {item.message}
                </blockquote>

                <div className="mt-4 grid gap-4 sm:grid-cols-2">
                  <label className="block text-sm font-semibold text-[#332e34]">
                    Correct category
                    <select
                      value={draft?.category ?? "general"}
                      disabled={!draft || savingId === item.id}
                      onChange={(event) => {
                        const category = event.target.value as Category;
                        setDrafts((current) => ({
                          ...current,
                          [item.id]: {
                            ...(current[item.id] ?? {
                              category: "general" as Category,
                              sentiment: "neutral" as Sentiment,
                            }),
                            category,
                          },
                        }));
                      }}
                      className="mt-2 min-h-11 w-full rounded-xl border border-[#dccbc4] bg-white px-3 py-2 font-normal"
                    >
                      {CATEGORIES.map((category) => (
                        <option key={category} value={category}>
                          {category}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="block text-sm font-semibold text-[#332e34]">
                    Correct sentiment
                    <select
                      value={draft?.sentiment ?? "neutral"}
                      disabled={!draft || savingId === item.id}
                      onChange={(event) => {
                        const sentiment = event.target.value as Sentiment;
                        setDrafts((current) => ({
                          ...current,
                          [item.id]: {
                            ...(current[item.id] ?? {
                              category: "general" as Category,
                              sentiment: "neutral" as Sentiment,
                            }),
                            sentiment,
                          },
                        }));
                      }}
                      className="mt-2 min-h-11 w-full rounded-xl border border-[#dccbc4] bg-white px-3 py-2 font-normal"
                    >
                      {SENTIMENTS.map((sentiment) => (
                        <option key={sentiment} value={sentiment}>
                          {sentiment}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>

                <button
                  type="button"
                  onClick={() => void saveClassification(item)}
                  disabled={!draft || savingId !== null}
                  className="mt-5 min-h-11 rounded-xl bg-[#7f2a3c] px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-[#682132] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {savingId === item.id ? "Saving correction..." : "Save correction and resolve"}
                </button>
              </article>
            );
          })}
        </section>
      </div>
    </main>
  );
}
