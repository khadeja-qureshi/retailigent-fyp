"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { supabase } from "@/lib/supabase/client";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

const STATUSES = [
  "open",
  "in_progress",
  "waiting_customer",
  "escalated",
  "resolved",
  "closed",
] as const;

const PRIORITIES = ["urgent", "high", "normal", "low"] as const;

type TicketStatus = (typeof STATUSES)[number];
type TicketPriority = (typeof PRIORITIES)[number];

interface SupportTicket {
  id: string;
  customer_id: string;
  conversation_id?: string | null;
  subject: string;
  description?: string | null;
  status: TicketStatus;
  priority: TicketPriority;
  sentiment?: string | null;
  assigned_staff_id?: string | null;
  handoff_summary?: string | null;
  agent_context?: Record<string, unknown>;
  created_at?: string | null;
  updated_at?: string | null;
}

async function request<T>(path: string): Promise<T> {
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.access_token) {
    throw new Error("Sign in with an authorized staff account.");
  }

  const response = await fetch(`${API_URL}${path}`, {
    headers: {
      Authorization: `Bearer ${session.access_token}`,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    let message = "The support ticket queue could not be loaded.";
    try {
      const payload = await response.json();
      if (typeof payload.detail === "string") message = payload.detail;
    } catch {
      // Keep the fallback for non-JSON errors.
    }
    throw new Error(message);
  }

  return (await response.json()) as T;
}

function formatDate(value?: string | null): string {
  if (!value) return "Date unavailable";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Date unavailable"
    : date.toLocaleString();
}

function label(value?: string | null): string {
  if (!value) return "Unknown";
  return value.replaceAll("_", " ");
}

function priorityStyle(priority: TicketPriority): string {
  switch (priority) {
    case "urgent":
      return "border-red-300 bg-red-50 text-red-800";
    case "high":
      return "border-orange-300 bg-orange-50 text-orange-800";
    case "normal":
      return "border-[#dccbc4] bg-[#f7ece7] text-[#674f56]";
    case "low":
      return "border-[#cbd9ce] bg-[#f0f6f1] text-[#496653]";
  }
}

export default function AdminTicketsPage() {
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const loadTickets = useCallback(async () => {
    setLoading(true);
    setLoadError(null);

    try {
      const params = new URLSearchParams({ limit: "100" });
      if (statusFilter) params.set("status", statusFilter);
      if (priorityFilter) params.set("priority", priorityFilter);

      const result = await request<{
        tickets: SupportTicket[];
        count: number;
      }>(`/api/v1/support/tickets?${params.toString()}`);

      const priorityRank: Record<TicketPriority, number> = {
        urgent: 0,
        high: 1,
        normal: 2,
        low: 3,
      };

      setTickets(
        [...result.tickets].sort((a, b) => {
          const priorityDifference =
            priorityRank[a.priority] - priorityRank[b.priority];

          if (priorityDifference !== 0) return priorityDifference;

          return (
            new Date(b.updated_at ?? b.created_at ?? 0).getTime() -
            new Date(a.updated_at ?? a.created_at ?? 0).getTime()
          );
        }),
      );
    } catch (caught) {
      setLoadError(
        caught instanceof Error
          ? caught.message
          : "The support ticket queue could not be loaded.",
      );
    } finally {
      setLoading(false);
    }
  }, [statusFilter, priorityFilter]);

  useEffect(() => {
    queueMicrotask(() => {
      void loadTickets();
    });
  }, [loadTickets]);

  return (
    <main className="min-h-[calc(100dvh-4rem)] bg-[#f1e6de] px-4 py-6 text-[#2c1c20] sm:px-6 sm:py-8">
      <div className="mx-auto w-full max-w-6xl">
        <header className="rounded-3xl border border-[#dccbc4] bg-[#fffaf7] p-5 shadow-sm sm:p-8">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#7f2a3c]">
            Staff workspace
          </p>
          <h1 className="mt-2 text-3xl font-bold sm:text-4xl">
            Support tickets
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-[#756369]">
            Review customer escalations, prioritise urgent concerns, and open a
            ticket to read its conversation and respond. Access is enforced by
            the backend.
          </p>

          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            <label className="text-sm font-semibold">
              Filter by status
              <select
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value)}
                className="mt-2 min-h-11 w-full rounded-xl border border-[#dccbc4] bg-white px-3 font-normal"
              >
                <option value="">All statuses</option>
                {STATUSES.map((status) => (
                  <option key={status} value={status}>
                    {label(status)}
                  </option>
                ))}
              </select>
            </label>

            <label className="text-sm font-semibold">
              Filter by priority
              <select
                value={priorityFilter}
                onChange={(event) => setPriorityFilter(event.target.value)}
                className="mt-2 min-h-11 w-full rounded-xl border border-[#dccbc4] bg-white px-3 font-normal"
              >
                <option value="">All priorities</option>
                {PRIORITIES.map((priority) => (
                  <option key={priority} value={priority}>
                    {label(priority)}
                  </option>
                ))}
              </select>
            </label>

            <div className="flex items-end">
              <button
                type="button"
                onClick={() => void loadTickets()}
                disabled={loading}
                className="min-h-11 w-full rounded-xl border border-[#dccbc4] px-4 py-2 text-sm font-semibold text-[#674f56] hover:bg-[#f7ece7] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? "Refreshing..." : "Refresh queue"}
              </button>
            </div>
          </div>

          <p className="mt-4 text-sm text-[#756369]" aria-live="polite">
            {loading
              ? "Loading tickets..."
              : `${tickets.length} ticket${tickets.length === 1 ? "" : "s"} shown`}
          </p>
        </header>

        {loadError && (
          <div
            role="alert"
            className="mt-5 rounded-2xl border border-[#e4aaa3] bg-[#fff2ef] px-4 py-3 text-sm text-[#9b352e]"
          >
            <p>{loadError}</p>
            <button
              type="button"
              onClick={() => void loadTickets()}
              className="mt-2 font-semibold underline"
            >
              Try again
            </button>
          </div>
        )}

        <section
          aria-label="Support ticket queue"
          className="mt-6 space-y-4"
        >
          {loading && tickets.length === 0 && !loadError && (
            <p className="rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-5 text-sm text-[#756369]">
              Loading the support queue...
            </p>
          )}

          {!loading && !loadError && tickets.length === 0 && (
            <div className="rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-6">
              <h2 className="font-semibold">No tickets found</h2>
              <p className="mt-1 text-sm text-[#756369]">
                Try changing the filters, or refresh to check for new tickets.
              </p>
            </div>
          )}

          {tickets.map((ticket) => (
            <article
              key={ticket.id}
              className="rounded-3xl border border-[#dccbc4] bg-[#fffaf7] p-5 shadow-sm transition hover:shadow-md sm:p-6"
            >
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <p className="break-all text-xs text-[#8c777c]">
                    Ticket {ticket.id}
                  </p>
                  <h2 className="mt-1 text-lg font-bold">
                    {ticket.subject || "Untitled support ticket"}
                  </h2>
                  <p className="mt-1 text-xs text-[#8c777c]">
                    Updated {formatDate(ticket.updated_at ?? ticket.created_at)}
                  </p>
                </div>

                <div className="flex flex-wrap gap-2 text-xs font-semibold">
                  <span className="rounded-full border border-[#dccbc4] px-3 py-1.5 capitalize">
                    {label(ticket.status)}
                  </span>
                  <span
                    className={`rounded-full border px-3 py-1.5 capitalize ${priorityStyle(ticket.priority)}`}
                  >
                    {label(ticket.priority)} priority
                  </span>
                  {ticket.sentiment && (
                    <span className="rounded-full border border-[#dccbc4] px-3 py-1.5 capitalize">
                      {label(ticket.sentiment)} sentiment
                    </span>
                  )}
                </div>
              </div>

              {ticket.description && (
                <p className="mt-4 whitespace-pre-wrap break-words text-sm leading-6 text-[#674f56]">
                  {ticket.description}
                </p>
              )}

              {ticket.handoff_summary && (
                <div className="mt-4 rounded-2xl bg-[#f7ece7] p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#7f2a3c]">
                    AI handoff summary
                  </p>
                  <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-[#674f56]">
                    {ticket.handoff_summary}
                  </p>
                </div>
              )}

              <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-[#eee0da] pt-4">
                <p className="text-xs text-[#8c777c]">
                  {ticket.assigned_staff_id
                    ? "Assigned to a staff member"
                    : "Unassigned"}
                </p>
                <Link
                  href={`/admin/tickets/${encodeURIComponent(ticket.id)}`}
                  className="inline-flex min-h-10 items-center justify-center rounded-xl bg-[#7f2a3c] px-4 py-2 text-sm font-semibold text-white transition hover:bg-[#682132]"
                >
                  Open ticket
                  <span aria-hidden="true" className="ml-2">→</span>
                </Link>
              </div>
            </article>
          ))}
        </section>
      </div>
    </main>
  );
}
