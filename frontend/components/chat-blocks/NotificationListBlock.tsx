"use client";

import {
  AppNotification,
} from "@/lib/api";


interface Props {
  notifications: AppNotification[];
  unreadCount?: number;
  busy?: boolean;

  onMarkRead?: (
    id: string
  ) => void;

  onMarkAllRead?: () => void;
}


function typeLabel(type: string) {
  const labels: Record<string, string> = {
    price_drop: "Price drop",
    restock: "Restock",
    sale: "Sale",
    smart_cart_match: "Smart Cart",
    purchase: "Purchase",
    support: "Support",
    general: "General",
  };

  return labels[type] ?? "Update";
}


export default function NotificationListBlock({
  notifications,
  unreadCount,
  busy = false,
  onMarkRead,
  onMarkAllRead,
}: Props) {
  const unread =
    unreadCount ??
    notifications.filter(
      (item) => !item.read_at
    ).length;


  return (
    <section className="rounded-2xl border border-neutral-800 bg-neutral-900 p-6">

      <div className="flex items-center justify-between gap-4">

        <h2 className="text-xl font-semibold">
          Notifications
          {unread > 0 && (
            <span className="ml-3 rounded-full bg-red-600 px-2 py-0.5 text-xs">
              {unread} new
            </span>
          )}
        </h2>

        {onMarkAllRead && unread > 0 && (
          <button
            type="button"
            disabled={busy}
            onClick={onMarkAllRead}
            className="rounded-lg border border-neutral-700 px-3 py-1.5 text-sm hover:bg-neutral-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Mark all read
          </button>
        )}

      </div>


      {notifications.length === 0 && (
        <p className="mt-4 text-neutral-400">
          You have no notifications.
        </p>
      )}


      <ul className="mt-4 space-y-3">

        {notifications.map((item) => {
          const isUnread = !item.read_at;

          return (
            <li
              key={item.id}
              className={
                "rounded-xl border p-4 " +
                (isUnread
                  ? "border-blue-900 bg-blue-950/20"
                  : "border-neutral-800 bg-neutral-950")
              }
            >

              <div className="flex items-start justify-between gap-4">

                <div>
                  <p className="text-xs uppercase tracking-wide text-neutral-500">
                    {typeLabel(item.type)}
                    {" · "}
                    {new Date(
                      item.created_at
                    ).toLocaleString()}
                  </p>

                  <h3 className="mt-1 font-semibold">
                    {item.title}
                  </h3>

                  <p className="mt-1 text-sm text-neutral-300">
                    {item.message}
                  </p>
                </div>

                {isUnread && onMarkRead && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => {
                      onMarkRead(item.id);
                    }}
                    className="shrink-0 rounded-lg border border-neutral-700 px-3 py-1.5 text-xs hover:bg-neutral-800 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Mark read
                  </button>
                )}

              </div>

            </li>
          );
        })}

      </ul>

    </section>
  );
}
