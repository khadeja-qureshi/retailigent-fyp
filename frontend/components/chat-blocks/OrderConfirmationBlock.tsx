"use client";

import { Order } from "@/lib/api";


interface Props {
  order: Order;
}


export default function OrderConfirmationBlock({
  order,
}: Props) {
  return (
    <section className="rounded-2xl border border-neutral-800 bg-neutral-900 p-6">
      <div>
        <p className="text-sm text-green-400">
          Purchase successful
        </p>

        <h2 className="mt-1 text-xl font-semibold">
          Order confirmed
        </h2>

        <p className="mt-2 text-sm text-neutral-400">
          Order #{order.id.slice(0, 8)}
        </p>
      </div>

      <div className="mt-6 space-y-4">
        {order.items.map((item) => (
          <article
            key={item.variant_id}
            className="rounded-xl border border-neutral-800 bg-neutral-950 p-5"
          >
            <div className="flex justify-between gap-4">
              <div>
                <h3 className="font-medium">
                  {item.product_snapshot
                    ?.product_name ??
                    "Product"}
                </h3>

                <p className="mt-1 text-sm text-neutral-500">
                  {item.product_snapshot
                    ?.variant_sku ??
                    item.variant_id}
                </p>
              </div>

              <strong>
                Rs.{" "}
                {item.line_total.toLocaleString()}
              </strong>
            </div>

            <p className="mt-3 text-sm text-neutral-400">
              Quantity: {item.quantity}
            </p>
          </article>
        ))}
      </div>

      <div className="mt-6 border-t border-neutral-800 pt-5">
        <div className="flex justify-between text-sm">
          <span className="text-neutral-400">
            Subtotal
          </span>

          <span>
            {order.currency}{" "}
            {order.subtotal.toLocaleString()}
          </span>
        </div>

        <div className="mt-2 flex justify-between text-sm">
          <span className="text-neutral-400">
            Discount
          </span>

          <span>
            {order.currency}{" "}
            {order.discount.toLocaleString()}
          </span>
        </div>

        <div className="mt-4 flex justify-between border-t border-neutral-800 pt-4">
          <span className="font-medium">
            Order total
          </span>

          <strong>
            {order.currency}{" "}
            {order.total.toLocaleString()}
          </strong>
        </div>
      </div>

      <p className="mt-4 text-xs text-neutral-500">
        Purchase completed through the Retailigent
        mock purchase system.
      </p>
    </section>
  );
}