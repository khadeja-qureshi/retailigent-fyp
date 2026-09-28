"use client";

import {
  WishlistResponse,
} from "@/lib/api";


interface Props {
  data: WishlistResponse;
  busyItemId?: string | null;

  onRemove: (
    itemId: string
  ) => void;
}


export default function WishlistBlock({
  data,
  busyItemId,
  onRemove,
}: Props) {
  if (data.items.length === 0) {
    return (
      <section className="rounded-2xl border border-neutral-800 bg-neutral-900 p-6">
        <h2 className="text-xl font-semibold">
          Wishlist
        </h2>

        <p className="mt-3 text-neutral-400">
          Your wishlist is empty.
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-neutral-800 bg-neutral-900 p-6">
      <h2 className="text-xl font-semibold">
        Wishlist
      </h2>

      <div className="mt-6 space-y-4">
        {data.items.map((item) => {
          const available =
            item.availability_hint
              ?.max_available_at_one_branch ?? 0;

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
                {available > 0
                  ? `Up to ${available} currently available at one branch`
                  : "Currently unavailable"}
              </p>

              <button
                disabled={
                  busyItemId === item.id
                }
                onClick={() =>
                  onRemove(item.id)
                }
                className="mt-4 text-sm text-red-400 disabled:opacity-40"
              >
                Remove from wishlist
              </button>
            </article>
          );
        })}
      </div>

      <p className="mt-5 text-xs text-neutral-500">
        Wishlist items do not reserve stock.
      </p>
    </section>
  );
}