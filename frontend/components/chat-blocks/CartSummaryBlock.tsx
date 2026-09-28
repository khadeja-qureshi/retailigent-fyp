"use client";

import {
  CartResponse,
} from "@/lib/api";


interface Props {
  data: CartResponse;
  busyItemId?: string | null;

  onQuantityChange: (
    itemId: string,
    quantity: number
  ) => void;

  onRemove: (
    itemId: string
  ) => void;
}


export default function CartSummaryBlock({
  data,
  busyItemId,
  onQuantityChange,
  onRemove,
}: Props) {
  if (data.items.length === 0) {
    return (
      <div className="rounded-2xl border border-neutral-800 bg-neutral-900 p-6">
        <h2 className="text-xl font-semibold">
          Your cart
        </h2>

        <p className="mt-3 text-neutral-400">
          Your cart is empty.
        </p>
      </div>
    );
  }

  const total = data.items.reduce(
    (sum, item) =>
      sum +
      (item.pricing?.effective_price ?? 0) *
        item.quantity,
    0
  );

  return (
    <section className="rounded-2xl border border-neutral-800 bg-neutral-900 p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">
          Your cart
        </h2>

        <span className="text-sm text-neutral-400">
          {data.item_count} item
          {data.item_count === 1 ? "" : "s"}
        </span>
      </div>

      <div className="mt-6 space-y-4">
        {data.items.map((item) => {
          const available =
            item.availability_hint
              ?.max_available_at_one_branch ?? 0;

          const exceedsStock =
            item.quantity > available;

          return (
            <article
              key={item.id}
              className="rounded-xl border border-neutral-800 bg-neutral-950 p-5"
            >
              <div className="flex justify-between gap-4">
                <div>
                  <h3 className="font-medium">
                    {item.product?.name ??
                      "Product"}
                  </h3>

                  <p className="mt-1 text-sm text-neutral-500">
                    {item.variant?.sku}
                  </p>
                </div>

                <strong>
                  Rs.{" "}
                  {(
                    item.pricing
                      ?.effective_price ?? 0
                  ).toLocaleString()}
                </strong>
              </div>

              <p className="mt-4 text-sm text-neutral-400">
                Currently available at one
                branch: up to {available}
              </p>

              {exceedsStock && (
                <p className="mt-2 text-sm text-amber-400">
                  Your cart quantity exceeds
                  current availability. Stock is
                  not reserved until a later
                  reservation or purchase step.
                </p>
              )}

              <div className="mt-5 flex items-center gap-3">
                <button
                  disabled={
                    busyItemId === item.id ||
                    item.quantity <= 1
                  }
                  onClick={() =>
                    onQuantityChange(
                      item.id,
                      item.quantity - 1
                    )
                  }
                  className="h-9 w-9 rounded-lg border border-neutral-700 disabled:opacity-40"
                >
                  −
                </button>

                <span className="min-w-8 text-center">
                  {item.quantity}
                </span>

                <button
                  disabled={
                    busyItemId === item.id
                  }
                  onClick={() =>
                    onQuantityChange(
                      item.id,
                      item.quantity + 1
                    )
                  }
                  className="h-9 w-9 rounded-lg border border-neutral-700 disabled:opacity-40"
                >
                  +
                </button>

                <button
                  disabled={
                    busyItemId === item.id
                  }
                  onClick={() =>
                    onRemove(item.id)
                  }
                  className="ml-auto text-sm text-red-400 disabled:opacity-40"
                >
                  Remove
                </button>
              </div>
            </article>
          );
        })}
      </div>

      <div className="mt-6 flex justify-between border-t border-neutral-800 pt-5">
        <span className="text-neutral-400">
          Estimated total
        </span>

        <strong>
          Rs. {total.toLocaleString()}
        </strong>
      </div>

      <p className="mt-3 text-xs text-neutral-500">
        Cart items do not reserve inventory.
        Availability may change before checkout.
      </p>
    </section>
  );
}