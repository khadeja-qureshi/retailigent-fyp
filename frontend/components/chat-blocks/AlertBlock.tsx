"use client";

import {
  RetailAlert,
} from "@/lib/api";


interface Props {
  alert: RetailAlert;
  busy?: boolean;

  onPause: (
    id: string
  ) => void;

  onResume: (
    id: string
  ) => void;

  onDelete: (
    id: string
  ) => void;
}


function alertLabel(
  type: RetailAlert["alert_type"]
) {
  if (type === "price_drop") {
    return "Price drop";
  }

  if (type === "restock") {
    return "Restock";
  }

  return "Sale";
}


function money(
  value?: number | null
) {
  if (value == null) {
    return "—";
  }

  return `Rs. ${value.toLocaleString()}`;
}


export default function AlertBlock({
  alert,
  busy = false,
  onPause,
  onResume,
  onDelete,
}: Props) {
  const triggered =
    Boolean(alert.triggered_at);

  const active =
    alert.is_active &&
    !triggered;

  const paused =
    !alert.is_active &&
    !triggered;


  return (
    <article className="rounded-2xl border border-neutral-800 bg-neutral-900 p-6">

      <div className="flex items-start justify-between gap-4">

        <div>
          <p className="text-xs uppercase tracking-wide text-neutral-500">
            Alert
          </p>

          <h3 className="mt-2 text-xl font-semibold">
            {alert.product?.name ??
              "Product alert"}
          </h3>

          <p className="mt-1 text-sm text-neutral-500">
            {alert.variant?.sku ??
              alert.variant_id}
          </p>
        </div>


        <span className="rounded-full border border-neutral-700 px-3 py-1 text-xs">

          {triggered
            ? "Triggered"
            : active
              ? "Watching"
              : "Paused"}

        </span>

      </div>


      <div className="mt-5 space-y-2 text-sm">

        <p>
          Alert type:{" "}
          <strong>
            {alertLabel(
              alert.alert_type
            )}
          </strong>
        </p>


        {alert.target_price != null && (
          <p>
            Target:{" "}
            <strong>
              {money(
                alert.target_price
              )}
            </strong>
          </p>
        )}


        {alert.effective_price != null && (
          <p>
            Current price:{" "}
            <strong>
              {money(
                alert.effective_price
              )}
            </strong>
          </p>
        )}

      </div>


      {triggered && (
        <div className="mt-5 rounded-xl border border-green-900 bg-green-950/30 p-4 text-green-300">

          Alert condition matched.

        </div>
      )}


      {paused && (
        <div className="mt-5 rounded-xl border border-neutral-700 bg-neutral-950 p-4 text-neutral-400">

          Alert monitoring is paused.

        </div>
      )}


      <div className="mt-6 flex flex-wrap gap-3">

        {active && (
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              onPause(
                alert.id
              );
            }}
            className="rounded-lg border border-neutral-700 px-4 py-2 hover:bg-neutral-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy
              ? "Working..."
              : "Pause"}
          </button>
        )}


        {paused && (
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              onResume(
                alert.id
              );
            }}
            className="rounded-lg border border-neutral-700 px-4 py-2 hover:bg-neutral-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy
              ? "Working..."
              : "Resume"}
          </button>
        )}


        {!triggered && (
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              onDelete(
                alert.id
              );
            }}
            className="rounded-lg border border-red-900 px-4 py-2 text-red-300 hover:bg-red-950/30 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy
              ? "Working..."
              : "Delete"}
          </button>
        )}

      </div>

    </article>
  );
}