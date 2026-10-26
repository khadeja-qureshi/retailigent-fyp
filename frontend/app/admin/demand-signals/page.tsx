"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { supabase } from "@/lib/supabase/client";

const API_URL = (
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000"
).replace(/\/+$/, "");

type DemandSignal = {
  id: string;
  customer_id: string | null;
  product_id: string | null;
  variant_id: string | null;
  branch_id: string | null;
  signal_type: string;
  requested_size: string | null;
  requested_color: string | null;
  fulfilled: boolean;
  metadata: Record<string, unknown> | null;
  created_at: string;

  product_name?: string | null;
  product_sku?: string | null;
  variant_sku?: string | null;
  branch_name?: string | null;
  branch_city?: string | null;
  branch_area?: string | null;
};

type DemandSignalsResponse = {
  demand_signals: DemandSignal[];
  count: number;
};

function asText(value: unknown): string | null {
  if (
    value === null ||
    value === undefined
  ) {
    return null;
  }

  const text = String(value).trim();
  return text ? text : null;
}

function asNumber(value: unknown): number | null {
  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return null;
  }

  const number = Number(value);

  return Number.isFinite(number)
    ? number
    : null;
}

function formatSignalType(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) =>
      letter.toUpperCase(),
    );
}

function formatDate(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString();
}

async function loadDemandSignals(): Promise<DemandSignalsResponse> {
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.access_token) {
    throw new Error(
      "Please sign in with an authorized staff account.",
    );
  }

  const response = await fetch(
    `${API_URL}/api/v1/admin/demand-signals?limit=200`,
    {
      method: "GET",
      headers: {
        Authorization:
          `Bearer ${session.access_token}`,
      },
      cache: "no-store",
    },
  );

  const payload = await response
    .json()
    .catch(() => null);

  if (!response.ok) {
    const detail =
      payload &&
      typeof payload.detail === "string"
        ? payload.detail
        : `Could not load demand signals (${response.status}).`;

    throw new Error(detail);
  }

  return payload as DemandSignalsResponse;
}

export default function AdminDemandSignalsPage() {
  const [
    demandSignals,
    setDemandSignals,
  ] = useState<DemandSignal[]>([]);

  const [
    loading,
    setLoading,
  ] = useState(true);

  const [
    error,
    setError,
  ] = useState<string | null>(null);

  const [
    signalFilter,
    setSignalFilter,
  ] = useState("all");

  const [
    search,
    setSearch,
  ] = useState("");

  const refresh = useCallback(
    async () => {
      setLoading(true);
      setError(null);

      try {
        const result =
          await loadDemandSignals();

        setDemandSignals(
          result.demand_signals ?? [],
        );
      } catch (caught) {
        setError(
          caught instanceof Error
            ? caught.message
            : "Could not load demand signals.",
        );
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    const timer = window.setTimeout(
      () => {
        void refresh();
      },
      0,
    );

    return () => {
      window.clearTimeout(timer);
    };
  }, [refresh]);

  const signalTypes = useMemo(
    () =>
      Array.from(
        new Set(
          demandSignals.map(
            (signal) =>
              signal.signal_type,
          ),
        ),
      ).sort(),
    [demandSignals],
  );

  const filteredSignals = useMemo(
    () => {
      const normalizedSearch =
        search.trim().toLowerCase();

      return demandSignals.filter(
        (signal) => {
          if (
            signalFilter !== "all" &&
            signal.signal_type !==
              signalFilter
          ) {
            return false;
          }

          if (!normalizedSearch) {
            return true;
          }

          const metadata =
            signal.metadata ?? {};

          const haystack = [
            signal.product_name,
            signal.product_sku,
            signal.variant_sku,
            signal.branch_name,
            signal.branch_city,
            signal.branch_area,
            signal.requested_size,
            signal.requested_color,
            signal.signal_type,
            asText(metadata.query),
            asText(
              metadata.requested_category,
            ),
            asText(
              metadata.requested_material,
            ),
          ]
            .filter(Boolean)
            .join(" ")
            .toLowerCase();

          return haystack.includes(
            normalizedSearch,
          );
        },
      );
    },
    [
      demandSignals,
      search,
      signalFilter,
    ],
  );

  const unfulfilledCount = useMemo(
    () =>
      demandSignals.filter(
        (signal) => !signal.fulfilled,
      ).length,
    [demandSignals],
  );

  const unavailableCount = useMemo(
    () =>
      demandSignals.filter(
        (signal) =>
          signal.signal_type ===
          "requested_variant_unavailable",
      ).length,
    [demandSignals],
  );

  const insufficientStockCount =
    useMemo(
      () =>
        demandSignals.filter(
          (signal) =>
            signal.signal_type ===
            "insufficient_stock",
        ).length,
      [demandSignals],
    );

  return (
    <main
      style={{
        minHeight: "100vh",
        padding: "32px",
        background: "#f7f5f3",
      }}
    >
      <div
        style={{
          maxWidth: "1280px",
          margin: "0 auto",
        }}
      >
        <div
          style={{
            display: "flex",
            gap: "16px",
            justifyContent:
              "space-between",
            alignItems: "flex-start",
            flexWrap: "wrap",
            marginBottom: "24px",
          }}
        >
          <div>
            <p
              style={{
                margin: 0,
                fontSize: "12px",
                fontWeight: 700,
                letterSpacing: "0.18em",
                textTransform: "uppercase",
                color: "#6864d9",
              }}
            >
              Retailigent Staff
            </p>

            <h1
              style={{
                margin:
                  "8px 0 6px",
                fontSize: "32px",
              }}
            >
              Demand Signals
            </h1>

            <p
              style={{
                margin: 0,
                maxWidth: "760px",
                color: "#666",
                lineHeight: 1.6,
              }}
            >
              Unavailable searches and
              insufficient-stock requests
              captured from customer
              conversations.
            </p>
          </div>

          <button
            type="button"
            onClick={() => {
              void refresh();
            }}
            disabled={loading}
            style={{
              border: "1px solid #d7d3cf",
              borderRadius: "10px",
              padding: "10px 16px",
              background: "#fff",
              cursor: loading
                ? "not-allowed"
                : "pointer",
              fontWeight: 600,
            }}
          >
            {loading
              ? "Refreshing..."
              : "Refresh"}
          </button>
        </div>

        <section
          style={{
            display: "grid",
            gridTemplateColumns:
              "repeat(auto-fit, minmax(180px, 1fr))",
            gap: "14px",
            marginBottom: "22px",
          }}
        >
          {[
            [
              "Total signals",
              demandSignals.length,
            ],
            [
              "Unfulfilled",
              unfulfilledCount,
            ],
            [
              "Unavailable searches",
              unavailableCount,
            ],
            [
              "Insufficient stock",
              insufficientStockCount,
            ],
          ].map(
            ([label, value]) => (
              <article
                key={String(label)}
                style={{
                  background: "#fff",
                  border:
                    "1px solid #e3dfdc",
                  borderRadius: "14px",
                  padding: "18px",
                }}
              >
                <div
                  style={{
                    fontSize: "13px",
                    color: "#777",
                    marginBottom: "8px",
                  }}
                >
                  {label}
                </div>

                <div
                  style={{
                    fontSize: "28px",
                    fontWeight: 700,
                  }}
                >
                  {value}
                </div>
              </article>
            ),
          )}
        </section>

        <section
          style={{
            display: "flex",
            gap: "12px",
            flexWrap: "wrap",
            marginBottom: "18px",
            background: "#fff",
            border:
              "1px solid #e3dfdc",
            borderRadius: "14px",
            padding: "16px",
          }}
        >
          <input
            value={search}
            onChange={(event) =>
              setSearch(
                event.target.value,
              )
            }
            placeholder="Search product, query, color, size..."
            style={{
              flex: "1 1 320px",
              minWidth: "240px",
              border:
                "1px solid #d9d5d2",
              borderRadius: "10px",
              padding: "11px 12px",
              fontSize: "14px",
            }}
          />

          <select
            value={signalFilter}
            onChange={(event) =>
              setSignalFilter(
                event.target.value,
              )
            }
            style={{
              minWidth: "220px",
              border:
                "1px solid #d9d5d2",
              borderRadius: "10px",
              padding: "11px 12px",
              background: "#fff",
              fontSize: "14px",
            }}
          >
            <option value="all">
              All signal types
            </option>

            {signalTypes.map(
              (signalType) => (
                <option
                  key={signalType}
                  value={signalType}
                >
                  {formatSignalType(
                    signalType,
                  )}
                </option>
              ),
            )}
          </select>
        </section>

        {error ? (
          <div
            style={{
              border:
                "1px solid #e5a6a6",
              background: "#fff1f1",
              color: "#a33",
              borderRadius: "12px",
              padding: "14px 16px",
              marginBottom: "18px",
            }}
          >
            {error}
          </div>
        ) : null}

        {loading &&
        demandSignals.length === 0 ? (
          <div
            style={{
              background: "#fff",
              border:
                "1px solid #e3dfdc",
              borderRadius: "14px",
              padding: "28px",
            }}
          >
            Loading demand signals...
          </div>
        ) : null}

        {!loading &&
        !error &&
        filteredSignals.length === 0 ? (
          <div
            style={{
              background: "#fff",
              border:
                "1px solid #e3dfdc",
              borderRadius: "14px",
              padding: "28px",
            }}
          >
            No matching demand signals.
          </div>
        ) : null}

        <div
          style={{
            display: "grid",
            gap: "14px",
          }}
        >
          {filteredSignals.map(
            (signal) => {
              const metadata =
                signal.metadata ?? {};

              const query =
                asText(metadata.query);

              const requestedQuantity =
                asNumber(
                  metadata.requested_quantity,
                );

              const availableQuantity =
                asNumber(
                  metadata.available_quantity,
                );

              const shortfallQuantity =
                asNumber(
                  metadata.shortfall_quantity,
                );

              const requestedCategory =
                asText(
                  metadata.requested_category,
                );

              const requestedMaterial =
                asText(
                  metadata.requested_material,
                );

              const requestedBranch =
                asText(
                  metadata.requested_branch,
                );

              return (
                <article
                  key={signal.id}
                  style={{
                    background: "#fff",
                    border:
                      "1px solid #e3dfdc",
                    borderRadius: "14px",
                    padding: "20px",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent:
                        "space-between",
                      gap: "14px",
                      alignItems:
                        "flex-start",
                      flexWrap: "wrap",
                    }}
                  >
                    <div>
                      <div
                        style={{
                          display: "flex",
                          gap: "8px",
                          flexWrap:
                            "wrap",
                          marginBottom:
                            "8px",
                        }}
                      >
                        <span
                          style={{
                            padding:
                              "5px 9px",
                            borderRadius:
                              "999px",
                            background:
                              "#efedff",
                            color:
                              "#514dc1",
                            fontSize:
                              "12px",
                            fontWeight:
                              700,
                          }}
                        >
                          {formatSignalType(
                            signal.signal_type,
                          )}
                        </span>

                        <span
                          style={{
                            padding:
                              "5px 9px",
                            borderRadius:
                              "999px",
                            background:
                              signal.fulfilled
                                ? "#edf8ef"
                                : "#fff0f0",
                            color:
                              signal.fulfilled
                                ? "#27733a"
                                : "#a93d3d",
                            fontSize:
                              "12px",
                            fontWeight:
                              700,
                          }}
                        >
                          {signal.fulfilled
                            ? "Fulfilled"
                            : "Unfulfilled"}
                        </span>
                      </div>

                      <h2
                        style={{
                          margin:
                            "0 0 5px",
                          fontSize:
                            "19px",
                        }}
                      >
                        {signal.product_name ??
                          "Unmatched customer demand"}
                      </h2>

                      <div
                        style={{
                          color: "#777",
                          fontSize: "13px",
                        }}
                      >
                        {formatDate(
                          signal.created_at,
                        )}
                      </div>
                    </div>

                    <div
                      style={{
                        color: "#777",
                        fontSize: "12px",
                        wordBreak:
                          "break-all",
                      }}
                    >
                      {signal.variant_sku
                        ? `Variant: ${signal.variant_sku}`
                        : ""}
                    </div>
                  </div>

                  {query ? (
                    <div
                      style={{
                        marginTop:
                          "16px",
                        padding:
                          "13px 14px",
                        borderRadius:
                          "10px",
                        background:
                          "#f5f3fb",
                        lineHeight: 1.5,
                      }}
                    >
                      “{query}”
                    </div>
                  ) : null}

                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns:
                        "repeat(auto-fit, minmax(170px, 1fr))",
                      gap: "12px",
                      marginTop:
                        "16px",
                    }}
                  >
                    <Info
                      label="Color"
                      value={
                        signal.requested_color
                      }
                    />

                    <Info
                      label="Size"
                      value={
                        signal.requested_size
                      }
                    />

                    <Info
                      label="Category"
                      value={
                        requestedCategory
                      }
                    />

                    <Info
                      label="Material"
                      value={
                        requestedMaterial
                      }
                    />

                    <Info
                      label="Requested quantity"
                      value={
                        requestedQuantity
                      }
                    />

                    <Info
                      label="Available quantity"
                      value={
                        availableQuantity
                      }
                    />

                    <Info
                      label="Shortfall"
                      value={
                        shortfallQuantity
                      }
                    />

                    <Info
                      label="Requested branch"
                      value={
                        requestedBranch
                      }
                    />

                    <Info
                      label="Recorded branch"
                      value={
                        signal.branch_name
                          ? [
                              signal.branch_name,
                              signal.branch_city,
                            ]
                              .filter(Boolean)
                              .join(", ")
                          : null
                      }
                    />
                  </div>
                </article>
              );
            },
          )}
        </div>
      </div>
    </main>
  );
}

function Info({
  label,
  value,
}: {
  label: string;
  value:
    | string
    | number
    | null
    | undefined;
}) {
  return (
    <div>
      <div
        style={{
          fontSize: "12px",
          color: "#888",
          marginBottom: "4px",
        }}
      >
        {label}
      </div>

      <div
        style={{
          fontSize: "14px",
          fontWeight: 600,
        }}
      >
        {value === null ||
        value === undefined ||
        value === ""
          ? "—"
          : String(value)}
      </div>
    </div>
  );
}
