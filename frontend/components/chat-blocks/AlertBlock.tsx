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
    alert.is_active && !triggered;

  const paused =
    !alert.is_active && !triggered;


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
              Rs.{" "}
              {alert.target_price
                .toLocaleString()}
            </strong>
          </p>
        )}

        {alert.effective_price != null && (
          <p>
            Current price:{" "}
            <strong>
              Rs.{" "}
              {alert.effective_price
                .toLocaleString()}
            </strong>
          </p>
        )}

      </div>


      {triggered && (
        <div className="mt-5 rounded-xl border border-green-900 bg-green-950/30 p-4 text-green-300">
          Alert condition matched.
        </div>
      )}


      <div className="mt-6 flex gap-3">

        {active && (
          <button
            disabled={busy}
            onClick={() =>
              onPause(alert.id)
            }
            className="rounded-lg border border-neutral-700 px-4 py-2"
          >
            Pause
          </button>
        )}


        {paused && (
          <button
            disabled={busy}
            onClick={() =>
              onResume(alert.id)
            }
            className="rounded-lg border border-neutral-700 px-4 py-2"
          >
            Resume
          </button>
        )}


        {!triggered && (
          <button
            disabled={busy}
            onClick={() =>
              onDelete(alert.id)
            }
            className="rounded-lg border border-red-900 px-4 py-2 text-red-300"
          >
            Delete
          </button>
        )}

      </div>

    </article>
  );
}