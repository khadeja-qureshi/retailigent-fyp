"use client";

import {
  CartResponse,
} from "@/lib/api";


interface Props {
  data: CartResponse;

  busyItemId?:
    string | null;

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
  if (
    data.items.length
    === 0
  ) {
    return (
      <section className="rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-5 shadow-sm sm:p-6">
        <h2 className="text-xl font-semibold text-[#332e34]">
          Your cart
        </h2>

        <p className="mt-3 text-sm text-[#756369]">
          Your cart is empty.
        </p>
      </section>
    );
  }


  const total =
    data.items.reduce(
      (
        sum,
        item
      ) =>
        sum
        +
        (
          item.pricing
            ?.effective_price
          ?? 0
        )
        *
        item.quantity,
      0
    );


  return (
    <section className="min-w-0 rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-4 shadow-sm sm:p-6">
      <div className="flex items-center justify-between gap-4">
        <h2 className="text-xl font-semibold text-[#332e34]">
          Your cart
        </h2>

        <span className="shrink-0 text-sm text-[#756369]">
          {
            data.item_count
          }{" "}
          item
          {
            data.item_count
            === 1
              ? ""
              : "s"
          }
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

              const exceedsStock =
                item.quantity
                >
                available;


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

                    <strong className="shrink-0 text-base text-[#332e34]">
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


                  <p className="mt-4 text-sm leading-6 text-[#756369]">
                    Currently available at one branch:
                    {" "}
                    <strong className="text-[#332e34]">
                      up to{" "}
                      {
                        available
                      }
                    </strong>
                  </p>


                  {
                    exceedsStock
                    && (
                      <div className="mt-3 rounded-xl border border-[#ecd5a4] bg-[#fff8e8] px-3 py-2.5 text-sm leading-5 text-[#8a6424]">
                        Your cart quantity exceeds current
                        availability. Cart items do not
                        reserve stock.
                      </div>
                    )
                  }


                  <div className="mt-5 flex flex-wrap items-center gap-2 sm:gap-3">
                    <button
                      type="button"
                      aria-label="Decrease quantity"
                      disabled={
                        busyItemId
                        === item.id
                        ||
                        item.quantity
                        <= 1
                      }
                      onClick={() => {
                        onQuantityChange(
                          item.id,
                          item.quantity - 1
                        );
                      }}
                      className="flex h-11 w-11 items-center justify-center rounded-xl border border-[#d8c8c1] bg-[#fffaf7] text-lg font-medium transition hover:border-[#7779de] disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      −
                    </button>

                    <span className="min-w-9 text-center font-semibold text-[#332e34]">
                      {
                        item.quantity
                      }
                    </span>

                    <button
                      type="button"
                      aria-label="Increase quantity"
                      disabled={
                        busyItemId
                        === item.id
                      }
                      onClick={() => {
                        onQuantityChange(
                          item.id,
                          item.quantity + 1
                        );
                      }}
                      className="flex h-11 w-11 items-center justify-center rounded-xl border border-[#d8c8c1] bg-[#fffaf7] text-lg font-medium transition hover:border-[#7779de] disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      +
                    </button>

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
                      className="ml-auto min-h-11 rounded-xl px-3 text-sm font-medium text-[#b33d34] transition hover:bg-[#fff2ef] disabled:opacity-40"
                    >
                      {
                        busyItemId
                        === item.id
                          ? "Updating..."
                          : "Remove"
                      }
                    </button>
                  </div>
                </article>
              );
            }
          )
        }
      </div>


      <div className="mt-6 flex flex-col gap-2 border-t border-[#e2d5cf] pt-5 sm:flex-row sm:items-center sm:justify-between">
        <span className="text-sm text-[#756369]">
          Estimated total
        </span>

        <strong className="text-xl text-[#332e34]">
          Rs.{" "}
          {
            total.toLocaleString()
          }
        </strong>
      </div>


      <p className="mt-3 text-xs leading-5 text-[#8c777c]">
        Cart items do not reserve inventory.
        Availability may change before checkout.
      </p>
    </section>
  );
}