"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import CartSummaryBlock from "@/components/chat-blocks/CartSummaryBlock";

import {
  CartResponse,
  addCartItem,
  getCart,
  removeCartItem,
  updateCartItem,
} from "@/lib/api";


export default function CartPage() {
  const [cart, setCart] =
    useState<CartResponse | null>(null);

  const [error, setError] =
    useState<string | null>(null);

  const [busyItemId, setBusyItemId] =
    useState<string | null>(null);

  const [variantId, setVariantId] =
    useState("");

  const [quantity, setQuantity] =
    useState(1);


  async function loadCart() {
    try {
      setError(null);
      setCart(await getCart());
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Failed to load cart"
      );
    }
  }


  useEffect(() => {
    loadCart();
  }, []);


  async function handleAdd() {
    if (!variantId.trim()) {
      return;
    }

    try {
      setError(null);

      const result = await addCartItem(
        variantId.trim(),
        quantity
      );

      setCart(result);
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
      setBusyItemId(itemId);

      const result =
        await updateCartItem(
          itemId,
          newQuantity
        );

      setCart(result);
    } finally {
      setBusyItemId(null);
    }
  }


  async function handleRemove(
    itemId: string
  ) {
    try {
      setBusyItemId(itemId);

      await removeCartItem(itemId);
      await loadCart();
    } finally {
      setBusyItemId(null);
    }
  }


  return (
    <main className="min-h-screen bg-neutral-950 text-white">
      <div className="mx-auto max-w-3xl p-6 md:p-10">

        <div className="mb-8 flex items-center justify-between">
          <div>
            <p className="text-sm text-neutral-500">
              Retailigent
            </p>

            <h1 className="text-3xl font-semibold">
              Cart
            </h1>
          </div>

          <nav className="flex gap-4 text-sm text-neutral-300">
            <Link
              href="/wishlist"
              className="underline"
            >
              Wishlist
            </Link>

            <Link
              href="/reservations"
              className="underline"
            >
              Reservations
            </Link>

            <Link
              href="/orders"
              className="underline"
            >
              Orders
            </Link>
          </nav>
        </div>

        {error && (
          <div className="mb-6 rounded-xl border border-red-900 bg-red-950/40 p-4 text-red-300">
            {error}
          </div>
        )}

        <div className="mb-8 rounded-2xl border border-neutral-800 bg-neutral-900 p-5">
          <p className="text-sm font-medium">
            Temporary Phase 6 test control
          </p>

          <input
            value={variantId}
            onChange={(event) =>
              setVariantId(
                event.target.value
              )
            }
            placeholder="Variant UUID"
            className="mt-4 w-full rounded-lg border border-neutral-700 bg-neutral-950 p-3"
          />

          <div className="mt-3 flex gap-3">
            <input
              type="number"
              min={1}
              value={quantity}
              onChange={(event) =>
                setQuantity(
                  Math.max(
                    1,
                    Number(
                      event.target.value
                    )
                  )
                )
              }
              className="w-28 rounded-lg border border-neutral-700 bg-neutral-950 p-3"
            />

            <button
              onClick={handleAdd}
              className="rounded-lg bg-white px-5 text-black"
            >
              Add to cart
            </button>
          </div>
        </div>

        {!cart ? (
          <p className="text-neutral-400">
            Loading cart...
          </p>
        ) : (
          <CartSummaryBlock
            data={cart}
            busyItemId={busyItemId}
            onQuantityChange={
              handleQuantityChange
            }
            onRemove={handleRemove}
          />
        )}

      </div>
    </main>
  );
}