"use client";

import Link from "next/link";

import {
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
    useState<ReservationListResponse | null>(
      null
    );

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
    useState<VariantInventoryRow[]>(
      []
    );

  const [
    branchId,
    setBranchId,
  ] =
    useState("");

  const [
    error,
    setError,
  ] =
    useState<string | null>(
      null
    );

  const [
    busy,
    setBusy,
  ] =
    useState<string | null>(
      null
    );


  async function loadReservations() {
    try {
      setError(null);

      setReservations(
        await getReservations()
      );
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to load reservations."
      );
    }
  }


  useEffect(() => {
    queueMicrotask(() => {
      void loadReservations();
    });
  }, []);


  async function findBranches() {
    if (
      !variantId.trim()
    ) {
      return;
    }

    try {
      setError(null);

      const response =
        await getVariantInventory(
          variantId.trim()
        );

      const available =
        response.inventory.filter(
          (
            row
          ) =>
            row.branch
            &&
            row.available_quantity
            > 0
        );

      setInventory(
        available
      );

      setBranchId(
        available[0]
          ?.branch_id
        ?? ""
      );

      if (
        !available.length
      ) {
        setError(
          "No active branch currently has stock."
        );
      }
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to find stock."
      );
    }
  }


  async function holdItem() {
    if (
      !variantId.trim()
      ||
      !branchId
    ) {
      return;
    }

    try {
      setError(null);

      setBusy(
        "create"
      );

      await createReservation(
        variantId.trim(),
        branchId,
        quantity,
        15
      );

      await loadReservations();
      await findBranches();
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
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

      setBusy(
        id
      );

      await releaseReservation(
        id
      );

      await loadReservations();

      if (
        variantId.trim()
      ) {
        await findBranches();
      }
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to release reservation."
      );
    } finally {
      setBusy(null);
    }
  }


  return (
    <main className="min-h-[calc(100dvh-4rem)] overflow-x-hidden bg-[#f1e6de] text-[#2c1c20]">
      <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6 sm:py-8 lg:px-8 lg:py-10">

        <header className="mb-6 sm:mb-8">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#7f2a3c]">
                Inventory holds
              </p>

              <h1 className="mt-2 text-3xl font-bold sm:text-4xl">
                Reservations
              </h1>

              <p className="mt-2 max-w-2xl text-sm leading-6 text-[#756369] sm:text-base">
                Explicitly hold available inventory at
                a branch before the reservation expires.
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
              href="/wishlist"
              className="shrink-0 rounded-full border border-[#d8c8c1] bg-[#fffaf7] px-4 py-2 text-sm font-medium text-[#5f4d52]"
            >
              Wishlist
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
            Hold an item
          </h2>

          <p className="mt-2 text-sm leading-6 text-[#756369]">
            Cart items do not reserve stock.
            This action explicitly books inventory
            for 15 minutes.
          </p>


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

              setInventory([]);
              setBranchId("");
            }}
            placeholder="Variant UUID"
            className="mt-5 min-h-11 w-full rounded-xl border border-[#d8c8c1] bg-white px-3 py-2.5 text-base outline-none transition focus:border-[#7779de] sm:text-sm"
          />


          <button
            type="button"
            onClick={
              findBranches
            }
            disabled={
              !variantId.trim()
            }
            className="mt-3 min-h-11 w-full rounded-xl border border-[#7f2a3c] px-4 py-2.5 text-sm font-semibold text-[#7f2a3c] transition hover:bg-[#f7e9e8] disabled:opacity-40 sm:w-auto"
          >
            Find available branches
          </button>


          {
            inventory.length
            > 0
            && (
              <div className="mt-6 rounded-2xl border border-[#e2d5cf] bg-white p-4 sm:p-5">
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
                  className="mt-2 min-h-11 w-full rounded-xl border border-[#d8c8c1] bg-white px-3 py-2.5 text-base outline-none focus:border-[#7779de] sm:text-sm"
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
                            row.branch
                              ?.name
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
                  className="mt-5 block text-sm font-medium text-[#332e34]"
                >
                  Quantity
                </label>

                <input
                  id="reservation-quantity"
                  type="number"
                  min={1}
                  value={
                    quantity
                  }
                  onChange={(
                    event
                  ) => {
                    setQuantity(
                      Math.max(
                        1,
                        Number(
                          event.target.value
                        )
                      )
                    );
                  }}
                  className="mt-2 min-h-11 w-full rounded-xl border border-[#d8c8c1] bg-white px-3 py-2.5 text-base outline-none focus:border-[#7779de] sm:w-32 sm:text-sm"
                />


                <button
                  type="button"
                  onClick={
                    holdItem
                  }
                  disabled={
                    busy
                    === "create"
                    ||
                    !branchId
                  }
                  className="mt-5 min-h-11 w-full rounded-xl bg-[#ce4d42] px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-[#ad3d34] disabled:opacity-50 sm:w-auto"
                >
                  {
                    busy
                    === "create"
                      ? "Creating hold..."
                      : "Hold for 15 minutes"
                  }
                </button>
              </div>
            )
          }
        </section>


        <section>
          <h2 className="mb-4 text-xl font-semibold text-[#332e34]">
            Reservation history
          </h2>


          {
            !reservations
              ? (
                <div className="rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-5 text-sm text-[#756369] shadow-sm">
                  Loading reservations...
                </div>
              )
              : reservations.items.length
                === 0
                ? (
                  <div className="rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-5 text-sm text-[#756369] shadow-sm">
                    No reservations yet.
                  </div>
                )
                : (
                  <div className="space-y-4">
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