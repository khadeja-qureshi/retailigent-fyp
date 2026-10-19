"use client";

import {
  Order,
} from "@/lib/api";


interface Props {
  order:
    Order;
}


export default function OrderConfirmationBlock({
  order,
}: Props) {
  return (
    <section className="min-w-0 rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-4 shadow-sm sm:p-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-[#4e7658]">
            Purchase successful
          </p>

          <h2 className="mt-1 text-xl font-semibold text-[#332e34]">
            Order confirmed
          </h2>

          <p className="mt-2 break-all text-xs text-[#8c777c] sm:text-sm">
            Order #
            {
              order.id.slice(
                0,
                8
              )
            }
          </p>
        </div>

        <span className="w-fit rounded-full bg-[#edf6ef] px-3 py-1.5 text-xs font-semibold text-[#4e7658]">
          Completed
        </span>
      </div>


      <div className="mt-5 space-y-3 sm:mt-6 sm:space-y-4">
        {
          order.items.map(
            (
              item
            ) => (
              <article
                key={
                  item.variant_id
                }
                className="min-w-0 rounded-2xl border border-[#e2d5cf] bg-white p-4 sm:p-5"
              >
                <div className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <h3 className="break-words font-semibold text-[#332e34]">
                      {
                        item.product_snapshot
                          ?.product_name
                        ??
                        "Product"
                      }
                    </h3>

                    <p className="mt-1 break-all text-xs text-[#8c777c] sm:text-sm">
                      {
                        item.product_snapshot
                          ?.variant_sku
                        ??
                        item.variant_id
                      }
                    </p>
                  </div>

                  <strong className="shrink-0 text-[#332e34]">
                    Rs.{" "}
                    {
                      item.line_total
                        .toLocaleString()
                    }
                  </strong>
                </div>


                <p className="mt-3 text-sm text-[#756369]">
                  Quantity:{" "}
                  <strong className="text-[#332e34]">
                    {
                      item.quantity
                    }
                  </strong>
                </p>
              </article>
            )
          )
        }
      </div>


      <div className="mt-6 space-y-3 border-t border-[#e2d5cf] pt-5 text-sm">
        <div className="flex items-center justify-between gap-4">
          <span className="text-[#756369]">
            Subtotal
          </span>

          <span className="text-right text-[#332e34]">
            {
              order.currency
            }{" "}
            {
              order.subtotal
                .toLocaleString()
            }
          </span>
        </div>


        <div className="flex items-center justify-between gap-4">
          <span className="text-[#756369]">
            Discount
          </span>

          <span className="text-right text-[#332e34]">
            {
              order.currency
            }{" "}
            {
              order.discount
                .toLocaleString()
            }
          </span>
        </div>


        <div className="flex items-center justify-between gap-4 border-t border-[#e2d5cf] pt-4 text-base">
          <span className="font-semibold text-[#332e34]">
            Order total
          </span>

          <strong className="text-right text-[#332e34]">
            {
              order.currency
            }{" "}
            {
              order.total
                .toLocaleString()
            }
          </strong>
        </div>
      </div>


      <p className="mt-4 text-xs leading-5 text-[#8c777c]">
        Purchase completed through the Retailigent
        mock purchase system.
      </p>
    </section>
  );
}