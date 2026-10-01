"use client";

import {
  useCallback,
  useEffect,
  useState,
} from "react";

import Link from "next/link";

import AlertBlock from "@/components/chat-blocks/AlertBlock";

import {
  AlertListResponse,
  AlertType,
  createAlert,
  deleteAlert,
  getAlerts,
  pauseAlert,
  resumeAlert,
} from "@/lib/api";


export default function AlertsPage() {
  const [data, setData] =
    useState<AlertListResponse | null>(
      null
    );

  const [variantId, setVariantId] =
    useState("");

  const [alertType, setAlertType] =
    useState<AlertType>(
      "price_drop"
    );

  const [targetPrice, setTargetPrice] =
    useState("");

  const [loading, setLoading] =
    useState(true);

  const [busy, setBusy] =
    useState<string | null>(null);

  const [error, setError] =
    useState<string | null>(null);


  const loadAlerts = useCallback(
    async (silent = false) => {
      try {
        if (!silent) {
          setLoading(true);
        }

        const result =
          await getAlerts();

        setData(result);

        if (!silent) {
          setError(null);
        }

      } catch (error) {
        if (!silent) {
          setError(
            error instanceof Error
              ? error.message
              : "Unable to load alerts."
          );
        }

      } finally {
        if (!silent) {
          setLoading(false);
        }
      }
    },
    []
  );


  useEffect(() => {
    void loadAlerts();

    // Poll every 2 seconds so triggered
    // alerts update without refreshing.
    const intervalId =
      window.setInterval(() => {
        void loadAlerts(true);
      }, 5000);

    return () => {
      window.clearInterval(
        intervalId
      );
    };
  }, [loadAlerts]);


  async function handleCreate() {
    if (!variantId.trim()) {
      setError(
        "Variant UUID is required."
      );
      return;
    }

    if (
      alertType === "price_drop" &&
      targetPrice.trim() === ""
    ) {
      setError(
        "Price-drop alerts require a target price."
      );
      return;
    }

    if (
      targetPrice.trim() !== "" &&
      Number(targetPrice) < 0
    ) {
      setError(
        "Target price cannot be negative."
      );
      return;
    }

    try {
      setBusy("create");
      setError(null);

      await createAlert({
        variant_id:
          variantId.trim(),

        alert_type:
          alertType,

        target_price:
          alertType ===
            "price_drop"
            ? Number(targetPrice)
            : null,
      });

      setVariantId("");
      setTargetPrice("");

      await loadAlerts(true);

    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to create alert."
      );

    } finally {
      setBusy(null);
    }
  }


  async function handlePause(
    alertId: string
  ) {
    try {
      setBusy(alertId);
      setError(null);

      await pauseAlert(
        alertId
      );

      await loadAlerts(true);

    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to pause alert."
      );

    } finally {
      setBusy(null);
    }
  }


  async function handleResume(
    alertId: string
  ) {
    try {
      setBusy(alertId);
      setError(null);

      await resumeAlert(
        alertId
      );

      await loadAlerts(true);

    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to resume alert."
      );

    } finally {
      setBusy(null);
    }
  }


  async function handleDelete(
    alertId: string
  ) {
    try {
      setBusy(alertId);
      setError(null);

      await deleteAlert(
        alertId
      );

      await loadAlerts(true);

    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to delete alert."
      );

    } finally {
      setBusy(null);
    }
  }


  return (
    <main className="min-h-screen bg-black px-6 py-10 text-white">

      <div className="mx-auto max-w-4xl">

        <div className="mb-8 flex flex-col gap-5 md:flex-row md:items-start md:justify-between">

          <div>

            <p className="text-sm uppercase tracking-widest text-neutral-500">
              Retailigent
            </p>

            <h1 className="mt-2 text-3xl font-semibold">
              Product Alerts
            </h1>

            <p className="mt-2 max-w-xl text-neutral-400">
              Watch products for price drops,
              restocks, and sale events.
            </p>

          </div>


          <nav className="flex flex-wrap gap-4 text-sm text-neutral-300">

            <Link
              href="/cart"
              className="underline hover:text-white"
            >
              Cart
            </Link>

            <Link
              href="/smart-cart"
              className="underline hover:text-white"
            >
              Smart Cart
            </Link>

            <Link
              href="/orders"
              className="underline hover:text-white"
            >
              Orders
            </Link>

          </nav>

        </div>


        {error && (
          <div className="mb-6 rounded-xl border border-red-900 bg-red-950/30 p-4 text-red-300">
            {error}
          </div>
        )}


        <section className="mb-10 rounded-2xl border border-neutral-800 bg-neutral-900 p-6">

          <h2 className="text-xl font-semibold">
            Create alert
          </h2>

          <p className="mt-2 text-sm text-neutral-400">
            Choose what Retailigent should
            watch for.
          </p>


          <div className="mt-6">

            <label className="block text-sm font-medium">
              Variant UUID
            </label>

            <input
              value={variantId}
              onChange={(event) => {
                setVariantId(
                  event.target.value
                );
              }}
              placeholder="f1000000-0000-0000-0000-000000000003"
              className="mt-2 w-full rounded-lg border border-neutral-700 bg-neutral-950 p-3 outline-none focus:border-neutral-500"
            />

          </div>


          <div className="mt-5">

            <label className="block text-sm font-medium">
              Alert type
            </label>

            <select
              value={alertType}
              onChange={(event) => {
                const value =
                  event.target
                    .value as AlertType;

                setAlertType(
                  value
                );

                if (
                  value !==
                  "price_drop"
                ) {
                  setTargetPrice("");
                }
              }}
              className="mt-2 w-full rounded-lg border border-neutral-700 bg-neutral-950 p-3 outline-none focus:border-neutral-500"
            >

              <option value="price_drop">
                Price drop
              </option>

              <option value="restock">
                Restock
              </option>

              <option value="sale">
                Sale
              </option>

            </select>

          </div>


          {alertType ===
            "price_drop" && (
            <div className="mt-5">

              <label className="block text-sm font-medium">
                Target price
              </label>

              <input
                type="number"
                min={0}
                value={targetPrice}
                onChange={(event) => {
                  setTargetPrice(
                    event.target.value
                  );
                }}
                placeholder="3000"
                className="mt-2 w-full rounded-lg border border-neutral-700 bg-neutral-950 p-3 outline-none focus:border-neutral-500"
              />

              <p className="mt-2 text-xs text-neutral-500">
                The alert triggers when the
                effective price reaches this
                amount or lower.
              </p>

            </div>
          )}


          {alertType ===
            "restock" && (
            <div className="mt-5 rounded-xl border border-neutral-700 bg-neutral-950 p-4 text-sm text-neutral-300">

              Retailigent will notify you when
              this variant is restocked.

            </div>
          )}


          {alertType ===
            "sale" && (
            <div className="mt-5 rounded-xl border border-neutral-700 bg-neutral-950 p-4 text-sm text-neutral-300">

              Retailigent will notify you when
              a sale starts for this variant.

            </div>
          )}


          <button
            type="button"
            disabled={
              busy === "create"
            }
            onClick={() => {
              void handleCreate();
            }}
            className="mt-6 rounded-lg bg-white px-5 py-3 font-medium text-black transition hover:bg-neutral-200 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy === "create"
              ? "Creating..."
              : "Create alert"}
          </button>

        </section>


        <section>

          <div className="mb-4 flex items-center justify-between">

            <h2 className="text-xl font-semibold">
              Your alerts
            </h2>

            <span className="text-xs text-neutral-500">
              Auto-refreshes every 5 seconds
            </span>

          </div>


          {loading && (
            <p className="text-neutral-400">
              Loading alerts...
            </p>
          )}


          {!loading &&
            !error &&
            data?.items.length === 0 && (
              <div className="rounded-2xl border border-neutral-800 bg-neutral-900 p-6">

                <h3 className="text-lg font-semibold">
                  No alerts yet
                </h3>

                <p className="mt-2 text-neutral-400">
                  Create your first alert above.
                </p>

              </div>
            )}


          {!loading &&
            data &&
            data.items.length > 0 && (
              <div className="space-y-5">

                {data.items.map(
                  (alert) => (
                    <AlertBlock
                      key={alert.id}
                      alert={alert}
                      busy={
                        busy === alert.id
                      }
                      onPause={
                        handlePause
                      }
                      onResume={
                        handleResume
                      }
                      onDelete={
                        handleDelete
                      }
                    />
                  )
                )}

              </div>
            )}

        </section>

      </div>

    </main>
  );
}