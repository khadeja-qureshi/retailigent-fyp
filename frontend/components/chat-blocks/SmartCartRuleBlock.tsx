"use client";

import {
  SmartCartRule,
} from "@/lib/api";


interface Props {
  rule: SmartCartRule;
  busy?: boolean;

  onPause: (
    id: string
  ) => void;

  onResume: (
    id: string
  ) => void;

  onCancel: (
    id: string
  ) => void;
}


function money(
  value?: number | null
) {
  if (value == null) {
    return "—";
  }

  return `Rs. ${value.toLocaleString()}`;
}


export default function SmartCartRuleBlock({
  rule,
  busy = false,
  onPause,
  onResume,
  onCancel,
}: Props) {
  const active =
    rule.status === "active";

  const paused =
    rule.status === "paused";

  const completed =
    rule.status === "completed";

  const triggered =
    rule.status === "triggered";


  return (
    <article className="rounded-2xl border border-neutral-800 bg-neutral-900 p-6">

      <div className="flex items-start justify-between gap-4">

        <div>
          <p className="text-xs uppercase tracking-wide text-neutral-500">
            Smart Cart
          </p>

          <h3 className="mt-2 text-xl font-semibold">
            {rule.product?.name ??
              "Smart Cart item"}
          </h3>

          <p className="mt-1 text-sm text-neutral-500">
            {rule.variant?.sku ??
              rule.variant_id}
          </p>
        </div>

        <span className="rounded-full border border-neutral-700 px-3 py-1 text-xs capitalize">
          {rule.status}
        </span>

      </div>


      <div className="mt-5 space-y-2 text-sm">

        <p>
          Quantity:{" "}
          <strong>
            {rule.quantity}
          </strong>
        </p>

        {rule.target_price != null && (
          <p>
            Target price:{" "}
            <strong>
              {money(
                rule.target_price
              )}
            </strong>
          </p>
        )}

        {rule.min_discount_percentage != null && (
          <p>
            Minimum discount:{" "}
            <strong>
              {rule.min_discount_percentage}%
            </strong>
          </p>
        )}

        <p>
          Current price:{" "}
          <strong>
            {money(
              rule.effective_price
            )}
          </strong>
        </p>

        <p>
          Mode:{" "}
          <strong>
            {rule.authorization_mode
              === "auto_buy"
              ? "Auto Buy"
              : "Notify Only"}
          </strong>
        </p>

        {rule.branch && (
          <p>
            Branch:{" "}
            <strong>
              {rule.branch.name}
            </strong>
          </p>
        )}

      </div>


      {completed && (
        <div className="mt-5 rounded-xl border border-green-900 bg-green-950/30 p-4 text-green-300">
          Purchase completed automatically.
        </div>
      )}


      {triggered && (
        <div className="mt-5 rounded-xl border border-amber-900 bg-amber-950/30 p-4 text-amber-300">
          Conditions matched. Processing action...
        </div>
      )}


      <div className="mt-6 flex flex-wrap gap-3">

        {active && (
          <button
            disabled={busy}
            onClick={() =>
              onPause(rule.id)
            }
            className="rounded-lg border border-neutral-700 px-4 py-2 hover:bg-neutral-800 disabled:opacity-50"
          >
            Pause
          </button>
        )}

        {paused && (
          <button
            disabled={busy}
            onClick={() =>
              onResume(rule.id)
            }
            className="rounded-lg border border-neutral-700 px-4 py-2 hover:bg-neutral-800 disabled:opacity-50"
          >
            Resume
          </button>
        )}

        {(active || paused) && (
          <button
            disabled={busy}
            onClick={() =>
              onCancel(rule.id)
            }
            className="rounded-lg border border-red-900 px-4 py-2 text-red-300 hover:bg-red-950/30 disabled:opacity-50"
          >
            Cancel
          </button>
        )}

      </div>

    </article>
  );
}