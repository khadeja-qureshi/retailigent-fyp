"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { supabase } from "@/lib/supabase/client";

type InventoryRow = {
  id: string;
  branch_id: string;
  variant_id: string;
  on_hand_quantity: number;
  reserved_quantity: number;
  safety_stock: number;
  available_quantity: number;
  updated_at: string;
  branches:
    | {
        id: string;
        name: string;
        city: string | null;
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
        colors:
          | {
              name: string;
            }
          | null;
        sizes:
          | {
              name: string;
            }
          | null;
      }
    | null;
};

function getStockStatus(row: InventoryRow) {
  if (row.available_quantity <= 0) {
    return {
      label: "Out of stock",
      className: "bg-red-50 text-red-700 border-red-200",
    };
  }

  if (row.available_quantity <= 2) {
    return {
      label: "Low stock",
      className: "bg-amber-50 text-amber-700 border-amber-200",
    };
  }

  return {
    label: "Available",
    className: "bg-emerald-50 text-emerald-700 border-emerald-200",
  };
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-PK", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export default function AdminInventoryPage() {
  const [rows, setRows] = useState<InventoryRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [query, setQuery] = useState("");
  const [branchFilter, setBranchFilter] = useState("all");
  const [stockFilter, setStockFilter] = useState("all");

  const loadInventory = useCallback(async () => {
    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();

      setLoading(true);
      setError(null);

      if (!session) {
        throw new Error("Please sign in with an authorized staff account.");
      }

      const { data, error: inventoryError } = await supabase
        .from("branch_inventory")
        .select(`
          id,
          branch_id,
          variant_id,
          on_hand_quantity,
          reserved_quantity,
          safety_stock,
          available_quantity,
          updated_at,
          branches (
            id,
            name,
            city
          ),
          product_variants (
            id,
            sku,
            products (
              id,
              name
            ),
            colors (
              name
            ),
            sizes (
              name
            )
          )
        `)
        .order("updated_at", {
          ascending: false,
        });

      if (inventoryError) {
        throw inventoryError;
      }

      setRows((data ?? []) as unknown as InventoryRow[]);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Could not load inventory.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void Promise.resolve().then(loadInventory);
  }, [loadInventory]);

  const branchOptions = useMemo(() => {
    const map = new Map<string, string>();

    rows.forEach((row) => {
      if (row.branches?.id) {
        map.set(
          row.branches.id,
          `${row.branches.name}${
            row.branches.city ? ` · ${row.branches.city}` : ""
          }`,
        );
      }
    });

    return Array.from(map.entries()).sort((a, b) =>
      a[1].localeCompare(b[1]),
    );
  }, [rows]);

  const filteredRows = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    return rows.filter((row) => {
      const productName =
        row.product_variants?.products?.name ?? "";

      const sku =
        row.product_variants?.sku ?? "";

      const color =
        row.product_variants?.colors?.name ?? "";

      const size =
        row.product_variants?.sizes?.name ?? "";

      const branch =
        row.branches?.name ?? "";

      const city =
        row.branches?.city ?? "";

      const matchesQuery =
        !normalizedQuery ||
        [
          productName,
          sku,
          color,
          size,
          branch,
          city,
        ].some((value) =>
          value.toLowerCase().includes(normalizedQuery),
        );

      const matchesBranch =
        branchFilter === "all" ||
        row.branch_id === branchFilter;

      const matchesStock =
        stockFilter === "all" ||
        (stockFilter === "out" &&
          row.available_quantity <= 0) ||
        (stockFilter === "low" &&
          row.available_quantity > 0 &&
          row.available_quantity <= 2) ||
        (stockFilter === "available" &&
          row.available_quantity > 2);

      return (
        matchesQuery &&
        matchesBranch &&
        matchesStock
      );
    });
  }, [
    rows,
    query,
    branchFilter,
    stockFilter,
  ]);

  const totals = useMemo(() => {
    return rows.reduce(
      (accumulator, row) => {
        accumulator.onHand += row.on_hand_quantity;
        accumulator.reserved += row.reserved_quantity;
        accumulator.available += row.available_quantity;

        if (row.available_quantity <= 0) {
          accumulator.outOfStock += 1;
        } else if (row.available_quantity <= 2) {
          accumulator.lowStock += 1;
        }

        return accumulator;
      },
      {
        onHand: 0,
        reserved: 0,
        available: 0,
        lowStock: 0,
        outOfStock: 0,
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
              Inventory
            </h1>

            <p className="mt-3 max-w-2xl text-sm leading-6 text-[#756369] sm:text-base">
              Monitor real branch-level inventory,
              reserved stock, safety stock, and sellable
              availability.
            </p>
          </div>

          <button
            type="button"
            onClick={() => void loadInventory()}
            disabled={loading}
            className="inline-flex min-h-11 items-center justify-center rounded-xl border border-[#d8c8c2] bg-white px-4 py-2 text-sm font-semibold text-[#5c454c] transition hover:bg-[#fff4f2] disabled:opacity-50"
          >
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </header>

        {error && (
          <div className="mt-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
            <p className="font-semibold">
              Could not load inventory
            </p>
            <p className="mt-1">{error}</p>
          </div>
        )}

        <section className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          <MetricCard
            title="On hand"
            value={totals.onHand}
          />
          <MetricCard
            title="Reserved"
            value={totals.reserved}
          />
          <MetricCard
            title="Available"
            value={totals.available}
          />
          <MetricCard
            title="Low stock"
            value={totals.lowStock}
          />
          <MetricCard
            title="Out of stock"
            value={totals.outOfStock}
          />
        </section>

        <section className="mt-6 rounded-2xl border border-[#dccbc4] bg-white p-4 shadow-sm sm:p-5">
          <div className="grid gap-3 lg:grid-cols-[1fr_240px_200px]">
            <input
              type="search"
              value={query}
              onChange={(event) =>
                setQuery(event.target.value)
              }
              placeholder="Search product, SKU, color, size or branch..."
              className="min-h-11 rounded-xl border border-[#d8c8c2] px-4 text-sm outline-none transition focus:border-[#7f2a3c] focus:ring-2 focus:ring-[#7f2a3c]/10"
            />

            <select
              value={branchFilter}
              onChange={(event) =>
                setBranchFilter(event.target.value)
              }
              className="min-h-11 rounded-xl border border-[#d8c8c2] bg-white px-3 text-sm outline-none focus:border-[#7f2a3c]"
            >
              <option value="all">
                All branches
              </option>

              {branchOptions.map(
                ([branchId, label]) => (
                  <option
                    key={branchId}
                    value={branchId}
                  >
                    {label}
                  </option>
                ),
              )}
            </select>

            <select
              value={stockFilter}
              onChange={(event) =>
                setStockFilter(event.target.value)
              }
              className="min-h-11 rounded-xl border border-[#d8c8c2] bg-white px-3 text-sm outline-none focus:border-[#7f2a3c]"
            >
              <option value="all">
                All stock
              </option>
              <option value="available">
                Available
              </option>
              <option value="low">
                Low stock
              </option>
              <option value="out">
                Out of stock
              </option>
            </select>
          </div>
        </section>

        <section className="mt-6 overflow-hidden rounded-2xl border border-[#dccbc4] bg-white shadow-sm">
          {loading ? (
            <div className="p-8 text-center text-sm text-[#756369]">
              Loading inventory...
            </div>
          ) : filteredRows.length === 0 ? (
            <div className="p-8 text-center">
              <p className="font-semibold">
                No inventory rows found
              </p>
              <p className="mt-2 text-sm text-[#756369]">
                Try changing the search or filters.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="border-b border-[#eee2dd] bg-[#fffaf7] text-xs uppercase tracking-wide text-[#756369]">
                  <tr>
                    <th className="px-5 py-4">
                      Product
                    </th>
                    <th className="px-5 py-4">
                      Variant
                    </th>
                    <th className="px-5 py-4">
                      Branch
                    </th>
                    <th className="px-5 py-4 text-right">
                      On hand
                    </th>
                    <th className="px-5 py-4 text-right">
                      Reserved
                    </th>
                    <th className="px-5 py-4 text-right">
                      Safety
                    </th>
                    <th className="px-5 py-4 text-right">
                      Available
                    </th>
                    <th className="px-5 py-4">
                      Status
                    </th>
                    <th className="px-5 py-4">
                      Updated
                    </th>
                  </tr>
                </thead>

                <tbody className="divide-y divide-[#f1e7e2]">
                  {filteredRows.map((row) => {
                    const status =
                      getStockStatus(row);

                    return (
                      <tr
                        key={row.id}
                        className="align-top hover:bg-[#fffaf7]/60"
                      >
                        <td className="px-5 py-4">
                          <p className="font-semibold">
                            {row.product_variants
                              ?.products?.name ??
                              "Unknown product"}
                          </p>

                          <p className="mt-1 text-xs text-[#756369]">
                            {row.product_variants
                              ?.sku ??
                              "No SKU"}
                          </p>
                        </td>

                        <td className="px-5 py-4 text-[#5e4a50]">
                          <div>
                            Color:{" "}
                            {row.product_variants
                              ?.colors?.name ??
                              "—"}
                          </div>
                          <div className="mt-1">
                            Size:{" "}
                            {row.product_variants
                              ?.sizes?.name ??
                              "—"}
                          </div>
                        </td>

                        <td className="px-5 py-4">
                          <p className="font-medium">
                            {row.branches?.name ??
                              "Unknown branch"}
                          </p>
                          <p className="mt-1 text-xs text-[#756369]">
                            {row.branches?.city ??
                              ""}
                          </p>
                        </td>

                        <td className="px-5 py-4 text-right tabular-nums">
                          {row.on_hand_quantity}
                        </td>

                        <td className="px-5 py-4 text-right tabular-nums">
                          {row.reserved_quantity}
                        </td>

                        <td className="px-5 py-4 text-right tabular-nums">
                          {row.safety_stock}
                        </td>

                        <td className="px-5 py-4 text-right font-bold tabular-nums">
                          {row.available_quantity}
                        </td>

                        <td className="px-5 py-4">
                          <span
                            className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${status.className}`}
                          >
                            {status.label}
                          </span>
                        </td>

                        <td className="whitespace-nowrap px-5 py-4 text-xs text-[#756369]">
                          {formatDate(
                            row.updated_at,
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <p className="mt-4 text-sm text-[#756369]">
          Showing {filteredRows.length} of{" "}
          {rows.length} inventory rows.
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
        {new Intl.NumberFormat().format(value)}
      </p>
    </article>
  );
}