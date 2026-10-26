"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { supabase } from "@/lib/supabase/client";

type PromotionRow = {
  id: string;
  name: string;
  product_id: string | null;
  variant_id: string | null;
  discount_type: "percentage" | "fixed";
  discount_value: number;
  starts_at: string;
  ends_at: string | null;
  priority: number;
  is_active: boolean;
  metadata: Record<string, unknown>;
  created_at: string;

  products:
    | {
        id: string;
        name: string;
      }
    | null;

  product_variants:
    | {
        id: string;
        sku: string;
        products:
          | {
              id: string;
              name: string;
            }
          | null;
      }
    | null;
};

type PromotionStatus =
  | "active"
  | "scheduled"
  | "expired"
  | "inactive";

function getPromotionStatus(
  promotion: PromotionRow,
): PromotionStatus {
  const now = Date.now();
  const startsAt = new Date(
    promotion.starts_at,
  ).getTime();

  const endsAt = promotion.ends_at
    ? new Date(promotion.ends_at).getTime()
    : null;

  if (
    endsAt !== null &&
    endsAt < now
  ) {
    return "expired";
  }

  if (startsAt > now) {
    return "scheduled";
  }

  if (promotion.is_active) {
    return "active";
  }

  return "inactive";
}

function statusStyles(status: PromotionStatus) {
  switch (status) {
    case "active":
      return "border-emerald-200 bg-emerald-50 text-emerald-700";

    case "scheduled":
      return "border-blue-200 bg-blue-50 text-blue-700";

    case "expired":
      return "border-slate-200 bg-slate-50 text-slate-600";

    case "inactive":
      return "border-amber-200 bg-amber-50 text-amber-700";
  }
}

function formatDate(value: string | null) {
  if (!value) {
    return "No end date";
  }

  return new Intl.DateTimeFormat("en-PK", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function discountLabel(
  promotion: PromotionRow,
) {
  if (
    promotion.discount_type ===
    "percentage"
  ) {
    return `${promotion.discount_value}%`;
  }

  return `PKR ${new Intl.NumberFormat(
    "en-PK",
  ).format(promotion.discount_value)}`;
}

function targetLabel(
  promotion: PromotionRow,
) {
  if (promotion.variant_id) {
    const productName =
      promotion.product_variants
        ?.products?.name;

    const sku =
      promotion.product_variants?.sku;

    if (productName && sku) {
      return `${productName} · ${sku}`;
    }

    return (
      sku ??
      productName ??
      "Specific variant"
    );
  }

  if (promotion.product_id) {
    return (
      promotion.products?.name ??
      "Specific product"
    );
  }

  return "Unknown target";
}

export default function AdminPromotionsPage() {
  const [rows, setRows] = useState<
    PromotionRow[]
  >([]);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] = useState<
    string | null
  >(null);

  const [query, setQuery] =
    useState("");

  const [statusFilter, setStatusFilter] =
    useState("all");

  const loadPromotions =
    useCallback(async () => {
      setLoading(true);
      setError(null);

      try {
        const {
          data: { session },
        } =
          await supabase.auth.getSession();

        if (!session) {
          throw new Error(
            "Please sign in with an authorized staff account.",
          );
        }

        const {
          data,
          error: promotionsError,
        } = await supabase
          .from("promotions")
          .select(`
            id,
            name,
            product_id,
            variant_id,
            discount_type,
            discount_value,
            starts_at,
            ends_at,
            priority,
            is_active,
            metadata,
            created_at,
            products (
              id,
              name
            ),
            product_variants (
              id,
              sku,
              products (
                id,
                name
              )
            )
          `)
          .order("starts_at", {
            ascending: false,
          });

        if (promotionsError) {
          throw promotionsError;
        }

        setRows(
          (data ?? []) as unknown as PromotionRow[],
        );
      } catch (caught) {
        setError(
          caught instanceof Error
            ? caught.message
            : "Could not load promotions.",
        );
      } finally {
        setLoading(false);
      }
    }, []);

  useEffect(() => {
    void loadPromotions();
  }, [loadPromotions]);

  const filteredRows = useMemo(() => {
    const normalized =
      query.trim().toLowerCase();

    return rows.filter((promotion) => {
      const status =
        getPromotionStatus(promotion);

      const matchesStatus =
        statusFilter === "all" ||
        status === statusFilter;

      const searchable = [
        promotion.name,
        targetLabel(promotion),
        promotion.discount_type,
      ]
        .join(" ")
        .toLowerCase();

      const matchesQuery =
        !normalized ||
        searchable.includes(normalized);

      return (
        matchesStatus &&
        matchesQuery
      );
    });
  }, [
    rows,
    query,
    statusFilter,
  ]);

  const summary = useMemo(() => {
    return rows.reduce(
      (result, promotion) => {
        const status =
          getPromotionStatus(promotion);

        result.total += 1;
        result[status] += 1;

        return result;
      },
      {
        total: 0,
        active: 0,
        scheduled: 0,
        expired: 0,
        inactive: 0,
      },
    );
  }, [rows]);

  return (
    <main className="min-h-screen bg-[#fffaf7] px-4 py-6 text-[#2c1c20] sm:px-6 sm:py-10">
      <div className="mx-auto max-w-7xl">
        <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#7f2a3c]">
              Retailigent · Staff
            </p>

            <h1 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">
              Promotions
            </h1>

            <p className="mt-3 max-w-2xl text-sm leading-6 text-[#756369] sm:text-base">
              Monitor active, scheduled,
              inactive, and expired promotions.
            </p>
          </div>

          <button
            type="button"
            onClick={() =>
              void loadPromotions()
            }
            disabled={loading}
            className="inline-flex min-h-11 items-center justify-center rounded-xl border border-[#d8c8c2] bg-white px-4 py-2 text-sm font-semibold text-[#5c454c] transition hover:bg-[#fff4f2] disabled:opacity-50"
          >
            {loading
              ? "Refreshing..."
              : "Refresh"}
          </button>
        </header>

        {error && (
          <section className="mt-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
            <p className="font-semibold">
              Could not load promotions
            </p>
            <p className="mt-1">
              {error}
            </p>
          </section>
        )}

        <section className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          <MetricCard
            title="Total"
            value={summary.total}
          />
          <MetricCard
            title="Active"
            value={summary.active}
          />
          <MetricCard
            title="Scheduled"
            value={summary.scheduled}
          />
          <MetricCard
            title="Inactive"
            value={summary.inactive}
          />
          <MetricCard
            title="Expired"
            value={summary.expired}
          />
        </section>

        <section className="mt-6 rounded-2xl border border-[#dccbc4] bg-white p-4 shadow-sm sm:p-5">
          <div className="grid gap-3 md:grid-cols-[1fr_220px]">
            <input
              type="search"
              value={query}
              onChange={(event) =>
                setQuery(
                  event.target.value,
                )
              }
              placeholder="Search promotion, product or SKU..."
              className="min-h-11 rounded-xl border border-[#d8c8c2] px-4 text-sm outline-none focus:border-[#7f2a3c] focus:ring-2 focus:ring-[#7f2a3c]/10"
            />

            <select
              value={statusFilter}
              onChange={(event) =>
                setStatusFilter(
                  event.target.value,
                )
              }
              className="min-h-11 rounded-xl border border-[#d8c8c2] bg-white px-3 text-sm outline-none focus:border-[#7f2a3c]"
            >
              <option value="all">
                All statuses
              </option>
              <option value="active">
                Active
              </option>
              <option value="scheduled">
                Scheduled
              </option>
              <option value="inactive">
                Inactive
              </option>
              <option value="expired">
                Expired
              </option>
            </select>
          </div>
        </section>

        <section className="mt-6 overflow-hidden rounded-2xl border border-[#dccbc4] bg-white shadow-sm">
          {loading ? (
            <div className="p-8 text-center text-sm text-[#756369]">
              Loading promotions...
            </div>
          ) : filteredRows.length ===
            0 ? (
            <div className="p-8 text-center">
              <p className="font-semibold">
                No promotions found
              </p>
              <p className="mt-2 text-sm text-[#756369]">
                Try changing the filters.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="border-b border-[#eee2dd] bg-[#fffaf7] text-xs uppercase tracking-wide text-[#756369]">
                  <tr>
                    <th className="px-5 py-4">
                      Promotion
                    </th>
                    <th className="px-5 py-4">
                      Target
                    </th>
                    <th className="px-5 py-4">
                      Discount
                    </th>
                    <th className="px-5 py-4">
                      Status
                    </th>
                    <th className="px-5 py-4">
                      Priority
                    </th>
                    <th className="px-5 py-4">
                      Starts
                    </th>
                    <th className="px-5 py-4">
                      Ends
                    </th>
                  </tr>
                </thead>

                <tbody className="divide-y divide-[#f1e7e2]">
                  {filteredRows.map(
                    (promotion) => {
                      const status =
                        getPromotionStatus(
                          promotion,
                        );

                      return (
                        <tr
                          key={
                            promotion.id
                          }
                          className="hover:bg-[#fffaf7]/60"
                        >
                          <td className="px-5 py-4">
                            <p className="font-semibold">
                              {
                                promotion.name
                              }
                            </p>
                            <p className="mt-1 font-mono text-[11px] text-[#9a858b]">
                              {promotion.id}
                            </p>
                          </td>

                          <td className="px-5 py-4 text-[#5e4a50]">
                            {targetLabel(
                              promotion,
                            )}
                          </td>

                          <td className="px-5 py-4 font-bold">
                            {discountLabel(
                              promotion,
                            )}
                          </td>

                          <td className="px-5 py-4">
                            <span
                              className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold capitalize ${statusStyles(
                                status,
                              )}`}
                            >
                              {status}
                            </span>
                          </td>

                          <td className="px-5 py-4 tabular-nums">
                            {
                              promotion.priority
                            }
                          </td>

                          <td className="whitespace-nowrap px-5 py-4 text-xs text-[#756369]">
                            {formatDate(
                              promotion.starts_at,
                            )}
                          </td>

                          <td className="whitespace-nowrap px-5 py-4 text-xs text-[#756369]">
                            {formatDate(
                              promotion.ends_at,
                            )}
                          </td>
                        </tr>
                      );
                    },
                  )}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <div className="mt-5 rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm leading-6 text-blue-900">
          <p className="font-semibold">
            Security note
          </p>
          <p className="mt-1">
            This page intentionally performs
            staff-side reads only. Promotion
            creation and updates should remain
            backend-controlled so Phase 16
            service-role security is not bypassed.
          </p>
        </div>

        <p className="mt-4 text-sm text-[#756369]">
          Showing {filteredRows.length} of{" "}
          {rows.length} promotions.
        </p>
      </div>
    </main>
  );
}

function MetricCard({
  title,
  value,
}: {
  title: string;
  value: number;
}) {
  return (
    <article className="rounded-2xl border border-[#dccbc4] bg-white p-5 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-wide text-[#756369]">
        {title}
      </p>
      <p className="mt-3 text-3xl font-bold tabular-nums">
        {new Intl.NumberFormat().format(
          value,
        )}
      </p>
    </article>
  );
}