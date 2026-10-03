"use client";

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
  const [notifications, setNotifications] =
    useState<AppNotification[]>([]);

  const [unreadCount, setUnreadCount] =
    useState(0);

  const [loading, setLoading] =
    useState(true);

  const [busy, setBusy] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);


  const load = useCallback(
    async (silent = false) => {
      try {
        if (!silent) {
          setLoading(true);
        }

        setError(null);

        const result =
          await getNotifications();

        setNotifications(
          result.notifications
        );
        setUnreadCount(
          result.unread_count
        );

      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Unable to load notifications."
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
    void load();

    const id = window.setInterval(() => {
      void load(true);
    }, 5000);

    return () => {
      window.clearInterval(id);
    };
  }, [load]);


  async function markRead(ids?: string[]) {
    try {
      setBusy(true);
      await markNotificationsRead(ids);
      await load(true);
      window.dispatchEvent(
        new Event("notifications-updated")
      );

    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to update notifications."
      );

    } finally {
      setBusy(false);
    }
  }


  return (
    <main className="min-h-screen bg-black px-6 py-10 text-white">
      <div className="mx-auto max-w-3xl">

        <div className="mb-8">
          <h1 className="text-3xl font-semibold">
            Notifications
          </h1>

          <p className="mt-2 text-neutral-400">
            Alerts, Smart Cart matches, and
            purchase confirmations.
          </p>
        </div>

        {loading && (
          <p className="text-neutral-400">
            Loading notifications...
          </p>
        )}

        {!loading && error && (
          <div className="rounded-xl border border-red-900 bg-red-950/30 p-5">
            <p className="text-red-400">
              {error}
            </p>
          </div>
        )}

        {!loading && !error && (
          <NotificationListBlock
            notifications={notifications}
            unreadCount={unreadCount}
            busy={busy}
            onMarkRead={(id) => {
              void markRead([id]);
            }}
            onMarkAllRead={() => {
              void markRead();
            }}
          />
        )}

      </div>
    </main>
  );
}
