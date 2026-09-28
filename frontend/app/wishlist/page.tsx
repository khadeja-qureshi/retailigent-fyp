"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import WishlistBlock from "@/components/chat-blocks/WishlistBlock";

import {
  WishlistResponse,
  addWishlistItem,
  getWishlist,
  removeWishlistItem,
} from "@/lib/api";


export default function WishlistPage() {
  const [wishlist, setWishlist] =
    useState<WishlistResponse | null>(
      null
    );

  const [variantId, setVariantId] =
    useState("");

  const [error, setError] =
    useState<string | null>(null);

  const [busyItemId, setBusyItemId] =
    useState<string | null>(null);


  async function loadWishlist() {
    try {
      setError(null);
      setWishlist(
        await getWishlist()
      );
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Failed to load wishlist"
      );
    }
  }


  useEffect(() => {
    loadWishlist();
  }, []);


  async function handleAdd() {
    if (!variantId.trim()) {
      return;
    }

    try {
      const result =
        await addWishlistItem(
          variantId.trim()
        );

      setWishlist(result);
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to add item"
      );
    }
  }


  async function handleRemove(
    itemId: string
  ) {
    try {
      setBusyItemId(itemId);

      await removeWishlistItem(
        itemId
      );

      await loadWishlist();
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
              Wishlist
            </h1>
          </div>

          <Link
            href="/cart"
            className="text-sm text-neutral-300 underline"
          >
            Cart
          </Link>
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

          <div className="mt-4 flex gap-3">
            <input
              value={variantId}
              onChange={(event) =>
                setVariantId(
                  event.target.value
                )
              }
              placeholder="Variant UUID"
              className="min-w-0 flex-1 rounded-lg border border-neutral-700 bg-neutral-950 p-3"
            />

            <button
              onClick={handleAdd}
              className="rounded-lg bg-white px-5 text-black"
            >
              Add
            </button>
          </div>
        </div>

        {!wishlist ? (
          <p className="text-neutral-400">
            Loading wishlist...
          </p>
        ) : (
          <WishlistBlock
            data={wishlist}
            busyItemId={busyItemId}
            onRemove={handleRemove}
          />
        )}
      </div>
    </main>
  );
}