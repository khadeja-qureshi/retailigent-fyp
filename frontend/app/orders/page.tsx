"use client";

import Link from "next/link";

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
  const [
    orders,
    setOrders,
  ] =
    useState<Order[]>(
      []
    );

  const [
    loading,
    setLoading,
  ] =
    useState(true);

  const [
    error,
    setError,
  ] =
    useState<string | null>(
      null
    );


  const loadOrders =
    useCallback(
      async (
        silent = false
      ) => {
        try {
          if (
            !silent
          ) {
            setLoading(
              true
            );
          }

          setError(null);

          const result =
            await getOrders();

          setOrders(
            result
          );
        } catch (error) {
          setError(
            error instanceof Error
              ? error.message
              : "Unable to load orders."
          );
        } finally {
          if (
            !silent
          ) {
            setLoading(
              false
            );
          }
        }
      },
      []
    );


  useEffect(() => {
    queueMicrotask(() => {
      void loadOrders();
    });


    const intervalId =
      window.setInterval(
        () => {
          void loadOrders(
            true
          );
        },
        5000
      );


    return () => {
      window.clearInterval(
        intervalId
      );
    };
  }, [
    loadOrders,
  ]);


  return (
    <main className="min-h-[calc(100dvh-4rem)] overflow-x-hidden bg-[#f1e6de] text-[#2c1c20]">
      <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6 sm:py-8 lg:px-8 lg:py-10">

        <header className="mb-6 sm:mb-8">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#7f2a3c]">
                Purchase history
              </p>

              <h1 className="mt-2 text-3xl font-bold sm:text-4xl">
                Your orders
              </h1>

              <p className="mt-2 max-w-2xl text-sm leading-6 text-[#756369] sm:text-base">
                View completed Retailigent mock purchases
                and their order totals.
              </p>
            </div>

            <Link
              href="/chat"
              className="inline-flex min-h-11 w-full items-center justify-center rounded-xl bg-[#7f2a3c] px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-[#682132] sm:w-auto"
            >
              Continue shopping
            </Link>
          </div>


          <nav className="mt-5 flex gap-2 overflow-x-auto pb-1 sm:flex-wrap sm:overflow-visible">
            <Link
              href="/cart"
              className="shrink-0 rounded-full border border-[#d8c8c1] bg-[#fffaf7] px-4 py-2 text-sm font-medium text-[#5f4d52]"
            >
              Cart
            </Link>

            <Link
              href="/wishlist"
              className="shrink-0 rounded-full border border-[#d8c8c1] bg-[#fffaf7] px-4 py-2 text-sm font-medium text-[#5f4d52]"
            >
              Wishlist
            </Link>

            <Link
              href="/reservations"
              className="shrink-0 rounded-full border border-[#d8c8c1] bg-[#fffaf7] px-4 py-2 text-sm font-medium text-[#5f4d52]"
            >
              Reservations
            </Link>
          </nav>
        </header>


        {
          loading
          && (
            <div className="rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-5 text-sm text-[#756369] shadow-sm">
              Loading orders...
            </div>
          )
        }


        {
          !loading
          &&
          error
          && (
            <div className="rounded-2xl border border-[#e4aaa3] bg-[#fff2ef] p-5 text-sm text-[#9b352e]">
              {
                error
              }
            </div>
          )
        }


        {
          !loading
          &&
          !error
          &&
          orders.length
          === 0
          && (
            <div className="rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-5 shadow-sm sm:p-6">
              <h2 className="text-xl font-semibold text-[#332e34]">
                No orders yet
              </h2>

              <p className="mt-3 text-sm leading-6 text-[#756369]">
                Your completed purchases will appear here.
              </p>
            </div>
          )
        }


        {
          !loading
          &&
          !error
          &&
          orders.length
          > 0
          && (
            <div className="space-y-4 sm:space-y-6">
              {
                orders.map(
                  (
                    order
                  ) => (
                    <OrderConfirmationBlock
                      key={
                        order.id
                      }
                      order={
                        order
                      }
                    />
                  )
                )
              }
            </div>
          )
        }
      </div>
    </main>
  );
}