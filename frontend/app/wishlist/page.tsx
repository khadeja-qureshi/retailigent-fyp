"use client";

import Link from "next/link";

import {
  useEffect,
  useState,
} from "react";

import WishlistBlock from "@/components/chat-blocks/WishlistBlock";

import {
  WishlistResponse,
  addWishlistItem,
  getWishlist,
  removeWishlistItem,
} from "@/lib/api";


export default function WishlistPage() {
  const [
    wishlist,
    setWishlist,
  ] =
    useState<WishlistResponse | null>(
      null
    );

  const [
    variantId,
    setVariantId,
  ] =
    useState("");

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
    queueMicrotask(() => {
      void loadWishlist();
    });
  }, []);


  async function handleAdd() {
    if (
      !variantId.trim()
    ) {
      return;
    }

    try {
      setError(null);

      const result =
        await addWishlistItem(
          variantId.trim()
        );

      setWishlist(
        result
      );

      setVariantId("");
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
      setError(null);

      setBusyItemId(
        itemId
      );

      await removeWishlistItem(
        itemId
      );

      await loadWishlist();
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
                Saved items
              </p>

              <h1 className="mt-2 text-3xl font-bold sm:text-4xl">
                Wishlist
              </h1>

              <p className="mt-2 max-w-2xl text-sm leading-6 text-[#756369] sm:text-base">
                Keep track of products you want
                to revisit later.
              </p>
            </div>

            <Link
              href="/chat"
              className="inline-flex min-h-11 w-full items-center justify-center rounded-xl bg-[#7f2a3c] px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-[#682132] sm:w-auto"
            >
              Find products
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
              href="/reservations"
              className="shrink-0 rounded-full border border-[#d8c8c1] bg-[#fffaf7] px-4 py-2 text-sm font-medium text-[#5f4d52]"
            >
              Reservations
            </Link>

            <Link
              href="/orders"
              className="shrink-0 rounded-full border border-[#d8c8c1] bg-[#fffaf7] px-4 py-2 text-sm font-medium text-[#5f4d52]"
            >
              Orders
            </Link>
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
          <p className="text-sm font-semibold text-[#332e34]">
            Developer test control
          </p>

          <p className="mt-1 text-xs leading-5 text-[#8c777c]">
            Save a variant directly by UUID.
          </p>


          <div className="mt-4 flex flex-col gap-3 sm:flex-row">
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
              className="min-h-11 min-w-0 flex-1 rounded-xl border border-[#d8c8c1] bg-white px-3 py-2.5 text-base outline-none transition focus:border-[#7779de] sm:text-sm"
            />

            <button
              type="button"
              onClick={
                handleAdd
              }
              disabled={
                !variantId.trim()
              }
              className="min-h-11 rounded-xl bg-[#ce4d42] px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-[#ad3d34] disabled:opacity-40"
            >
              Add to wishlist
            </button>
          </div>
        </section>


        {
          !wishlist
            ? (
              <div className="rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-5 text-sm text-[#756369] shadow-sm">
                Loading wishlist...
              </div>
            )
            : (
              <WishlistBlock
                data={
                  wishlist
                }
                busyItemId={
                  busyItemId
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