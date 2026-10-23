"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { supabase } from "@/lib/supabase/client";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

type DemandRow = {
  product_id?: string | null;
  variant_id?: string | null;
  branch_id?: string | null;
  product_name?: string | null;
  color_name?: string | null;
  size_name?: string | null;
  branch_name?: string | null;
  signal_type?: string | null;
  requested_size?: string | null;
  requested_color?: string | null;
  demand_signal_count?: number | string | null;
  unfulfilled_signal_count?: number | string | null;
  affected_branches?: number | string | null;
  signal_count?: number | string | null;
  latest_signal_at?: string | null;
};

type InventoryRow = {
  branch_id?: string | null;
  branch_name?: string | null;
  branch_city?: string | null;
  total_variants?: number | string | null;
  available_variants?: number | string | null;
  low_stock_variants?: number | string | null;
  out_of_stock_variants?: number | string | null;
};

type DemandResponse = {
  high_interest_low_availability: DemandRow[];
  unavailable_searches: DemandRow[];
  product_demand_availability: DemandRow[];
  count?: Record<string, number>;
};

type InventoryResponse = {
  branches: InventoryRow[];
  count?: Record<string, number>;
};

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
    let message = "Analytics data could not be loaded.";

    try {
      const payload = await response.json();
      if (typeof payload.detail === "string") {
        message = payload.detail;
      }
    } catch {
      // Retain the fallback for non-JSON errors.
    }

    throw new Error(message);
  }

  return (await response.json()) as T;
}

function numberValue(value?: number | string | null): number {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function displayNumber(value: number): string {
  return new Intl.NumberFormat().format(value);
}

function displayDate(value?: string | null): string {
  if (!value) return "Not available";
  const date = new Date(value);

  return Number.isNaN(date.getTime())
    ? "Not available"
    : date.toLocaleString();
}

function shortId(value?: string | null): string {
  if (!value) return "Not linked";
  return value.length > 12 ? `${value.slice(0, 8)}…` : value;
}

function Metric({
  label,
  value,
  description,
}: {
  label: string;
  value: number;
  description: string;
}) {
  return (
    <section className="rounded-2xl border border-[#dccbc4] bg-white p-3 sm:p-4">
      <p className="text-sm font-medium text-[#756369]">{label}</p>
      <p className="mt-2 text-3xl font-bold tabular-nums">
        {displayNumber(value)}
      </p>
      <p className="mt-2 text-xs leading-5 text-[#756369]">
        {description}
      </p>
    </section>
  );
}

function SectionHeading({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="mb-4">
      <h2 className="text-xl font-bold">{title}</h2>
      <p className="mt-1 text-sm leading-6 text-[#756369]">
        {description}
      </p>
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <p className="rounded-xl border border-dashed border-[#dccbc4] bg-white p-5 text-sm text-[#756369]">
      {message}
    </p>
  );
}

export default function AdminAnalyticsPage() {
  const [demand, setDemand] = useState<DemandResponse | null>(null);
  const [inventory, setInventory] = useState<InventoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  const loadAnalytics = useCallback(async () => {
    setLoading(true);
    setLoadError(null);

    try {
      const [demandResult, inventoryResult] = await Promise.all([
        request<DemandResponse>("/api/v1/analytics/demand?limit=100"),
        request<InventoryResponse>("/api/v1/analytics/inventory?limit=100"),
      ]);

      setDemand(demandResult);
      setInventory(inventoryResult);
      setLastUpdated(new Date().toLocaleString());
    } catch (caught) {
      setLoadError(
        caught instanceof Error
          ? caught.message
          : "Analytics data could not be loaded.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadAnalytics();
    }, 0);

    return () => window.clearTimeout(timer);
  }, [loadAnalytics]);

  const interestRows = demand?.high_interest_low_availability ?? [];
  const unavailableRows = demand?.unavailable_searches ?? [];
  const productRows = demand?.product_demand_availability ?? [];
  const branchRows = inventory?.branches ?? [];

  const demandChartData = [...productRows]
    .sort(
      (a, b) =>
        numberValue(b.unfulfilled_signal_count) -
        numberValue(a.unfulfilled_signal_count),
    )
    .slice(0, 8)
    .map((row) => ({
      name: row.product_name ?? ([row.color_name, row.size_name].filter(Boolean).join(' / ') || shortId(row.variant_id ?? row.product_id)),
      demand: numberValue(row.demand_signal_count),
      unfulfilled: numberValue(row.unfulfilled_signal_count),
    }));

  const branchChartData = [...branchRows]
    .sort(
      (a, b) =>
        numberValue(b.out_of_stock_variants) -
        numberValue(a.out_of_stock_variants),
    )
    .slice(0, 8)
    .map((row) => ({
      name: row.branch_name ?? shortId(row.branch_id),
      available: numberValue(row.available_variants),
      lowStock: numberValue(row.low_stock_variants),
      outOfStock: numberValue(row.out_of_stock_variants),
    }));


  const totalDemandSignals = productRows.reduce(
    (sum, row) => sum + numberValue(row.demand_signal_count),
    0,
  );

  const outstandingSignals = productRows.reduce(
    (sum, row) => sum + numberValue(row.unfulfilled_signal_count),
    0,
  );

  const lowStockVariants = branchRows.reduce(
    (sum, row) => sum + numberValue(row.low_stock_variants),
    0,
  );

  const outOfStockVariants = branchRows.reduce(
    (sum, row) => sum + numberValue(row.out_of_stock_variants),
    0,
  );

  const inventoryDistribution = [
    {
      name: "Available",
      value: branchRows.reduce(
        (sum, row) => sum + numberValue(row.available_variants),
        0,
      ),
    },
    {
      name: "Low stock",
      value: lowStockVariants,
    },
    {
      name: "Out of stock",
      value: outOfStockVariants,
    },
  ].filter((item) => item.value > 0);

  return (
    <main className="min-h-[calc(100dvh-4rem)] bg-[#f1e6de] px-3 py-4 text-[#2c1c20] sm:px-5 sm:py-5 xl:px-6 xl:py-6">
      <div className="mx-auto w-full max-w-[96rem] space-y-4">
        <header className="rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-4 shadow-sm sm:p-5 xl:p-6">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#7f2a3c]">
            Staff workspace
          </p>

          <h1 className="mt-1 text-2xl font-bold sm:text-3xl xl:text-4xl">
            Retail analytics
          </h1>

          <p className="mt-2 max-w-3xl text-sm leading-5 text-[#756369]">
            Review recorded product demand, unavailable searches, and branch
            inventory conditions. Analytics access is enforced by the backend.
          </p>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => void loadAnalytics()}
              disabled={loading}
              className="min-h-11 rounded-xl bg-[#7f2a3c] px-5 py-2 text-sm font-semibold text-white hover:bg-[#672130] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? "Refreshing…" : "Refresh analytics"}
            </button>

            <Link
              href="/admin/tickets"
              className="inline-flex min-h-11 items-center rounded-xl border border-[#dccbc4] px-4 py-2 text-sm font-semibold hover:bg-[#f7ece7]"
            >
              Support tickets
            </Link>

            <Link
              href="/admin/feedback"
              className="inline-flex min-h-11 items-center rounded-xl border border-[#dccbc4] px-4 py-2 text-sm font-semibold hover:bg-[#f7ece7]"
            >
              Feedback review
            </Link>
          </div>

          <p className="mt-4 text-xs text-[#756369]" aria-live="polite">
            {loading
              ? "Loading analytics…"
              : lastUpdated
                ? `Last refreshed: ${lastUpdated}`
                : "Analytics have not loaded."}
          </p>
        </header>

        {loadError && (
          <section
            role="alert"
            className="rounded-2xl border border-red-300 bg-red-50 p-5 text-sm text-red-900"
          >
            <p className="font-semibold">Unable to load analytics</p>
            <p className="mt-2">{loadError}</p>
            <p className="mt-2">
              Check that the backend is running, the database views are
              available, and your account has staff or admin access.
            </p>
          </section>
        )}

        <section>
          <SectionHeading
            title="Demand and inventory overview"
            description="Summary calculated from the rows returned by the analytics views. These figures are not guaranteed to represent every record in the database."
          />

          <div className="grid grid-cols-1 gap-3 min-[480px]:grid-cols-2 xl:grid-cols-4">
            <Metric
              label="Demand signals"
              value={totalDemandSignals}
              description="Sum of demand counts in the returned product rows."
            />
            <Metric
              label="Unfulfilled demand"
              value={outstandingSignals}
              description="Unfulfilled signal counts in the returned product rows."
            />
            <Metric
              label="Low-stock variants"
              value={lowStockVariants}
              description="Sum of low-stock variants across returned branches."
            />
            <Metric
              label="Out-of-stock variants"
              value={outOfStockVariants}
              description="Sum of out-of-stock variants across returned branches."
            />
          </div>
        </section>


        <section className="space-y-3">
          <SectionHeading
            title="Visual analytics"
            description="Compare recorded product demand and branch stock conditions at a glance."
          />

          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <div className="rounded-2xl border border-[#dccbc4] bg-white p-3 sm:p-4">
              <h3 className="mb-1 text-base font-semibold text-[#38272b]">
                Product demand vs. unfulfilled
              </h3>
              <p className="mb-4 text-sm text-[#756369]">
                Top 8 variants ranked by unfulfilled demand signals.
              </p>
              {loading && !demand ? (
                <EmptyState message="Loading demand chart…" />
              ) : demandChartData.length === 0 ? (
                <EmptyState message="No demand data available to chart." />
              ) : (
                <div className="h-64 w-full sm:h-60 xl:h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={demandChartData}
                      margin={{ top: 8, right: 12, left: 0, bottom: 36 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis
                        dataKey="name"
                        angle={-25}
                        textAnchor="end"
                        interval={0}
                        tick={{ fontSize: 11 }}
                      />
                      <YAxis allowDecimals={false} />
                      <Tooltip />
                      <Legend />
                      <Bar
                        dataKey="demand"
                        name="Total demand"
                        fill="#98736d"
                        radius={[4, 4, 0, 0]}
                      />
                      <Bar
                        dataKey="unfulfilled"
                        name="Unfulfilled"
                        fill="#c65d54"
                        radius={[4, 4, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>

            <div className="rounded-2xl border border-[#dccbc4] bg-white p-3 sm:p-4">
              <h3 className="mb-1 text-base font-semibold text-[#38272b]">
                Branch stock conditions
              </h3>
              <p className="mb-4 text-sm text-[#756369]">
                Top 8 branches ranked by out-of-stock variants.
              </p>
              {loading && !inventory ? (
                <EmptyState message="Loading inventory chart…" />
              ) : branchChartData.length === 0 ? (
                <EmptyState message="No branch inventory data available to chart." />
              ) : (
                <div className="h-64 w-full sm:h-60 xl:h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={branchChartData}
                      layout="vertical" margin={{ top: 8, right: 12, left: 0, bottom: 8 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis type="number" allowDecimals={false} />
                      <YAxis type="category" dataKey="name" width={100} tick={{ fontSize: 10 }} interval={0} />
                      <Tooltip />
                      <Legend />
                      <Bar
                        dataKey="available"
                        name="Available variants"
                        fill="#64866c"
                        radius={[0, 4, 4, 0]}
                      />
                      <Bar
                        dataKey="lowStock"
                        name="Low-stock variants"
                        fill="#d6a64f"
                        radius={[0, 4, 4, 0]}
                      />
                      <Bar
                        dataKey="outOfStock"
                        name="Out-of-stock variants"
                        fill="#c65d54"
                        radius={[0, 4, 4, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>

            <div className="rounded-2xl border border-[#dccbc4] bg-white p-3 sm:p-4 lg:col-span-2">
              <h3 className="mb-1 text-base font-semibold text-[#38272b]">
                Inventory distribution
              </h3>
              <p className="mb-4 text-sm text-[#756369]">
                Aggregated variant counts across the returned branch summaries.
              </p>
              {loading && !inventory ? (
                <EmptyState message="Loading inventory distribution…" />
              ) : inventoryDistribution.length === 0 ? (
                <EmptyState message="No inventory distribution data available to chart." />
              ) : (
                <div className="h-64 w-full sm:h-60 xl:h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={inventoryDistribution}
                        dataKey="value"
                        nameKey="name"
                        cx="50%"
                        cy="45%"
                        outerRadius="32%"
                      >
                        {inventoryDistribution.map((entry) => (
                          <Cell
                            key={entry.name}
                            fill={
                              entry.name === "Available"
                                ? "#64866c"
                                : entry.name === "Low stock"
                                  ? "#d6a64f"
                                  : "#c65d54"
                            }
                          />
                        ))}
                      </Pie>
                      <Tooltip
                        formatter={(value) => displayNumber(Number(value))}
                      />
                    </PieChart>
                  </ResponsiveContainer>


                  <div className="mt-2 flex flex-wrap justify-center gap-x-4 gap-y-2 px-1 text-sm">
                    {inventoryDistribution.map((entry) => (
                      <div key={entry.name} className="flex min-w-0 items-center gap-2">
                        <span
                          aria-hidden="true"
                          className="h-2.5 w-2.5 shrink-0 rounded-full"
                          style={{
                            backgroundColor:
                              entry.name === "Available"
                                ? "#64866c"
                                : entry.name === "Low stock"
                                  ? "#d6a64f"
                                  : "#c65d54",
                          }}
                        />
                        <span className="break-words text-[#756369]">
                          {entry.name}: {displayNumber(Number(entry.value))}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

              )}
            </div>
          </div>
        </section>

        <section className="rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-5 sm:p-6">
          <SectionHeading
            title="High demand with availability concerns"
            description="Products, variants, and branches associated with outstanding demand signals."
          />

          {loading && !demand ? (
            <EmptyState message="Loading demand signals…" />
          ) : interestRows.length === 0 ? (
            <EmptyState message="No matching demand records were returned." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[650px] text-left text-sm">
                <thead>
                  <tr className="border-b border-[#dccbc4] text-[#756369]">
                    <th className="px-3 py-3 font-semibold">Product</th>
                    <th className="px-3 py-3 font-semibold">Variant</th>
                    <th className="px-3 py-3 font-semibold">Branch</th>
                    <th className="px-3 py-3 font-semibold">Demand signals</th>
                    <th className="px-3 py-3 font-semibold">Latest signal</th>
                  </tr>
                </thead>
                <tbody>
                  {interestRows.map((row, index) => (
                    <tr
                      key={`${row.product_id ?? "product"}-${row.variant_id ?? "variant"}-${row.branch_id ?? "branch"}-${index}`}
                      className="border-b border-[#eee1da] last:border-0"
                    >
                      <td className="px-3 py-3">{row.product_name ?? shortId(row.product_id)}</td>
                      <td className="px-3 py-3">{[row.color_name, row.size_name].filter(Boolean).join(" / ") || shortId(row.variant_id)}</td>
                      <td className="px-3 py-3">{row.branch_name ?? shortId(row.branch_id)}</td>
                      <td className="px-3 py-3 font-semibold">
                        {displayNumber(numberValue(row.unfulfilled_signal_count))}
                      </td>
                      <td className="px-3 py-3">
                        {displayDate(row.latest_signal_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-5 sm:p-6">
          <SectionHeading
            title="Unavailable search patterns"
            description="Recorded unavailable demand grouped by signal type, requested size, and requested color."
          />

          {loading && !demand ? (
            <EmptyState message="Loading unavailable searches…" />
          ) : unavailableRows.length === 0 ? (
            <EmptyState message="No unavailable search records were returned." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[500px] text-left text-sm">
                <thead>
                  <tr className="border-b border-[#dccbc4] text-[#756369]">
                    <th className="px-3 py-3 font-semibold">Signal type</th>
                    <th className="px-3 py-3 font-semibold">Size</th>
                    <th className="px-3 py-3 font-semibold">Color</th>
                    <th className="px-3 py-3 font-semibold">Signals</th>
                    <th className="px-3 py-3 font-semibold">Latest signal</th>
                  </tr>
                </thead>
                <tbody>
                  {unavailableRows.map((row, index) => (
                    <tr
                      key={`${row.signal_type ?? "signal"}-${row.requested_size ?? "size"}-${row.requested_color ?? "color"}-${index}`}
                      className="border-b border-[#eee1da] last:border-0"
                    >
                      <td className="px-3 py-3">
                        {row.signal_type ?? "Unknown"}
                      </td>
                      <td className="px-3 py-3">
                        {row.requested_size ?? "Not specified"}
                      </td>
                      <td className="px-3 py-3">
                        {row.requested_color ?? "Not specified"}
                      </td>
                      <td className="px-3 py-3 font-semibold">
                        {displayNumber(numberValue(row.signal_count))}
                      </td>
                      <td className="px-3 py-3">
                        {displayDate(row.latest_signal_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-5 sm:p-6">
          <SectionHeading
            title="Product demand"
            description="Demand volume and the number of affected branches for each returned product variant."
          />

          {loading && !demand ? (
            <EmptyState message="Loading product demand…" />
          ) : productRows.length === 0 ? (
            <EmptyState message="No product demand records were returned." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[600px] text-left text-sm">
                <thead>
                  <tr className="border-b border-[#dccbc4] text-[#756369]">
                    <th className="px-3 py-3 font-semibold">Product</th>
                    <th className="px-3 py-3 font-semibold">Variant</th>
                    <th className="px-3 py-3 font-semibold">Demand signals</th>
                    <th className="px-3 py-3 font-semibold">Unfulfilled</th>
                    <th className="px-3 py-3 font-semibold">Affected branches</th>
                  </tr>
                </thead>
                <tbody>
                  {productRows.map((row, index) => (
                    <tr
                      key={`${row.product_id ?? "product"}-${row.variant_id ?? "variant"}-${index}`}
                      className="border-b border-[#eee1da] last:border-0"
                    >
                      <td className="px-3 py-3">{row.product_name ?? shortId(row.product_id)}</td>
                      <td className="px-3 py-3">{[row.color_name, row.size_name].filter(Boolean).join(" / ") || shortId(row.variant_id)}</td>
                      <td className="px-3 py-3">
                        {displayNumber(numberValue(row.demand_signal_count))}
                      </td>
                      <td className="px-3 py-3 font-semibold">
                        {displayNumber(numberValue(row.unfulfilled_signal_count))}
                      </td>
                      <td className="px-3 py-3">
                        {displayNumber(numberValue(row.affected_branches))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-5 sm:p-6">
          <SectionHeading
            title="Branch inventory"
            description="Variant availability by branch, based on the existing inventory summary view."
          />

          {loading && !inventory ? (
            <EmptyState message="Loading branch inventory…" />
          ) : branchRows.length === 0 ? (
            <EmptyState message="No branch inventory records were returned." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[600px] text-left text-sm">
                <thead>
                  <tr className="border-b border-[#dccbc4] text-[#756369]">
                    <th className="px-3 py-3 font-semibold">Branch</th>
                    <th className="px-3 py-3 font-semibold">Total variants</th>
                    <th className="px-3 py-3 font-semibold">Available</th>
                    <th className="px-3 py-3 font-semibold">Low stock</th>
                    <th className="px-3 py-3 font-semibold">Out of stock</th>
                  </tr>
                </thead>
                <tbody>
                  {branchRows.map((row, index) => (
                    <tr
                      key={`${row.branch_id ?? "branch"}-${index}`}
                      className="border-b border-[#eee1da] last:border-0"
                    >
                      <td className="px-3 py-3">{row.branch_name ?? shortId(row.branch_id)}</td>
                      <td className="px-3 py-3">
                        {displayNumber(numberValue(row.total_variants))}
                      </td>
                      <td className="px-3 py-3">
                        {displayNumber(numberValue(row.available_variants))}
                      </td>
                      <td className="px-3 py-3 font-semibold">
                        {displayNumber(numberValue(row.low_stock_variants))}
                      </td>
                      <td className="px-3 py-3 font-semibold">
                        {displayNumber(numberValue(row.out_of_stock_variants))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <footer className="px-1 pb-2 text-xs leading-5 text-[#756369]">
          Figures reflect the rows returned by the backend endpoints and their
          database views. They may not represent complete historical totals.
        </footer>
      </div>
    </main>
  );
}
