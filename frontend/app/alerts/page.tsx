"use client";

import {
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
  ] = useState("");

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
  ] = useState("");

  const [
    busy,
    setBusy,
  ] =
    useState<string | null>(null);

  const [
    error,
    setError,
  ] =
    useState<string | null>(null);


  async function loadAlerts() {
    try {
      setError(null);

      setData(
        await getAlerts()
      );

    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to load alerts."
      );
    }
  }


  useEffect(() => {
    loadAlerts();
  }, []);


  async function handleCreate() {
    if (!variantId.trim()) {
      setError(
        "Variant UUID is required."
      );
      return;
    }

    if (
      alertType === "price_drop"
      && !targetPrice
    ) {
      setError(
        "Price-drop alerts require a target price."
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
          alertType === "price_drop"
            ? Number(targetPrice)
            : null,
      });

      setVariantId("");
      setTargetPrice("");

      await loadAlerts();

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
    id: string
  ) {
    try {
      setBusy(id);

      await pauseAlert(id);

      await loadAlerts();

    } finally {
      setBusy(null);
    }
  }


  async function handleResume(
    id: string
  ) {
    try {
      setBusy(id);

      await resumeAlert(id);

      await loadAlerts();

    } finally {
      setBusy(null);
    }
  }


  async function handleDelete(
    id: string
  ) {
    try {
      setBusy(id);

      await deleteAlert(id);

      await loadAlerts();

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
              Alerts
            </h1>

            <p className="mt-2 text-neutral-400">
              Watch products for price drops,
              restocks, and sales.
            </p>
          </div>

          <Link
            href="/smart-cart"
            className="text-sm underline"
          >
            Smart Cart
          </Link>

        </div>


        {error && (
          <div className="mb-6 rounded-xl border border-red-900 bg-red-950/30 p-4 text-red-300">
            {error}
          </div>
        )}


        <section className="mb-8 rounded-2xl border border-neutral-800 bg-neutral-900 p-6">

          <h2 className="text-xl font-semibold">
            Create alert
          </h2>


          <label className="mt-5 block text-sm">
            Variant UUID
          </label>

          <input
            value={variantId}
            onChange={(event) =>
              setVariantId(
                event.target.value
              )
            }
            placeholder="Variant UUID"
            className="mt-2 w-full rounded-lg border border-neutral-700 bg-neutral-950 p-3"
          />


          <label className="mt-5 block text-sm">
            Alert type
          </label>

          <select
            value={alertType}
            onChange={(event) => {
  const value =
    event.target.value as AlertType;

  setAlertType(value);
}}
            className="mt-2 w-full rounded-lg border border-neutral-700 bg-neutral-950 p-3"
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


          {alertType === "price_drop" && (
            <>
              <label className="mt-5 block text-sm">
                Target price
              </label>

              <input
                type="number"
                min={0}
                value={targetPrice}
                onChange={(event) =>
                  setTargetPrice(
                    event.target.value
                  )
                }
                placeholder="3000"
                className="mt-2 w-full rounded-lg border border-neutral-700 bg-neutral-950 p-3"
              />
            </>
          )}


          <button
            disabled={
              busy === "create"
            }
            onClick={handleCreate}
            className="mt-6 rounded-lg bg-white px-5 py-3 font-medium text-black disabled:opacity-50"
          >
            {busy === "create"
              ? "Creating..."
              : "Create alert"}
          </button>

        </section>


        <h2 className="mb-4 text-xl font-semibold">
          Your alerts
        </h2>


        {!data ? (
          <p className="text-neutral-400">
            Loading alerts...
          </p>

        ) : data.items.length === 0 ? (
          <p className="text-neutral-400">
            No alerts yet.
          </p>

        ) : (
          <div className="space-y-4">

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

      </div>

    </main>
  );
}