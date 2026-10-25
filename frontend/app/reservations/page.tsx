"use client";

import Link from "next/link";

import {
  useCallback,
  useEffect,
  useState,
} from "react";

import ReservationBlock from "@/components/chat-blocks/ReservationBlock";

import {
  ReservationListResponse,
  VariantInventoryRow,
  createReservation,
  getReservations,
  getVariantInventory,
  releaseReservation,
} from "@/lib/api";


export default function ReservationsPage() {
  const [
    reservations,
    setReservations,
  ] =
    useState<ReservationListResponse>({
      items: [],
      count: 0,
    });


  const [
    loadingReservations,
    setLoadingReservations,
  ] =
    useState(true);


  const [
    variantId,
    setVariantId,
  ] =
    useState("");


  const [
    quantity,
    setQuantity,
  ] =
    useState(1);


  const [
    inventory,
    setInventory,
  ] =
    useState<VariantInventoryRow[]>([]);


  const [
    branchId,
    setBranchId,
  ] =
    useState("");


  const [
    error,
    setError,
  ] =
    useState<string | null>(null);


  const [
    busy,
    setBusy,
  ] =
    useState<string | null>(null);


  const loadReservations =
    useCallback(
      async () => {
        setLoadingReservations(true);

        try {
          setError(null);

          const response =
            await getReservations();

          setReservations(response);

        } catch (caught) {
          setReservations({
            items: [],
            count: 0,
          });

          setError(
            caught instanceof Error
              ? caught.message
              : "Unable to load reservations."
          );

        } finally {
          setLoadingReservations(false);
        }
      },
      []
    );


  useEffect(() => {
    void loadReservations();
  }, [
    loadReservations,
  ]);


  async function findBranches() {
    const trimmedVariantId =
      variantId.trim();


    if (!trimmedVariantId) {
      setError(
        "Enter a variant UUID first."
      );

      return;
    }


    try {
      setError(null);

      setBusy(
        "find-branches"
      );


      const response =
        await getVariantInventory(
          trimmedVariantId
        );


      const available =
        response.inventory.filter(
          (
            row
          ) =>
            Boolean(row.branch)
            &&
            row.available_quantity > 0
        );


      setInventory(
        available
      );


      setBranchId(
        available[0]?.branch_id
        ??
        ""
      );


      if (
        available.length === 0
      ) {
        setError(
          "No active branch currently has stock for this variant."
        );
      }

    } catch (caught) {
      setInventory([]);

      setBranchId("");

      setError(
        caught instanceof Error
          ? caught.message
          : "Unable to find stock."
      );

    } finally {
      setBusy(null);
    }
  }


  async function holdItem() {
    const trimmedVariantId =
      variantId.trim();


    if (!trimmedVariantId) {
      setError(
        "Enter a variant UUID first."
      );

      return;
    }


    if (!branchId) {
      setError(
        "Find and select an available branch first."
      );

      return;
    }


    if (
      !Number.isFinite(quantity)
      ||
      quantity < 1
    ) {
      setError(
        "Quantity must be at least 1."
      );

      return;
    }


    try {
      setError(null);

      setBusy(
        "create"
      );


      await createReservation(
        trimmedVariantId,
        branchId,
        quantity,
        15
      );


      await loadReservations();


      try {
        const response =
          await getVariantInventory(
            trimmedVariantId
          );


        const available =
          response.inventory.filter(
            (
              row
            ) =>
              Boolean(row.branch)
              &&
              row.available_quantity > 0
          );


        setInventory(
          available
        );


        setBranchId(
          available[0]?.branch_id
          ??
          ""
        );

      } catch {
        setInventory([]);

        setBranchId("");
      }

    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Unable to reserve item."
      );

    } finally {
      setBusy(null);
    }
  }


  async function handleRelease(
    id: string
  ) {
    try {
      setError(null);

      setBusy(id);


      await releaseReservation(
        id
      );


      await loadReservations();


      if (
        variantId.trim()
      ) {
        try {
          const response =
            await getVariantInventory(
              variantId.trim()
            );


          const available =
            response.inventory.filter(
              (
                row
              ) =>
                Boolean(row.branch)
                &&
                row.available_quantity > 0
            );


          setInventory(
            available
          );


          setBranchId(
            available[0]?.branch_id
            ??
            ""
          );

        } catch {
          setInventory([]);

          setBranchId("");
        }
      }

    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Unable to release reservation."
      );

    } finally {
      setBusy(null);
    }
  }


  return (
    <main className="min-h-[calc(100dvh-3.5rem)] overflow-x-hidden bg-[#f1e6de] text-[#2c1c20]">

      <div className="mx-auto w-full max-w-5xl px-4 py-5 sm:px-6 lg:px-8">

        <header className="mb-5">

          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">

            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#7779de]">
                Inventory holds
              </p>


              <h1 className="mt-1.5 text-3xl font-bold">
                Reservations
              </h1>


              <p className="mt-1.5 max-w-2xl text-sm leading-6 text-[#756369]">
                Explicitly hold available inventory at a branch before the
                reservation expires.
              </p>
            </div>


            <Link
              href="/chat"
              className="inline-flex min-h-10 w-full items-center justify-center rounded-xl bg-[#332e34] px-5 py-2 text-sm font-semibold text-white transition hover:bg-[#4a4148] sm:w-auto"
            >
              Ask assistant
            </Link>

          </div>


          <nav className="mt-4 flex gap-2 overflow-x-auto pb-1 sm:flex-wrap sm:overflow-visible">

            <Link
              href="/cart"
              className="shrink-0 rounded-full border border-[#d8c8c1] bg-[#fffaf7] px-4 py-2 text-sm font-medium text-[#5f4d52] transition hover:border-[#7779de]"
            >
              Cart
            </Link>


            <Link
              href="/wishlist"
              className="shrink-0 rounded-full border border-[#d8c8c1] bg-[#fffaf7] px-4 py-2 text-sm font-medium text-[#5f4d52] transition hover:border-[#7779de]"
            >
              Wishlist
            </Link>


            <Link
              href="/orders"
              className="shrink-0 rounded-full border border-[#d8c8c1] bg-[#fffaf7] px-4 py-2 text-sm font-medium text-[#5f4d52] transition hover:border-[#7779de]"
            >
              Orders
            </Link>

          </nav>

        </header>


        {
          error
          && (
            <div
              role="alert"
              className="mb-5 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
            >
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">

                <div>
                  <p className="font-semibold">
                    Something went wrong
                  </p>

                  <p className="mt-1">
                    {error}
                  </p>
                </div>


                <button
                  type="button"
                  onClick={() => {
                    void loadReservations();
                  }}
                  disabled={
                    loadingReservations
                  }
                  className="shrink-0 rounded-lg border border-red-300 bg-white px-3 py-2 text-xs font-semibold text-red-800 transition hover:bg-red-100 disabled:opacity-50"
                >
                  Retry
                </button>

              </div>
            </div>
          )
        }


        <section className="mb-6 rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-4 shadow-sm sm:p-5">

          <h2 className="text-lg font-semibold text-[#332e34]">
            Hold an item
          </h2>


          <p className="mt-1 text-sm leading-6 text-[#756369]">
            Cart items do not reserve stock. This action explicitly books
            inventory for 15 minutes.
          </p>


          <div className="mt-4">

            <label
              htmlFor="reservation-variant"
              className="mb-1.5 block text-xs font-semibold uppercase tracking-[0.1em] text-[#756369]"
            >
              Variant ID
            </label>


            <input
              id="reservation-variant"
              value={
                variantId
              }
              onChange={(
                event
              ) => {
                setVariantId(
                  event.target.value
                );

                setInventory([]);

                setBranchId("");

                setError(null);
              }}
              placeholder="Variant UUID"
              autoComplete="off"
              className="min-h-10 w-full rounded-xl border border-[#d8c8c1] bg-white px-3 py-2 text-sm outline-none transition placeholder:text-[#a4969a] focus:border-[#7779de] focus:ring-2 focus:ring-[#7779de]/10"
            />

          </div>


          <button
            type="button"
            onClick={() => {
              void findBranches();
            }}
            disabled={
              !variantId.trim()
              ||
              busy === "find-branches"
            }
            className="mt-3 inline-flex min-h-10 w-full items-center justify-center rounded-xl border border-[#7779de] px-4 py-2 text-sm font-semibold text-[#6667ca] transition hover:bg-[#f3f2ff] disabled:cursor-not-allowed disabled:opacity-40 sm:w-auto"
          >
            {
              busy === "find-branches"
                ? "Checking stock..."
                : "Find available branches"
            }
          </button>


          {
            inventory.length > 0
            && (
              <div className="mt-5 rounded-2xl border border-[#e2d5cf] bg-white p-4">

                <label
                  htmlFor="reservation-branch"
                  className="block text-sm font-medium text-[#332e34]"
                >
                  Branch
                </label>


                <select
                  id="reservation-branch"
                  value={
                    branchId
                  }
                  onChange={(
                    event
                  ) => {
                    setBranchId(
                      event.target.value
                    );
                  }}
                  className="mt-2 min-h-10 w-full rounded-xl border border-[#d8c8c1] bg-white px-3 py-2 text-sm outline-none focus:border-[#7779de]"
                >
                  {
                    inventory.map(
                      (
                        row
                      ) => (
                        <option
                          key={
                            row.branch_id
                          }
                          value={
                            row.branch_id
                          }
                        >
                          {
                            row.branch?.name
                            ??
                            "Branch"
                          }
                          {" — "}
                          {
                            row.available_quantity
                          }
                          {" available"}
                        </option>
                      )
                    )
                  }
                </select>


                <label
                  htmlFor="reservation-quantity"
                  className="mt-4 block text-sm font-medium text-[#332e34]"
                >
                  Quantity
                </label>


                <input
                  id="reservation-quantity"
                  type="number"
                  min={1}
                  step={1}
                  value={
                    quantity
                  }
                  onChange={(
                    event
                  ) => {
                    const nextQuantity =
                      Number(
                        event.target.value
                      );


                    setQuantity(
                      Number.isFinite(
                        nextQuantity
                      )
                        ? Math.max(
                          1,
                          Math.floor(
                            nextQuantity
                          )
                        )
                        : 1
                    );
                  }}
                  className="mt-2 min-h-10 w-full rounded-xl border border-[#d8c8c1] bg-white px-3 py-2 text-sm outline-none focus:border-[#7779de] sm:w-32"
                />


                <button
                  type="button"
                  onClick={() => {
                    void holdItem();
                  }}
                  disabled={
                    busy === "create"
                    ||
                    !branchId
                  }
                  className="mt-4 inline-flex min-h-10 w-full items-center justify-center rounded-xl bg-[#ce4d42] px-5 py-2 text-sm font-semibold text-white transition hover:bg-[#ad3d34] disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
                >
                  {
                    busy === "create"
                      ? "Creating hold..."
                      : "Hold for 15 minutes"
                  }
                </button>

              </div>
            )
          }

        </section>


        <section>

          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">

            <div>
              <h2 className="text-lg font-semibold text-[#332e34]">
                Reservation history
              </h2>

              {
                !loadingReservations
                && reservations.count > 0
                && (
                  <p className="mt-1 text-xs text-[#756369]">
                    {
                      reservations.count
                    }
                    {
                      reservations.count === 1
                        ? " reservation"
                        : " reservations"
                    }
                  </p>
                )
              }
            </div>


            <button
              type="button"
              onClick={() => {
                void loadReservations();
              }}
              disabled={
                loadingReservations
              }
              className="rounded-lg border border-[#d8c8c1] bg-[#fffaf7] px-3 py-2 text-xs font-semibold text-[#5f4d52] transition hover:border-[#7779de] hover:text-[#6667ca] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {
                loadingReservations
                  ? "Refreshing..."
                  : "Refresh"
              }
            </button>

          </div>


          {
            loadingReservations
              ? (
                <div
                  role="status"
                  className="rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-5 text-sm text-[#756369] shadow-sm"
                >
                  <div className="flex items-center gap-3">

                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-[#7779de]/20 border-t-[#7779de]" />

                    <span>
                      Loading reservations...
                    </span>

                  </div>
                </div>
              )
              : reservations.items.length === 0
                ? (
                  <div className="rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-5 shadow-sm">

                    <p className="text-sm font-medium text-[#45353a]">
                      No reservations yet.
                    </p>


                    <p className="mt-1 text-sm leading-6 text-[#756369]">
                      When you reserve an available product, the hold will
                      appear here.
                    </p>


                    <Link
                      href="/chat"
                      className="mt-3 inline-flex text-sm font-semibold text-[#6667ca] hover:underline"
                    >
                      Ask the assistant to find a product →
                    </Link>

                  </div>
                )
                : (
                  <div className="space-y-3">

                    {
                      reservations.items.map(
                        (
                          reservation
                        ) => (
                          <ReservationBlock
                            key={
                              reservation.id
                            }
                            reservation={
                              reservation
                            }
                            busy={
                              busy
                              === reservation.id
                            }
                            onRelease={
                              handleRelease
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