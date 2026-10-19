"use client";

import Link from "next/link";

import {
  useEffect,
  useState,
} from "react";

import CartSummaryBlock from "@/components/chat-blocks/CartSummaryBlock";

import {
  CartResponse,
  addCartItem,
  getCart,
  removeCartItem,
  updateCartItem,
} from "@/lib/api";


const SHOP_LINKS = [
  {
    href: "/wishlist",
    label: "Wishlist",
  },
  {
    href: "/reservations",
    label: "Reservations",
  },
  {
    href: "/smart-cart",
    label: "Smart Cart",
  },
  {
    href: "/alerts",
    label: "Alerts",
  },
  {
    href: "/orders",
    label: "Orders",
  },
];


export default function CartPage() {
  const [
    cart,
    setCart,
  ] =
    useState<CartResponse | null>(
      null
    );

  const [
    error,
    setError,
  ] =
    useState<string | null>(
      null
    );

  const [
    busyItemId,
    setBusyItemId,
  ] =
    useState<string | null>(
      null
    );

  const [
    variantId,
    setVariantId,
  ] =
    useState("");

  const [
    quantity,
    setQuantity,
  ] =
    useState(1);


  async function loadCart() {
    try {
      setError(null);

      setCart(
        await getCart()
      );
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Failed to load cart"
      );
    }
  }


  useEffect(() => {
    queueMicrotask(() => {
      void loadCart();
    });
  }, []);


  async function handleAdd() {
    if (!variantId.trim()) {
      return;
    }

    try {
      setError(null);

      const result =
        await addCartItem(
          variantId.trim(),
          quantity
        );

      setCart(
        result
      );

      setVariantId("");
      setQuantity(1);
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to add item"
      );
    }
  }


  async function handleQuantityChange(
    itemId: string,
    newQuantity: number
  ) {
    try {
      setError(null);

      setBusyItemId(
        itemId
      );

      const result =
        await updateCartItem(
          itemId,
          newQuantity
        );

      setCart(
        result
      );
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to update quantity"
      );
    } finally {
      setBusyItemId(null);
    }
  }


  async function handleRemove(
    itemId: string
  ) {
    try {
      setError(null);

      setBusyItemId(
        itemId
      );

      await removeCartItem(
        itemId
      );

      await loadCart();
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to remove item"
      );
    } finally {
      setBusyItemId(null);
    }
  }


  return (
    <main className="min-h-[calc(100dvh-4rem)] overflow-x-hidden bg-[#f1e6de] text-[#2c1c20]">
      <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6 sm:py-8 lg:px-8 lg:py-10">

        <header className="mb-6 sm:mb-8">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#7f2a3c]">
                Shopping workspace
              </p>

              <h1 className="mt-2 text-3xl font-bold sm:text-4xl">
                Your cart
              </h1>

              <p className="mt-2 max-w-2xl text-sm leading-6 text-[#756369] sm:text-base">
                Review quantities and current availability
                before continuing your shopping journey.
              </p>
            </div>

            <Link
              href="/chat"
              className="inline-flex min-h-11 w-full items-center justify-center rounded-xl bg-[#7f2a3c] px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-[#682132] sm:w-auto"
            >
              Ask assistant
            </Link>
          </div>


          <nav className="mt-5 flex max-w-full gap-2 overflow-x-auto pb-1 sm:flex-wrap sm:overflow-visible">
            {
              SHOP_LINKS.map(
                (
                  link
                ) => (
                  <Link
                    key={
                      link.href
                    }
                    href={
                      link.href
                    }
                    className="shrink-0 rounded-full border border-[#d8c8c1] bg-[#fffaf7] px-4 py-2 text-sm font-medium text-[#5f4d52] transition hover:border-[#7779de] hover:text-[#5f62c7]"
                  >
                    {
                      link.label
                    }
                  </Link>
                )
              )
            }
          </nav>
        </header>


        {
          error
          && (
            <div className="mb-6 rounded-2xl border border-[#e4aaa3] bg-[#fff2ef] px-4 py-3 text-sm text-[#9b352e]">
              {
                error
              }
            </div>
          )
        }


        <section className="mb-6 rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-4 shadow-sm sm:mb-8 sm:p-6">
          <div>
            <p className="text-sm font-semibold text-[#332e34]">
              Developer test control
            </p>

            <p className="mt-1 text-xs leading-5 text-[#8c777c]">
              Add a variant directly using its UUID.
              This control can be removed for the final demo.
            </p>
          </div>


          <div className="mt-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_7rem_auto]">
            <input
              value={
                variantId
              }
              onChange={(
                event
              ) => {
                setVariantId(
                  event.target.value
                );
              }}
              placeholder="Variant UUID"
              className="min-h-11 min-w-0 rounded-xl border border-[#d8c8c1] bg-white px-3 py-2.5 text-base outline-none transition placeholder:text-[#ad999e] focus:border-[#7779de] sm:text-sm"
            />

            <input
              type="number"
              min={1}
              value={
                quantity
              }
              onChange={(
                event
              ) => {
                setQuantity(
                  Math.max(
                    1,
                    Number(
                      event.target.value
                    )
                  )
                );
              }}
              aria-label="Quantity"
              className="min-h-11 w-full rounded-xl border border-[#d8c8c1] bg-white px-3 py-2.5 text-base outline-none transition focus:border-[#7779de] sm:text-sm"
            />

            <button
              type="button"
              onClick={
                handleAdd
              }
              disabled={
                !variantId.trim()
              }
              className="min-h-11 rounded-xl bg-[#ce4d42] px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-[#ad3d34] disabled:cursor-not-allowed disabled:opacity-40"
            >
              Add to cart
            </button>
          </div>
        </section>


        {
          !cart
            ? (
              <div className="rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-5 text-sm text-[#756369] shadow-sm">
                Loading cart...
              </div>
            )
            : (
              <CartSummaryBlock
                data={
                  cart
                }
                busyItemId={
                  busyItemId
                }
                onQuantityChange={
                  handleQuantityChange
                }
                onRemove={
                  handleRemove
                }
              />
            )
        }
      </div>
    </main>
  );
}