"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { supabase } from "@/lib/supabase/client";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

type Ticket = {
  priority?: string;
  status?: string;
};

type InventoryRow = {
  low_stock_variants?: number | string | null;
  out_of_stock_variants?: number | string | null;
};

type OverviewData = {
  tickets: Ticket[] | null;
  feedbackCount: number | null;
  lowStock: number | null;
  outOfStock: number | null;
  errors: string[];
};

async function request<T>(path: string): Promise<T> {
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.access_token) {
    throw new Error("Please sign in with an authorized staff account.");
  }

  const response = await fetch(`${API_URL}${path}`, {
    headers: {
      Authorization: `Bearer ${session.access_token}`,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    let message = `Request failed (${response.status}).`;

    try {
      const payload = await response.json();
      if (typeof payload.detail === "string") {
        message = payload.detail;
      }
    } catch {
      // Keep the HTTP status message.
    }

    throw new Error(message);
  }

  return (await response.json()) as T;
}

function numeric(value?: number | string | null): number {
  const result = Number(value ?? 0);
  return Number.isFinite(result) ? result : 0;
}

function MetricCard({
  label,
  value,
  description,
  href,
  accent = "default",
}: {
  label: string;
  value: number | null;
  description: string;
  href: string;
  accent?: "default" | "warning" | "danger";
}) {
  const valueStyle =
    accent === "danger"
      ? "text-red-700"
      : accent === "warning"
        ? "text-amber-700"
        : "text-[#2c1c20]";

  return (
    <Link
      href={href}
      className="group rounded-2xl border border-[#dccbc4] bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-[#b99ba0] hover:shadow-md sm:p-6"
    >
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-semibold text-[#756369]">{label}</p>
        <span className="text-lg text-[#9b7d84] transition group-hover:translate-x-1">
          ↗
        </span>
      </div>
      <p className={`mt-4 text-3xl font-bold tabular-nums ${valueStyle}`}>
        {value === null ? "—" : new Intl.NumberFormat().format(value)}
      </p>
      <p className="mt-2 text-sm leading-5 text-[#756369]">{description}</p>
      <p className="mt-5 text-sm font-semibold text-[#7f2a3c]">
        Open section →
      </p>
    </Link>
  );
}

function WorkspaceCard({
  eyebrow,
  title,
  description,
  href,
  details,
}: {
  eyebrow: string;
  title: string;
  description: string;
  href: string;
  details: string[];
}) {
  return (
    <section className="flex flex-col rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-5 sm:p-6">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#7f2a3c]">
        {eyebrow}
      </p>
      <h2 className="mt-2 text-xl font-bold">{title}</h2>
      <p className="mt-2 flex-1 text-sm leading-6 text-[#756369]">
        {description}
      </p>
      <ul className="mt-5 space-y-2">
        {details.map((detail) => (
          <li key={detail} className="flex gap-2 text-sm text-[#5e4a50]">
            <span className="text-[#7f2a3c]">•</span>
            <span>{detail}</span>
          </li>
        ))}
      </ul>
      <Link
        href={href}
        className="mt-6 inline-flex min-h-11 items-center justify-center rounded-xl bg-[#7f2a3c] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[#652131]"
      >
        Open {title} →
      </Link>
    </section>
  );
}

export default function AdminOverviewPage() {
  const [data, setData] = useState<OverviewData>({
    tickets: null,
    feedbackCount: null,
    lowStock: null,
    outOfStock: null,
    errors: [],
  });
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  const loadOverview = useCallback(async () => {
    setLoading(true);

    const next: OverviewData = {
      tickets: null,
      feedbackCount: null,
      lowStock: null,
      outOfStock: null,
      errors: [],
    };

    const results = await Promise.allSettled([
      request<{ tickets: Ticket[] }>("/api/v1/support/tickets?limit=100"),
      request<{ feedback: unknown[]; count: number }>(
        "/api/v1/feedback/review-queue?limit=200",
      ),
      request<{ branches: InventoryRow[] }>(
        "/api/v1/analytics/inventory?limit=100",
      ),
    ]);

    const names = ["Support tickets", "Feedback review", "Inventory analytics"];

    results.forEach((result, index) => {
      if (result.status === "rejected") {
        next.errors.push(
          `${names[index]}: ${
            result.reason instanceof Error
              ? result.reason.message
              : "Could not load data."
          }`,
        );
        return;
      }

      if (index === 0) {
        const payload = result.value as { tickets: Ticket[] };
        next.tickets = payload.tickets;
      } else if (index === 1) {
        const payload = result.value as {
          feedback: unknown[];
          count: number;
        };
        next.feedbackCount = numeric(payload.count);
      } else {
        const payload = result.value as { branches: InventoryRow[] };
        next.lowStock = payload.branches.reduce(
          (sum, row) => sum + numeric(row.low_stock_variants),
          0,
        );
        next.outOfStock = payload.branches.reduce(
          (sum, row) => sum + numeric(row.out_of_stock_variants),
          0,
        );
      }
    });

    setData(next);
    setLastUpdated(new Date().toLocaleString());
    setLoading(false);
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadOverview();
    }, 0);

    return () => window.clearTimeout(timer);
  }, [loadOverview]);

  const openTickets =
    data.tickets?.filter(
      (ticket) =>
        ticket.status !== "resolved" && ticket.status !== "closed",
    ).length ?? null;

  const priorityTickets =
    data.tickets?.filter(
      (ticket) =>
        (ticket.status !== "resolved" && ticket.status !== "closed") &&
        (ticket.priority === "urgent" || ticket.priority === "high"),
    ).length ?? null;

  return (
    <main className="min-h-[calc(100dvh-4rem)] bg-[#f1e6de] px-4 py-6 text-[#2c1c20] sm:px-6 sm:py-8">
      <div className="mx-auto w-full max-w-7xl space-y-6">
        <header className="overflow-hidden rounded-3xl border border-[#dccbc4] bg-[#fffaf7] shadow-sm">
          <div className="bg-gradient-to-br from-[#332e34] to-[#593640] p-6 text-white sm:p-9">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-white/60">
              Retailigent · Administration
            </p>
            <div className="mt-3 flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
              <div>
                <h1 className="text-3xl font-bold sm:text-4xl">
                  Staff workspace
                </h1>
                <p className="mt-3 max-w-2xl text-sm leading-6 text-white/75 sm:text-base">
                  One place to manage customer support, review feedback, and
                  monitor retail demand and inventory.
                </p>
              </div>
              <button
                type="button"
                onClick={() => void loadOverview()}
                disabled={loading}
                className="inline-flex min-h-11 shrink-0 items-center justify-center rounded-xl border border-white/20 bg-white/10 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-white/20 disabled:cursor-wait disabled:opacity-60"
              >
                {loading ? "Refreshing…" : "↻ Refresh overview"}
              </button>
            </div>
          </div>

          <div className="flex flex-col gap-1 px-6 py-4 text-xs text-[#756369] sm:flex-row sm:items-center sm:justify-between sm:px-9">
            <span>
              {loading
                ? "Updating workspace data…"
                : data.errors.length
                  ? `${data.errors.length} data source(s) need attention`
                  : "Connected data sources loaded"}
            </span>
            <span>
              {lastUpdated ? `Last checked ${lastUpdated}` : "Not yet refreshed"}
            </span>
          </div>
        </header>

        {data.errors.length > 0 && (
          <section
            role="status"
            className="rounded-2xl border border-amber-300 bg-amber-50 p-5"
          >
            <h2 className="font-semibold text-amber-950">
              Some overview data is unavailable
            </h2>
            <ul className="mt-2 space-y-1 text-sm leading-6 text-amber-900">
              {data.errors.map((error) => (
                <li key={error}>{error}</li>
              ))}
            </ul>
            <p className="mt-3 text-xs text-amber-800">
              Open the relevant section or refresh after checking the backend
              connection and staff permissions.
            </p>
          </section>
        )}

        <section>
          <div className="mb-4">
            <h2 className="text-xl font-bold">At a glance</h2>
            <p className="mt-1 text-sm text-[#756369]">
              Live summaries from the existing staff APIs.
            </p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard
              label="Open support tickets"
              value={openTickets}
              description={
                priorityTickets === null
                  ? "Active customer support queue"
                  : `${priorityTickets} open ticket(s) marked urgent or high priority`
              }
              href="/admin/tickets"
              accent={priorityTickets !== null && priorityTickets > 0 ? "danger" : "default"}
            />
            <MetricCard
              label="Feedback awaiting review"
              value={data.feedbackCount}
              description="Feedback flagged for staff classification review"
              href="/admin/feedback"
              accent={
                data.feedbackCount !== null && data.feedbackCount > 0
                  ? "warning"
                  : "default"
              }
            />
            <MetricCard
              label="Low-stock variants"
              value={data.lowStock}
              description="Low-stock counts across the returned branch summaries"
              href="/admin/analytics"
              accent={data.lowStock !== null && data.lowStock > 0 ? "warning" : "default"}
            />
            <MetricCard
              label="Out-of-stock variants"
              value={data.outOfStock}
              description="Out-of-stock counts across the returned branch summaries"
              href="/admin/analytics"
              accent={data.outOfStock !== null && data.outOfStock > 0 ? "danger" : "default"}
            />
          </div>
        </section>

        <section>
          <div className="mb-4">
            <h2 className="text-xl font-bold">Workspace tools</h2>
            <p className="mt-1 text-sm text-[#756369]">
              Choose an area to continue working.
            </p>
          </div>
          <div className="grid gap-4 lg:grid-cols-3">
            <WorkspaceCard
              eyebrow="Customer care"
              title="Support tickets"
              description="Review customer escalations, prioritize urgent cases, update ticket status, and respond to customers."
              href="/admin/tickets"
              details={[
                "Prioritized ticket queue",
                "Ticket status and priority updates",
                "Staff replies and conversation context",
              ]}
            />
            <WorkspaceCard
              eyebrow="Quality & experience"
              title="Feedback review"
              description="Inspect feedback flagged for review and correct its category or sentiment classification."
              href="/admin/feedback"
              details={[
                "AI-classified feedback",
                "Staff category and sentiment corrections",
                "Review queue workflow",
              ]}
            />
            <WorkspaceCard
              eyebrow="Retail operations"
              title="Retail analytics"
              description="Explore branch inventory summaries and available demand signals to help identify stock and product-interest patterns."
              href="/admin/analytics"
              details={[
                "Branch inventory summaries",
                "Low-stock and out-of-stock counts",
                "Demand and unavailable-search signals",
              ]}
            />
            <WorkspaceCard
              eyebrow="Staff intelligence"
              title="Ask analytics"
              description="Ask questions about recorded demand signals, branch inventory, and retail operations using the available analytics data."
              href="/admin/ask"
              details={[
                "Ask questions in natural language",
                "Ground answers in available analytics",
                "Identify data gaps and unavailable results",
              ]}
            />
          </div>
        </section>

        <footer className="rounded-2xl border border-[#dccbc4] bg-white/70 px-5 py-4 text-sm leading-6 text-[#756369]">
          <span className="font-semibold text-[#5e4a50]">Data note:</span>{" "}
          Inventory figures are totals across returned branch summaries and may
          count the same variant at different branches separately. Demand
          metrics depend on recorded demand signals; an empty result does not
          necessarily mean that customers have no unmet demand.
        </footer>
      </div>
    </main>
  );
}
