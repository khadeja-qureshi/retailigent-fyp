"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { supabase } from "@/lib/supabase/client";

type OrderItemRow = {
  id: string;
  variant_id: string;
  quantity: number;
  unit_price: number;
  line_total: number;
  product_snapshot:
    | Record<string, unknown>
    | null;

  product_variants:
    | {
        sku: string;
        products:
          | {
              name: string;
            }
          | null;
      }
    | null;
};

type OrderRow = {
  id: string;
  customer_id: string;
  branch_id: string | null;
  status: string;
  subtotal: number;
  discount: number;
  total: number;
  currency: string;
  source: string;
  metadata:
    | Record<string, unknown>
    | null;
  created_at: string;
  updated_at: string;

  profiles:
    | {
        id: string;
        full_name: string | null;
      }
    | null;

  branches:
    | {
        id: string;
        name: string;
        city: string | null;
      }
    | null;

  order_items:
    | OrderItemRow[]
    | null;
};

function formatMoney(
  amount: number,
  currency = "PKR",
) {
  try {
    return new Intl.NumberFormat(
      "en-PK",
      {
        style: "currency",
        currency,
        maximumFractionDigits: 2,
      },
    ).format(amount);
  } catch {
    return `${currency} ${new Intl.NumberFormat(
      "en-PK",
    ).format(amount)}`;
  }
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-PK", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function statusStyle(status: string) {
  const normalized =
    status.toLowerCase();

  if (
    [
      "completed",
      "paid",
      "fulfilled",
    ].includes(normalized)
  ) {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }

  if (
    [
      "cancelled",
      "failed",
      "refunded",
    ].includes(normalized)
  ) {
    return "border-red-200 bg-red-50 text-red-700";
  }

  if (
    [
      "processing",
      "confirmed",
    ].includes(normalized)
  ) {
    return "border-blue-200 bg-blue-50 text-blue-700";
  }

  return "border-amber-200 bg-amber-50 text-amber-700";
}

function snapshotProductName(
  item: OrderItemRow,
) {
  const snapshot =
    item.product_snapshot;

  if (snapshot) {
    const name =
      snapshot.product_name ??
      snapshot.name;

    if (
      typeof name === "string" &&
      name.trim()
    ) {
      return name;
    }
  }

  return (
    item.product_variants
      ?.products?.name ??
    "Unknown product"
  );
}

function snapshotSku(
  item: OrderItemRow,
) {
  const snapshot =
    item.product_snapshot;

  if (snapshot) {
    const sku =
      snapshot.variant_sku ??
      snapshot.sku;

    if (
      typeof sku === "string" &&
      sku.trim()
    ) {
      return sku;
    }
  }

  return (
    item.product_variants?.sku ??
    "—"
  );
}

export default function AdminOrdersPage() {
  const [orders, setOrders] =
    useState<OrderRow[]>([]);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] = useState<
    string | null
  >(null);

  const [query, setQuery] =
    useState("");

  const [statusFilter, setStatusFilter] =
    useState("all");

  const [expandedOrder, setExpandedOrder] =
    useState<string | null>(null);

  const loadOrders =
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
          error: ordersError,
        } = await supabase
          .from("orders")
          .select(`
            id,
            customer_id,
            branch_id,
            status,
            subtotal,
            discount,
            total,
            currency,
            source,
            metadata,
            created_at,
            updated_at,
            profiles (
              id,
              full_name
            ),
            branches (
              id,
              name,
              city
            ),
            order_items (
              id,
              variant_id,
              quantity,
              unit_price,
              line_total,
              product_snapshot,
              product_variants (
                sku,
                products (
                  name
                )
              )
            )
          `)
          .order("created_at", {
            ascending: false,
          });

        if (ordersError) {
          throw ordersError;
        }

        setOrders(
          (data ?? []) as unknown as OrderRow[],
        );
      } catch (caught) {
        setError(
          caught instanceof Error
            ? caught.message
            : "Could not load orders.",
        );
      } finally {
        setLoading(false);
      }
    }, []);

  useEffect(() => {
    void loadOrders();
  }, [loadOrders]);

  const statuses = useMemo(() => {
    return Array.from(
      new Set(
        orders
          .map((order) => order.status)
          .filter(Boolean),
      ),
    ).sort();
  }, [orders]);

  const filteredOrders =
    useMemo(() => {
      const normalized =
        query.trim().toLowerCase();

      return orders.filter(
        (order) => {
          const productNames =
            (
              order.order_items ?? []
            )
              .map(snapshotProductName)
              .join(" ");

          const skus =
            (
              order.order_items ?? []
            )
              .map(snapshotSku)
              .join(" ");

          const searchable = [
            order.id,
            order.customer_id,
            order.profiles
              ?.full_name ?? "",
            order.branches?.name ??
              "",
            order.branches?.city ??
              "",
            order.status,
            order.source,
            productNames,
            skus,
          ]
            .join(" ")
            .toLowerCase();

          const matchesQuery =
            !normalized ||
            searchable.includes(
              normalized,
            );

          const matchesStatus =
            statusFilter === "all" ||
            order.status ===
              statusFilter;

          return (
            matchesQuery &&
            matchesStatus
          );
        },
      );
    }, [
      orders,
      query,
      statusFilter,
    ]);

  const summary = useMemo(() => {
    return orders.reduce(
      (result, order) => {
        result.orders += 1;

        result.revenue +=
          Number(order.total ?? 0);

        result.items += (
          order.order_items ?? []
        ).reduce(
          (sum, item) =>
            sum + item.quantity,
          0,
        );

        return result;
      },
      {
        orders: 0,
        revenue: 0,
        items: 0,
      },
    );
  }, [orders]);

  return (
    <main className="min-h-screen bg-[#fffaf7] px-4 py-6 text-[#2c1c20] sm:px-6 sm:py-10">
      <div className="mx-auto max-w-7xl">
        <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#7f2a3c]">
              Retailigent · Staff
            </p>

            <h1 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">
              Orders
            </h1>

            <p className="mt-3 max-w-2xl text-sm leading-6 text-[#756369] sm:text-base">
              Review customer purchases,
              fulfillment branches, order
              totals, and purchased items.
            </p>
          </div>

          <button
            type="button"
            onClick={() =>
              void loadOrders()
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
              Could not load orders
            </p>
            <p className="mt-1">
              {error}
            </p>
          </section>
        )}

        <section className="mt-8 grid gap-4 sm:grid-cols-3">
          <MetricCard
            title="Orders"
            value={new Intl.NumberFormat().format(
              summary.orders,
            )}
          />

          <MetricCard
            title="Units sold"
            value={new Intl.NumberFormat().format(
              summary.items,
            )}
          />

          <MetricCard
            title="Order value"
            value={formatMoney(
              summary.revenue,
            )}
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
              placeholder="Search order ID, customer, branch, product or SKU..."
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

              {statuses.map(
                (status) => (
                  <option
                    key={status}
                    value={status}
                  >
                    {status}
                  </option>
                ),
              )}
            </select>
          </div>
        </section>

        <section className="mt-6 overflow-hidden rounded-2xl border border-[#dccbc4] bg-white shadow-sm">
          {loading ? (
            <div className="p-8 text-center text-sm text-[#756369]">
              Loading orders...
            </div>
          ) : filteredOrders.length ===
            0 ? (
            <div className="p-8 text-center">
              <p className="font-semibold">
                No orders found
              </p>
              <p className="mt-2 text-sm text-[#756369]">
                No order matches the
                selected filters.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-[#eee2dd]">
              {filteredOrders.map(
                (order) => {
                  const isExpanded =
                    expandedOrder ===
                    order.id;

                  const itemCount =
                    (
                      order.order_items ??
                      []
                    ).reduce(
                      (sum, item) =>
                        sum +
                        item.quantity,
                      0,
                    );

                  return (
                    <article
                      key={order.id}
                      className="p-5"
                    >
                      <div className="grid gap-5 lg:grid-cols-[1.5fr_1fr_1fr_auto] lg:items-center">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="font-bold">
                              Order{" "}
                              {order.id.slice(
                                0,
                                8,
                              )}
                            </p>

                            <span
                              className={`rounded-full border px-2.5 py-1 text-xs font-semibold capitalize ${statusStyle(
                                order.status,
                              )}`}
                            >
                              {
                                order.status
                              }
                            </span>
                          </div>

                          <p className="mt-2 text-sm text-[#756369]">
                            Customer:{" "}
                            {order.profiles
                              ?.full_name ??
                              order.customer_id.slice(
                                0,
                                8,
                              )}
                          </p>

                          <p className="mt-1 text-xs text-[#9a858b]">
                            {formatDate(
                              order.created_at,
                            )}
                          </p>
                        </div>

                        <div>
                          <p className="text-xs font-semibold uppercase tracking-wide text-[#756369]">
                            Fulfillment
                          </p>
                          <p className="mt-1 font-medium">
                            {order.branches
                              ?.name ??
                              "No branch"}
                          </p>
                          <p className="mt-1 text-xs text-[#756369]">
                            {order.branches
                              ?.city ??
                              ""}
                          </p>
                        </div>

                        <div>
                          <p className="text-xs font-semibold uppercase tracking-wide text-[#756369]">
                            Total
                          </p>
                          <p className="mt-1 text-lg font-bold">
                            {formatMoney(
                              Number(
                                order.total,
                              ),
                              order.currency,
                            )}
                          </p>
                          <p className="mt-1 text-xs text-[#756369]">
                            {itemCount} unit
                            {itemCount === 1
                              ? ""
                              : "s"}
                          </p>
                        </div>

                        <button
                          type="button"
                          onClick={() =>
                            setExpandedOrder(
                              isExpanded
                                ? null
                                : order.id,
                            )
                          }
                          className="inline-flex min-h-10 items-center justify-center rounded-xl border border-[#d8c8c2] px-4 text-sm font-semibold text-[#7f2a3c] hover:bg-[#fff4f2]"
                        >
                          {isExpanded
                            ? "Hide items"
                            : "View items"}
                        </button>
                      </div>

                      {isExpanded && (
                        <div className="mt-5 border-t border-[#eee2dd] pt-5">
                          <div className="grid gap-3 sm:grid-cols-3">
                            <OrderAmount
                              label="Subtotal"
                              value={formatMoney(
                                Number(
                                  order.subtotal,
                                ),
                                order.currency,
                              )}
                            />

                            <OrderAmount
                              label="Discount"
                              value={formatMoney(
                                Number(
                                  order.discount,
                                ),
                                order.currency,
                              )}
                            />

                            <OrderAmount
                              label="Final total"
                              value={formatMoney(
                                Number(
                                  order.total,
                                ),
                                order.currency,
                              )}
                            />
                          </div>

                          <h3 className="mt-6 text-sm font-bold">
                            Order items
                          </h3>

                          {(
                            order.order_items ??
                            []
                          ).length === 0 ? (
                            <p className="mt-3 text-sm text-[#756369]">
                              No order items
                              were returned.
                            </p>
                          ) : (
                            <div className="mt-3 overflow-x-auto rounded-xl border border-[#eee2dd]">
                              <table className="min-w-full text-sm">
                                <thead className="bg-[#fffaf7] text-left text-xs uppercase tracking-wide text-[#756369]">
                                  <tr>
                                    <th className="px-4 py-3">
                                      Product
                                    </th>
                                    <th className="px-4 py-3">
                                      SKU
                                    </th>
                                    <th className="px-4 py-3 text-right">
                                      Qty
                                    </th>
                                    <th className="px-4 py-3 text-right">
                                      Unit price
                                    </th>
                                    <th className="px-4 py-3 text-right">
                                      Line total
                                    </th>
                                  </tr>
                                </thead>

                                <tbody className="divide-y divide-[#eee2dd]">
                                  {(
                                    order.order_items ??
                                    []
                                  ).map(
                                    (
                                      item,
                                    ) => (
                                      <tr
                                        key={
                                          item.id
                                        }
                                      >
                                        <td className="px-4 py-3 font-medium">
                                          {snapshotProductName(
                                            item,
                                          )}
                                        </td>

                                        <td className="px-4 py-3 text-[#756369]">
                                          {snapshotSku(
                                            item,
                                          )}
                                        </td>

                                        <td className="px-4 py-3 text-right tabular-nums">
                                          {
                                            item.quantity
                                          }
                                        </td>

                                        <td className="px-4 py-3 text-right tabular-nums">
                                          {formatMoney(
                                            Number(
                                              item.unit_price,
                                            ),
                                            order.currency,
                                          )}
                                        </td>

                                        <td className="px-4 py-3 text-right font-semibold tabular-nums">
                                          {formatMoney(
                                            Number(
                                              item.line_total,
                                            ),
                                            order.currency,
                                          )}
                                        </td>
                                      </tr>
                                    ),
                                  )}
                                </tbody>
                              </table>
                            </div>
                          )}

                          <p className="mt-4 text-xs text-[#9a858b]">
                            Source:{" "}
                            {order.source}
                          </p>
                        </div>
                      )}
                    </article>
                  );
                },
              )}
            </div>
          )}
        </section>

        <p className="mt-4 text-sm text-[#756369]">
          Showing {filteredOrders.length}{" "}
          of {orders.length} orders.
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
  value: string;
}) {
  return (
    <article className="rounded-2xl border border-[#dccbc4] bg-white p-5 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-wide text-[#756369]">
        {title}
      </p>
      <p className="mt-3 text-3xl font-bold">
        {value}
      </p>
    </article>
  );
}

function OrderAmount({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl bg-[#fffaf7] p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-[#756369]">
        {label}
      </p>
      <p className="mt-2 font-bold">
        {value}
      </p>
    </div>
  );
}