"use client";

import {
  WishlistResponse,
} from "@/lib/api";


interface Props {
  data: WishlistResponse;

  busyItemId?:
    string | null;

  onRemove: (
    itemId: string
  ) => void;
}


export default function WishlistBlock({
  data,
  busyItemId,
  onRemove,
}: Props) {
  if (
    data.items.length
    === 0
  ) {
    return (
      <section className="rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-5 shadow-sm sm:p-6">
        <h2 className="text-xl font-semibold text-[#332e34]">
          Wishlist
        </h2>

        <p className="mt-3 text-sm text-[#756369]">
          Your wishlist is empty.
        </p>
      </section>
    );
  }


  return (
    <section className="min-w-0 rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-4 shadow-sm sm:p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-[#332e34]">
          Wishlist
        </h2>

        <span className="text-sm text-[#756369]">
          {
            data.items.length
          }{" "}
          saved
        </span>
      </div>


      <div className="mt-5 space-y-3 sm:mt-6 sm:space-y-4">
        {
          data.items.map(
            (
              item
            ) => {
              const available =
                item.availability_hint
                  ?.max_available_at_one_branch
                ?? 0;


              return (
                <article
                  key={
                    item.id
                  }
                  className="min-w-0 rounded-2xl border border-[#e2d5cf] bg-white p-4 sm:p-5"
                >
                  <div className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <h3 className="break-words font-semibold text-[#332e34]">
                        {
                          item.product
                            ?.name
                          ??
                          "Product"
                        }
                      </h3>

                      <p className="mt-1 break-all text-xs text-[#8c777c] sm:text-sm">
                        {
                          item.variant
                            ?.sku
                        }
                      </p>
                    </div>

                    <strong className="shrink-0 text-[#332e34]">
                      Rs.{" "}
                      {
                        (
                          item.pricing
                            ?.effective_price
                          ?? 0
                        )
                          .toLocaleString()
                      }
                    </strong>
                  </div>


                  <div
                    className={
                      (
                        "mt-4 rounded-xl "
                        +
                        "px-3 py-2.5 "
                        +
                        "text-sm leading-5 "
                      )
                      +
                      (
                        available
                        > 0
                          ? (
                            "border border-[#cbdccf] "
                            +
                            "bg-[#f0f8f2] "
                            +
                            "text-[#42664a]"
                          )
                          : (
                            "border border-[#e4aaa3] "
                            +
                            "bg-[#fff2ef] "
                            +
                            "text-[#9b352e]"
                          )
                      )
                    }
                  >
                    {
                      available
                      > 0
                        ? (
                          `Up to ${available} currently available at one branch`
                        )
                        : "Currently unavailable"
                    }
                  </div>


                  <button
                    type="button"
                    disabled={
                      busyItemId
                      === item.id
                    }
                    onClick={() => {
                      onRemove(
                        item.id
                      );
                    }}
                    className="mt-4 min-h-11 rounded-xl px-3 text-sm font-medium text-[#b33d34] transition hover:bg-[#fff2ef] disabled:opacity-40"
                  >
                    {
                      busyItemId
                      === item.id
                        ? "Removing..."
                        : "Remove from wishlist"
                    }
                  </button>
                </article>
              );
            }
          )
        }
      </div>


      <p className="mt-5 text-xs leading-5 text-[#8c777c]">
        Wishlist items do not reserve stock.
      </p>
    </section>
  );
}