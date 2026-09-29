"use client";

import {
  useEffect,
  useState,
} from "react";

import Link from "next/link";

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
  ] = useState("");

  const [
    quantity,
    setQuantity,
  ] = useState(1);

  const [
    inventory,
    setInventory,
  ] =
    useState<VariantInventoryRow[]>([]);

  const [
    branchId,
    setBranchId,
  ] = useState("");

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
    loadReservations();
  }, []);


  async function findBranches() {
    try {
      setError(null);

      const response =
        await getVariantInventory(
          variantId.trim()
        );

      const available =
        response.inventory.filter(
          (row) =>
            row.branch &&
            row.available_quantity > 0
        );

      setInventory(
        available
      );

      setBranchId(
        available[0]?.branch_id ?? ""
      );

      if (!available.length) {
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
    try {
      setError(null);
      setBusy("create");

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
      setBusy(id);

      await releaseReservation(id);

      await loadReservations();

      if (variantId.trim()) {
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
    <main className="min-h-screen bg-neutral-950 text-white">

      <div className="mx-auto max-w-3xl p-6 md:p-10">

        <div className="mb-8 flex justify-between">

          <div>
            <p className="text-sm text-neutral-500">
              Retailigent
            </p>

            <h1 className="text-3xl font-semibold">
              Reservations
            </h1>
          </div>

          <div className="flex gap-4 text-sm">
            <Link
              href="/cart"
              className="underline"
            >
              Cart
            </Link>

            <Link
              href="/wishlist"
              className="underline"
            >
              Wishlist
            </Link>
          </div>

        </div>

        {error && (
          <div className="mb-6 rounded-xl border border-red-900 bg-red-950/40 p-4 text-red-300">
            {error}
          </div>
        )}

        <section className="mb-8 rounded-2xl border border-neutral-800 bg-neutral-900 p-6">

          <h2 className="text-xl font-semibold">
            Hold an item
          </h2>

          <p className="mt-2 text-sm text-neutral-400">
            Cart items do not reserve stock.
            This action explicitly books inventory.
          </p>

          <input
            value={variantId}
            onChange={(event) => {
              setVariantId(
                event.target.value
              );

              setInventory([]);
              setBranchId("");
            }}
            placeholder="Variant UUID"
            className="mt-5 w-full rounded-lg border border-neutral-700 bg-neutral-950 p-3"
          />

          <button
            onClick={findBranches}
            className="mt-3 rounded-lg border border-neutral-700 px-4 py-2"
          >
            Find available branches
          </button>

          {inventory.length > 0 && (
            <>

              <label className="mt-5 block text-sm">
                Branch
              </label>

              <select
                value={branchId}
                onChange={(event) =>
                  setBranchId(
                    event.target.value
                  )
                }
                className="mt-2 w-full rounded-lg border border-neutral-700 bg-neutral-950 p-3"
              >

                {inventory.map(
                  (row) => (
                    <option
                      key={row.branch_id}
                      value={row.branch_id}
                    >
                      {row.branch?.name}
                      {" — "}
                      {row.available_quantity}
                      {" available"}
                    </option>
                  )
                )}

              </select>

              <label className="mt-5 block text-sm">
                Quantity
              </label>

              <input
                type="number"
                min={1}
                value={quantity}
                onChange={(event) =>
                  setQuantity(
                    Math.max(
                      1,
                      Number(
                        event.target.value
                      )
                    )
                  )
                }
                className="mt-2 w-28 rounded-lg border border-neutral-700 bg-neutral-950 p-3"
              />

              <button
                onClick={holdItem}
                disabled={
                  busy === "create"
                }
                className="mt-5 rounded-lg bg-white px-5 py-3 font-medium text-black disabled:opacity-50"
              >
                {busy === "create"
                  ? "Creating hold..."
                  : "Hold for 15 minutes"}
              </button>

            </>
          )}

        </section>

        <h2 className="mb-4 text-xl font-semibold">
          Reservation history
        </h2>

        {!reservations ? (
          <p>Loading...</p>
        ) : reservations.items.length === 0 ? (
          <p className="text-neutral-400">
            No reservations.
          </p>
        ) : (
          <div className="space-y-4">

            {reservations.items.map(
              (reservation) => (
                <ReservationBlock
                  key={reservation.id}
                  reservation={reservation}
                  busy={
                    busy === reservation.id
                  }
                  onRelease={
                    handleRelease
                  }
                />
              )
            )}

          </div>
        )}

      </div>

    </main>
  );
}