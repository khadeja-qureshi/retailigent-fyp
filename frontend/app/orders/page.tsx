"use client";

import {
  useCallback,
  useEffect,
  useState,
} from "react";

import OrderConfirmationBlock from "@/components/chat-blocks/OrderConfirmationBlock";
import {
  getOrders,
  Order,
} from "@/lib/api";


export default function OrdersPage() {
  const [orders, setOrders] =
    useState<Order[]>([]);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState<string | null>(null);


  const loadOrders = useCallback(
    async (silent = false) => {
      try {
        if (!silent) {
          setLoading(true);
        }

        setError(null);

        const result =
          await getOrders();

        setOrders(result);

      } catch (error) {
        setError(
          error instanceof Error
            ? error.message
            : "Unable to load orders."
        );

      } finally {
        if (!silent) {
          setLoading(false);
        }
      }
    },
    []
  );


  useEffect(() => {
    // Initial page load
    void loadOrders();

    // Poll every 2 seconds so auto-buy
    // orders appear without refreshing.
    const intervalId =
      window.setInterval(() => {
        void loadOrders(true);
      }, 2000);

    return () => {
      window.clearInterval(
        intervalId
      );
    };
  }, [loadOrders]);


  return (
    <main className="min-h-screen bg-black px-6 py-10 text-white">
      <div className="mx-auto max-w-3xl">

        <div className="mb-8">
          <h1 className="text-3xl font-semibold">
            Your orders
          </h1>

          <p className="mt-2 text-neutral-400">
            View your completed Retailigent purchases.
          </p>
        </div>


        {loading && (
          <p className="text-neutral-400">
            Loading orders...
          </p>
        )}


        {!loading && error && (
          <div className="rounded-xl border border-red-900 bg-red-950/30 p-5">
            <p className="text-red-400">
              {error}
            </p>
          </div>
        )}


        {!loading &&
          !error &&
          orders.length === 0 && (
            <div className="rounded-2xl border border-neutral-800 bg-neutral-900 p-6">

              <h2 className="text-xl font-semibold">
                No orders yet
              </h2>

              <p className="mt-3 text-neutral-400">
                Your completed purchases will appear here.
              </p>

            </div>
          )}


        {!loading &&
          !error &&
          orders.length > 0 && (
            <div className="space-y-6">

              {orders.map(
                (order) => (
                  <OrderConfirmationBlock
                    key={order.id}
                    order={order}
                  />
                )
              )}

            </div>
          )}

      </div>
    </main>
  );
}