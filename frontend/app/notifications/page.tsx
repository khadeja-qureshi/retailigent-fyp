"use client";

import Link from "next/link";

import {
  useCallback,
  useEffect,
  useState,
} from "react";

import NotificationListBlock from "@/components/chat-blocks/NotificationListBlock";

import {
  AppNotification,
  getNotifications,
  markNotificationsRead,
} from "@/lib/api";


export default function NotificationsPage() {
  const [
    notifications,
    setNotifications,
  ] =
    useState<AppNotification[]>(
      []
    );

  const [
    unreadCount,
    setUnreadCount,
  ] =
    useState(0);

  const [
    loading,
    setLoading,
  ] =
    useState(true);

  const [
    busy,
    setBusy,
  ] =
    useState(false);

  const [
    error,
    setError,
  ] =
    useState<string | null>(
      null
    );


  const load =
    useCallback(
      async (
        silent = false
      ) => {
        try {
          if (!silent) {
            setLoading(
              true
            );
          }

          setError(
            null
          );


          const result =
            await getNotifications();


          setNotifications(
            result.notifications
          );

          setUnreadCount(
            result.unread_count
          );
        } catch (
          caught
        ) {
          setError(
            caught instanceof Error
              ? caught.message
              : "Unable to load notifications."
          );
        } finally {
          if (!silent) {
            setLoading(
              false
            );
          }
        }
      },
      []
    );


  useEffect(() => {
    queueMicrotask(
      () => {
        void load();
      }
    );


    const intervalId =
      window.setInterval(
        () => {
          void load(
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
    load,
  ]);


  async function markRead(
    ids?: string[]
  ) {
    try {
      setBusy(
        true
      );

      setError(
        null
      );


      await markNotificationsRead(
        ids
      );


      await load(
        true
      );


      window.dispatchEvent(
        new Event(
          "notifications-updated"
        )
      );
    } catch (
      caught
    ) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Unable to update notifications."
      );
    } finally {
      setBusy(
        false
      );
    }
  }


  return (
    <main className="min-h-[calc(100dvh-4rem)] overflow-x-hidden bg-[#f1e6de] text-[#2c1c20]">

      <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6 sm:py-8 lg:px-8 lg:py-10">

        <header className="mb-6 sm:mb-8">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">

            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#7f2a3c]">
                Activity center
              </p>

              <h1 className="mt-2 text-3xl font-bold sm:text-4xl">
                Notifications
              </h1>

              <p className="mt-2 max-w-2xl text-sm leading-6 text-[#756369] sm:text-base">
                Keep track of product alerts,
                Smart Cart matches, purchases,
                and other Retailigent activity.
              </p>
            </div>


            <Link
              href="/chat"
              className="inline-flex min-h-11 w-full items-center justify-center rounded-xl bg-[#7f2a3c] px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-[#682132] sm:w-auto"
            >
              Open assistant
            </Link>
          </div>


          <div className="mt-5 flex flex-wrap gap-2">

            <Link
              href="/alerts"
              className="rounded-full border border-[#d8c8c1] bg-[#fffaf7] px-4 py-2 text-sm font-medium text-[#5f4d52] transition hover:border-[#7779de]"
            >
              Product Alerts
            </Link>

            <Link
              href="/smart-cart"
              className="rounded-full border border-[#d8c8c1] bg-[#fffaf7] px-4 py-2 text-sm font-medium text-[#5f4d52] transition hover:border-[#7779de]"
            >
              Smart Cart
            </Link>

            <Link
              href="/orders"
              className="rounded-full border border-[#d8c8c1] bg-[#fffaf7] px-4 py-2 text-sm font-medium text-[#5f4d52] transition hover:border-[#7779de]"
            >
              Orders
            </Link>
          </div>
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


        {
          loading
            ? (
              <div className="rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-5 text-sm text-[#756369] shadow-sm sm:p-6">
                Loading notifications...
              </div>
            )
            : (
              <NotificationListBlock
                notifications={
                  notifications
                }
                unreadCount={
                  unreadCount
                }
                busy={
                  busy
                }
                onMarkRead={(
                  id
                ) => {
                  void markRead(
                    [
                      id,
                    ]
                  );
                }}
                onMarkAllRead={() => {
                  void markRead();
                }}
              />
            )
        }
      </div>
    </main>
  );
}