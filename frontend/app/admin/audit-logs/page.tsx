"use client";

import { Fragment, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { supabase } from "@/lib/supabase/client";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

const PAGE_SIZE = 25;

const ACTOR_TYPES = ["user", "staff", "agent", "system"] as const;

const ENTITY_TYPES = [
  "user_roles",
  "promotions",
  "branch_inventory",
  "reservations",
  "orders",
  "purchase_attempts",
  "feedback",
  "support_escalations",
] as const;

type AuditEntry = {
  id: string;
  created_at: string;
  actor_user_id: string | null;
  actor_name: string | null;
  actor_type: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  before_data: Record<string, unknown> | null;
  after_data: Record<string, unknown> | null;
  metadata: Record<string, unknown>;
};

type AuditResponse = {
  entries: AuditEntry[];
  total: number;
  limit: number;
  offset: number;
};

type Filters = {
  action: string;
  entityType: string;
  actorType: string;
  since: string;
  until: string;
};

const EMPTY_FILTERS: Filters = {
  action: "",
  entityType: "",
  actorType: "",
  since: "",
  until: "",
};

async function request<T>(path: string): Promise<T> {
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.access_token) {
    throw new Error("Sign in with an administrator account.");
  }

  const response = await fetch(`${API_URL}${path}`, {
    headers: { Authorization: `Bearer ${session.access_token}` },
    cache: "no-store",
  });

  if (!response.ok) {
    let message = `Request failed (${response.status}).`;

    if (response.status === 403) {
      message = "Only administrators can view the audit log.";
    } else {
      try {
        const payload = await response.json();
        if (typeof payload.detail === "string") {
          message = payload.detail;
        }
      } catch {
        // Keep the HTTP status message.
      }
    }

    throw new Error(message);
  }

  return (await response.json()) as T;
}

function prettyDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function label(value: string): string {
  return value.replace(/_/g, " ");
}

function actorLabel(entry: AuditEntry): string {
  if (entry.actor_name) return entry.actor_name;
  if (entry.actor_user_id) return `${entry.actor_user_id.slice(0, 8)}…`;
  return entry.actor_type === "system" ? "System / unattributed" : "Unknown";
}

function typeStyle(type: string): string {
  switch (type) {
    case "staff":
      return "bg-[#f3e3e6] text-[#7f2a3c]";
    case "system":
      return "bg-[#ece8ee] text-[#4a3f55]";
    case "agent":
      return "bg-[#e3eef3] text-[#244a5c]";
    default:
      return "bg-[#efe9e2] text-[#5e4a50]";
  }
}

function Json({ title, data }: { title: string; data: unknown }) {
  return (
    <div className="min-w-0">
      <p className="text-xs font-semibold uppercase tracking-wide text-[#756369]">
        {title}
      </p>
      <pre className="mt-1 max-h-64 overflow-auto rounded-xl border border-[#dccbc4] bg-white p-3 text-xs leading-5 text-[#2c1c20]">
        {data ? JSON.stringify(data, null, 2) : "—"}
      </pre>
    </div>
  );
}

export default function AuditLogsPage() {
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [applied, setApplied] = useState<Filters>(EMPTY_FILTERS);
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<AuditResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);

    const params = new URLSearchParams({
      limit: String(PAGE_SIZE),
      offset: String(offset),
    });

    if (applied.action.trim()) params.set("action", applied.action.trim());
    if (applied.entityType) params.set("entity_type", applied.entityType);
    if (applied.actorType) params.set("actor_type", applied.actorType);
    if (applied.since) {
      params.set("since", new Date(`${applied.since}T00:00:00`).toISOString());
    }
    if (applied.until) {
      params.set("until", new Date(`${applied.until}T23:59:59`).toISOString());
    }

    try {
      setData(
        await request<AuditResponse>(
          `/api/v1/admin/audit-logs?${params.toString()}`,
        ),
      );
    } catch (caught) {
      setData(null);
      setError(
        caught instanceof Error
          ? caught.message
          : "The audit log could not be loaded.",
      );
    } finally {
      setLoading(false);
    }
  }, [applied, offset]);

  useEffect(() => {
    queueMicrotask(() => {
      void load();
    });
  }, [load]);

  function applyFilters() {
    setOpenId(null);
    setOffset(0);
    setApplied(filters);
  }

  function clearFilters() {
    setFilters(EMPTY_FILTERS);
    setApplied(EMPTY_FILTERS);
    setOffset(0);
    setOpenId(null);
  }

  const total = data?.total ?? 0;
  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + PAGE_SIZE, total);

  const inputStyle =
    "min-h-11 w-full rounded-xl border border-[#dccbc4] bg-white px-3 text-sm text-[#2c1c20] outline-none focus:border-[#7f2a3c]";

  return (
    <main className="min-h-[calc(100dvh-4rem)] bg-[#f1e6de] px-4 py-6 text-[#2c1c20] sm:px-6 sm:py-8">
      <div className="mx-auto w-full max-w-7xl space-y-6">
        <header className="overflow-hidden rounded-3xl border border-[#dccbc4] bg-[#fffaf7] shadow-sm">
          <div className="bg-gradient-to-br from-[#332e34] to-[#593640] p-6 text-white sm:p-9">
            <Link
              href="/admin"
              className="text-xs font-semibold uppercase tracking-[0.2em] text-white/60 hover:text-white"
            >
              ← Retailigent · Administration
            </Link>
            <h1 className="mt-3 text-3xl font-bold sm:text-4xl">Audit log</h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-white/75 sm:text-base">
              Every role change, promotion edit, stock correction, reservation,
              purchase and support or feedback change, with before and after
              values. The log is append-only and cannot be edited or deleted.
            </p>
          </div>
        </header>

        <section className="rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-5 sm:p-6">
          <form
            onSubmit={(event) => {
              event.preventDefault();
              applyFilters();
            }}
            className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5"
          >
            <label className="text-sm font-semibold text-[#5e4a50]">
              Action starts with
              <input
                value={filters.action}
                onChange={(e) =>
                  setFilters({ ...filters, action: e.target.value })
                }
                placeholder="e.g. role_ or purchase_"
                className={`${inputStyle} mt-1 font-normal`}
              />
            </label>

            <label className="text-sm font-semibold text-[#5e4a50]">
              Record type
              <select
                value={filters.entityType}
                onChange={(e) =>
                  setFilters({ ...filters, entityType: e.target.value })
                }
                className={`${inputStyle} mt-1 font-normal`}
              >
                <option value="">All</option>
                {ENTITY_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {label(type)}
                  </option>
                ))}
              </select>
            </label>

            <label className="text-sm font-semibold text-[#5e4a50]">
              Actor type
              <select
                value={filters.actorType}
                onChange={(e) =>
                  setFilters({ ...filters, actorType: e.target.value })
                }
                className={`${inputStyle} mt-1 font-normal`}
              >
                <option value="">All</option>
                {ACTOR_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </select>
            </label>

            <label className="text-sm font-semibold text-[#5e4a50]">
              From
              <input
                type="date"
                value={filters.since}
                onChange={(e) =>
                  setFilters({ ...filters, since: e.target.value })
                }
                className={`${inputStyle} mt-1 font-normal`}
              />
            </label>

            <label className="text-sm font-semibold text-[#5e4a50]">
              To
              <input
                type="date"
                value={filters.until}
                onChange={(e) =>
                  setFilters({ ...filters, until: e.target.value })
                }
                className={`${inputStyle} mt-1 font-normal`}
              />
            </label>

            <div className="flex flex-wrap gap-3 sm:col-span-2 lg:col-span-5">
              <button
                type="submit"
                disabled={loading}
                className="inline-flex min-h-11 items-center justify-center rounded-xl bg-[#7f2a3c] px-5 text-sm font-semibold text-white transition hover:bg-[#652131] disabled:cursor-wait disabled:opacity-60"
              >
                Apply filters
              </button>
              <button
                type="button"
                onClick={clearFilters}
                className="inline-flex min-h-11 items-center justify-center rounded-xl border border-[#dccbc4] bg-white px-5 text-sm font-semibold text-[#5e4a50] transition hover:bg-[#f7efe9]"
              >
                Clear
              </button>
              <button
                type="button"
                onClick={() => void load()}
                disabled={loading}
                className="inline-flex min-h-11 items-center justify-center rounded-xl border border-[#dccbc4] bg-white px-5 text-sm font-semibold text-[#5e4a50] transition hover:bg-[#f7efe9] disabled:opacity-60"
              >
                ↻ Refresh
              </button>
            </div>
          </form>
        </section>

        {error && (
          <section
            role="alert"
            className="rounded-2xl border border-red-300 bg-red-50 p-5 text-sm text-red-900"
          >
            {error}
          </section>
        )}

        <section className="overflow-hidden rounded-2xl border border-[#dccbc4] bg-white shadow-sm">
          <div className="flex flex-col gap-1 border-b border-[#dccbc4] px-5 py-3 text-sm text-[#756369] sm:flex-row sm:items-center sm:justify-between">
            <span>
              {loading
                ? "Loading audit log…"
                : data
                  ? `Showing ${from}–${to} of ${new Intl.NumberFormat().format(total)} entries`
                  : "No data"}
            </span>
            <span>Newest first</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead className="bg-[#fffaf7] text-xs uppercase tracking-wide text-[#756369]">
                <tr>
                  <th className="px-5 py-3 font-semibold">When</th>
                  <th className="px-5 py-3 font-semibold">Who</th>
                  <th className="px-5 py-3 font-semibold">Action</th>
                  <th className="px-5 py-3 font-semibold">Record</th>
                  <th className="px-5 py-3 font-semibold">
                    <span className="sr-only">Details</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {data?.entries.map((entry) => {
                  const isOpen = openId === entry.id;

                  return (
                    <Fragment key={entry.id}>
                      <tr className="border-t border-[#efe4dc] align-top">
                        <td className="whitespace-nowrap px-5 py-3 text-[#5e4a50]">
                          {prettyDate(entry.created_at)}
                        </td>
                        <td className="px-5 py-3">
                          <p className="font-semibold">{actorLabel(entry)}</p>
                          <span
                            className={`mt-1 inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${typeStyle(entry.actor_type)}`}
                          >
                            {entry.actor_type}
                          </span>
                        </td>
                        <td className="px-5 py-3 font-semibold">
                          {label(entry.action)}
                        </td>
                        <td className="px-5 py-3 text-[#5e4a50]">
                          <p>{label(entry.entity_type)}</p>
                          {entry.entity_id && (
                            <p className="font-mono text-xs text-[#756369]">
                              {entry.entity_id.slice(0, 8)}…
                            </p>
                          )}
                        </td>
                        <td className="px-5 py-3 text-right">
                          <button
                            type="button"
                            aria-expanded={isOpen}
                            onClick={() => setOpenId(isOpen ? null : entry.id)}
                            className="min-h-11 rounded-lg px-3 text-sm font-semibold text-[#7f2a3c] hover:underline"
                          >
                            {isOpen ? "Hide" : "Details"}
                          </button>
                        </td>
                      </tr>

                      {isOpen && (
                        <tr className="bg-[#fffaf7]">
                          <td colSpan={5} className="px-5 py-4">
                            <div className="grid gap-4 md:grid-cols-3">
                              <Json title="Before" data={entry.before_data} />
                              <Json title="After" data={entry.after_data} />
                              <Json title="Metadata" data={entry.metadata} />
                            </div>
                            <p className="mt-3 break-all font-mono text-xs text-[#756369]">
                              Entry {entry.id}
                              {entry.entity_id
                                ? ` · record ${entry.entity_id}`
                                : ""}
                              {entry.actor_user_id
                                ? ` · actor ${entry.actor_user_id}`
                                : ""}
                            </p>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}

                {!loading && data && data.entries.length === 0 && (
                  <tr>
                    <td
                      colSpan={5}
                      className="px-5 py-10 text-center text-[#756369]"
                    >
                      No audit entries match these filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between gap-3 border-t border-[#dccbc4] px-5 py-3">
            <button
              type="button"
              disabled={loading || offset === 0}
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              className="min-h-11 rounded-xl border border-[#dccbc4] bg-white px-4 text-sm font-semibold text-[#5e4a50] transition hover:bg-[#f7efe9] disabled:cursor-not-allowed disabled:opacity-50"
            >
              ← Newer
            </button>
            <button
              type="button"
              disabled={loading || offset + PAGE_SIZE >= total}
              onClick={() => setOffset(offset + PAGE_SIZE)}
              className="min-h-11 rounded-xl border border-[#dccbc4] bg-white px-4 text-sm font-semibold text-[#5e4a50] transition hover:bg-[#f7efe9] disabled:cursor-not-allowed disabled:opacity-50"
            >
              Older →
            </button>
          </div>
        </section>
      </div>
    </main>
  );
}
