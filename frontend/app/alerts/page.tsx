"use client";

import Link from "next/link";

import {
  useCallback,
  useEffect,
  useState,
} from "react";

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
  const [
    data,
    setData,
  ] =
    useState<AlertListResponse | null>(
      null
    );

  const [
    variantId,
    setVariantId,
  ] =
    useState("");

  const [
    alertType,
    setAlertType,
  ] =
    useState<AlertType>(
      "price_drop"
    );

  const [
    targetPrice,
    setTargetPrice,
  ] =
    useState("");

  const [
    loading,
    setLoading,
  ] =
    useState(true);

  const [
    busy,
    setBusy,
  ] =
    useState<string | null>(
      null
    );

  const [
    error,
    setError,
  ] =
    useState<string | null>(
      null
    );


  const loadAlerts =
    useCallback(
      async (
        silent = false
      ) => {
        try {
          if (!silent) {
            setLoading(
              true
            );
          }

          const result =
            await getAlerts();

          setData(
            result
          );

          if (!silent) {
            setError(
              null
            );
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
            setLoading(
              false
            );
          }
        }
      },
      []
    );


  useEffect(() => {
    queueMicrotask(() => {
      void loadAlerts();
    });

    const intervalId =
      window.setInterval(
        () => {
          void loadAlerts(
            true
          );
        },
        5000
      );

    return () => {
      window.clearInterval(
        intervalId
      );
    };
  }, [
    loadAlerts,
  ]);


  async function handleCreate() {
    if (!variantId.trim()) {
      setError(
        "Variant UUID is required."
      );

      return;
    }

    if (
      alertType
      === "price_drop"
      &&
      targetPrice.trim()
      === ""
    ) {
      setError(
        "Price-drop alerts require a target price."
      );

      return;
    }

    if (
      targetPrice.trim()
      !== ""
      &&
      Number(
        targetPrice
      ) < 0
    ) {
      setError(
        "Target price cannot be negative."
      );

      return;
    }


    try {
      setBusy(
        "create"
      );

      setError(
        null
      );


      await createAlert({
        variant_id:
          variantId.trim(),

        alert_type:
          alertType,

        target_price:
          alertType
          === "price_drop"
            ? Number(
                targetPrice
              )
            : null,
      });


      setVariantId("");
      setTargetPrice("");


      await loadAlerts(
        true
      );
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to create alert."
      );
    } finally {
      setBusy(
        null
      );
    }
  }


  async function handlePause(
    alertId: string
  ) {
    try {
      setBusy(
        alertId
      );

      setError(
        null
      );

      await pauseAlert(
        alertId
      );

      await loadAlerts(
        true
      );
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to pause alert."
      );
    } finally {
      setBusy(
        null
      );
    }
  }


  async function handleResume(
    alertId: string
  ) {
    try {
      setBusy(
        alertId
      );

      setError(
        null
      );

      await resumeAlert(
        alertId
      );

      await loadAlerts(
        true
      );
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to resume alert."
      );
    } finally {
      setBusy(
        null
      );
    }
  }


  async function handleDelete(
    alertId: string
  ) {
    try {
      setBusy(
        alertId
      );

      setError(
        null
      );

      await deleteAlert(
        alertId
      );

      await loadAlerts(
        true
      );
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to delete alert."
      );
    } finally {
      setBusy(
        null
      );
    }
  }


  return (
    <main className="min-h-[calc(100dvh-4rem)] overflow-x-hidden bg-[#f1e6de] text-[#2c1c20]">
      <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6 sm:py-8 lg:px-8 lg:py-10">

        <header className="mb-6 sm:mb-8">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#7f2a3c]">
                Product monitoring
              </p>

              <h1 className="mt-2 text-3xl font-bold sm:text-4xl">
                Product Alerts
              </h1>

              <p className="mt-2 max-w-2xl text-sm leading-6 text-[#756369] sm:text-base">
                Watch products for price drops,
                restocks, and sale events.
              </p>
            </div>

            <Link
              href="/chat"
              className="inline-flex min-h-11 w-full items-center justify-center rounded-xl bg-[#7f2a3c] px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-[#682132] sm:w-auto"
            >
              Ask assistant
            </Link>
          </div>


          <nav className="mt-5 flex gap-2 overflow-x-auto pb-1 sm:flex-wrap sm:overflow-visible">
            <Link
              href="/cart"
              className="shrink-0 rounded-full border border-[#d8c8c1] bg-[#fffaf7] px-4 py-2 text-sm font-medium text-[#5f4d52]"
            >
              Cart
            </Link>

            <Link
              href="/smart-cart"
              className="shrink-0 rounded-full border border-[#d8c8c1] bg-[#fffaf7] px-4 py-2 text-sm font-medium text-[#5f4d52]"
            >
              Smart Cart
            </Link>

            <Link
              href="/orders"
              className="shrink-0 rounded-full border border-[#d8c8c1] bg-[#fffaf7] px-4 py-2 text-sm font-medium text-[#5f4d52]"
            >
              Orders
            </Link>
          </nav>
        </header>


        {
          error
          && (
            <div className="mb-6 rounded-2xl border border-[#e4aaa3] bg-[#fff2ef] px-4 py-3 text-sm text-[#9b352e]">
              {
                error
              }
            </div>
          )
        }


        <section className="mb-8 rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-4 shadow-sm sm:p-6">
          <h2 className="text-xl font-semibold text-[#332e34]">
            Create alert
          </h2>

          <p className="mt-2 text-sm leading-6 text-[#756369]">
            Choose what Retailigent should watch for.
          </p>


          <div className="mt-6">
            <label className="block text-sm font-medium text-[#332e34]">
              Variant UUID
            </label>

            <input
              value={
                variantId
              }
              onChange={(
                event
              ) => {
                setVariantId(
                  event.target.value
                );
              }}
              placeholder="Variant UUID"
              className="mt-2 min-h-11 w-full min-w-0 rounded-xl border border-[#d8c8c1] bg-white px-3 py-2.5 text-base outline-none transition placeholder:text-[#ad999e] focus:border-[#7779de] sm:text-sm"
            />
          </div>


          <div className="mt-5">
            <label className="block text-sm font-medium text-[#332e34]">
              Alert type
            </label>

            <select
              value={
                alertType
              }
              onChange={(
                event
              ) => {
                const value =
                  event.target
                    .value as AlertType;

                setAlertType(
                  value
                );

                if (
                  value
                  !== "price_drop"
                ) {
                  setTargetPrice("");
                }
              }}
              className="mt-2 min-h-11 w-full rounded-xl border border-[#d8c8c1] bg-white px-3 py-2.5 text-base outline-none focus:border-[#7779de] sm:text-sm"
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


          {
            alertType
            === "price_drop"
            && (
              <div className="mt-5">
                <label className="block text-sm font-medium text-[#332e34]">
                  Target price
                </label>

                <input
                  type="number"
                  min={0}
                  value={
                    targetPrice
                  }
                  onChange={(
                    event
                  ) => {
                    setTargetPrice(
                      event.target.value
                    );
                  }}
                  placeholder="3000"
                  className="mt-2 min-h-11 w-full rounded-xl border border-[#d8c8c1] bg-white px-3 py-2.5 text-base outline-none focus:border-[#7779de] sm:text-sm"
                />

                <p className="mt-2 text-xs leading-5 text-[#8c777c]">
                  The alert triggers when the effective
                  price reaches this amount or lower.
                </p>
              </div>
            )
          }


          {
            alertType
            === "restock"
            && (
              <div className="mt-5 rounded-xl border border-[#d8c8c1] bg-white p-4 text-sm leading-6 text-[#756369]">
                Retailigent will notify you when this
                variant is restocked.
              </div>
            )
          }


          {
            alertType
            === "sale"
            && (
              <div className="mt-5 rounded-xl border border-[#d8c8c1] bg-white p-4 text-sm leading-6 text-[#756369]">
                Retailigent will notify you when a sale
                starts for this variant.
              </div>
            )
          }


          <button
            type="button"
            disabled={
              busy
              === "create"
            }
            onClick={() => {
              void handleCreate();
            }}
            className="mt-6 min-h-11 w-full rounded-xl bg-[#ce4d42] px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-[#ad3d34] disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
          >
            {
              busy
              === "create"
                ? "Creating..."
                : "Create alert"
            }
          </button>
        </section>


        <section>
          <div className="mb-4 flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
            <h2 className="text-xl font-semibold text-[#332e34]">
              Your alerts
            </h2>

            <span className="text-xs text-[#8c777c]">
              Auto-refreshes every 5 seconds
            </span>
          </div>


          {
            loading
            && (
              <div className="rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-5 text-sm text-[#756369] shadow-sm">
                Loading alerts...
              </div>
            )
          }


          {
            !loading
            &&
            !error
            &&
            data?.items.length
            === 0
            && (
              <div className="rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-5 shadow-sm sm:p-6">
                <h3 className="text-lg font-semibold text-[#332e34]">
                  No alerts yet
                </h3>

                <p className="mt-2 text-sm leading-6 text-[#756369]">
                  Create your first alert above.
                </p>
              </div>
            )
          }


          {
            !loading
            &&
            data
            &&
            data.items.length
            > 0
            && (
              <div className="space-y-4 sm:space-y-5">
                {
                  data.items.map(
                    (
                      alert
                    ) => (
                      <AlertBlock
                        key={
                          alert.id
                        }
                        alert={
                          alert
                        }
                        busy={
                          busy
                          === alert.id
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
                  )
                }
              </div>
            )
          }
        </section>
      </div>
    </main>
  );
}