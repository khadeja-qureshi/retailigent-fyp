"use client";

import {
  AppNotification,
} from "@/lib/api";


interface Props {
  notifications:
    AppNotification[];

  unreadCount?:
    number;

  busy?:
    boolean;

  onMarkRead?: (
    id: string
  ) => void;

  onMarkAllRead?:
    () => void;
}


function typeLabel(
  type: string
) {
  const labels:
    Record<
      string,
      string
    > = {
      price_drop:
        "Price drop",

      restock:
        "Restock",

      sale:
        "Sale",

      smart_cart_match:
        "Smart Cart",

      purchase:
        "Purchase",

      support:
        "Support",

      general:
        "General",
    };


  return (
    labels[type]
    ??
    "Update"
  );
}


function formatDate(
  value: string
) {
  const date =
    new Date(
      value
    );


  if (
    Number.isNaN(
      date.getTime()
    )
  ) {
    return value;
  }


  return date.toLocaleString(
    undefined,
    {
      month:
        "short",

      day:
        "numeric",

      hour:
        "numeric",

      minute:
        "2-digit",
    }
  );
}


function NotificationIcon({
  type,
}: {
  type: string;
}) {
  if (
    type
    === "purchase"
  ) {
    return (
      <svg
        viewBox="0 0 24 24"
        aria-hidden="true"
        className="h-5 w-5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M5 12l4 4L19 6"
        />
      </svg>
    );
  }


  if (
    type
    === "price_drop"
    ||
    type
    === "sale"
  ) {
    return (
      <svg
        viewBox="0 0 24 24"
        aria-hidden="true"
        className="h-5 w-5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M5 7h14M7 11h10M9 15h6M11 19h2"
        />
      </svg>
    );
  }


  if (
    type
    === "restock"
  ) {
    return (
      <svg
        viewBox="0 0 24 24"
        aria-hidden="true"
        className="h-5 w-5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M4 8l8-4 8 4-8 4-8-4z"
        />

        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M4 12l8 4 8-4M4 16l8 4 8-4"
        />
      </svg>
    );
  }


  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      className="h-5 w-5"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M18 15v-4a6 6 0 10-12 0v4l-2 2h16l-2-2z"
      />

      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M10 20h4"
      />
    </svg>
  );
}


export default function NotificationListBlock({
  notifications,
  unreadCount,
  busy = false,
  onMarkRead,
  onMarkAllRead,
}: Props) {
  const unread =
    unreadCount
    ??
    notifications.filter(
      (
        item
      ) =>
        !item.read_at
    ).length;


  return (
    <section className="min-w-0 rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-4 shadow-sm sm:p-6">

      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">

        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-xl font-semibold text-[#332e34]">
              Recent activity
            </h2>


            {
              unread > 0
              && (
                <span className="rounded-full bg-[#f54631] px-2.5 py-1 text-xs font-bold text-white">
                  {
                    unread
                  }{" "}
                  new
                </span>
              )
            }
          </div>


          <p className="mt-1 text-sm text-[#8c777c]">
            {
              notifications.length
            }{" "}
            notification
            {
              notifications.length
              === 1
                ? ""
                : "s"
            }
          </p>
        </div>


        {
          onMarkAllRead
          &&
          unread > 0
          && (
            <button
              type="button"
              disabled={
                busy
              }
              onClick={
                onMarkAllRead
              }
              className="min-h-11 w-full rounded-xl border border-[#7779de] px-4 py-2.5 text-sm font-semibold text-[#5f62c7] transition hover:bg-[#f0effc] disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
            >
              {
                busy
                  ? "Updating..."
                  : "Mark all read"
              }
            </button>
          )
        }
      </div>


      {
        notifications.length
        === 0
        && (
          <div className="mt-6 rounded-2xl border border-dashed border-[#d8c8c1] bg-white px-4 py-8 text-center sm:px-6 sm:py-10">

            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-[#eeeafb] text-[#5f62c7]">
              <NotificationIcon
                type="general"
              />
            </div>

            <h3 className="mt-4 font-semibold text-[#332e34]">
              You&apos;re all caught up
            </h3>

            <p className="mt-2 text-sm leading-6 text-[#756369]">
              New Retailigent activity will appear here.
            </p>
          </div>
        )
      }


      {
        notifications.length
        > 0
        && (
          <ul className="mt-5 space-y-3 sm:mt-6">

            {
              notifications.map(
                (
                  item
                ) => {
                  const isUnread =
                    !item.read_at;


                  return (
                    <li
                      key={
                        item.id
                      }
                      className={
                        (
                          "min-w-0 rounded-2xl "
                          +
                          "border p-4 "
                          +
                          "transition "
                          +
                          "sm:p-5 "
                        )
                        +
                        (
                          isUnread
                            ? (
                              "border-[#c9c9f1] "
                              +
                              "bg-[#f5f4ff]"
                            )
                            : (
                              "border-[#e2d5cf] "
                              +
                              "bg-white"
                            )
                        )
                      }
                    >
                      <div className="flex min-w-0 items-start gap-3 sm:gap-4">

                        <div
                          className={
                            (
                              "flex h-10 w-10 "
                              +
                              "shrink-0 "
                              +
                              "items-center "
                              +
                              "justify-center "
                              +
                              "rounded-xl "
                            )
                            +
                            (
                              isUnread
                                ? (
                                  "bg-[#7779de] "
                                  +
                                  "text-white"
                                )
                                : (
                                  "bg-[#f1e6de] "
                                  +
                                  "text-[#7f2a3c]"
                                )
                            )
                          }
                        >
                          <NotificationIcon
                            type={
                              item.type
                            }
                          />
                        </div>


                        <div className="min-w-0 flex-1">

                          <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between sm:gap-3">

                            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[#7f2a3c]">
                              {
                                typeLabel(
                                  item.type
                                )
                              }
                            </p>

                            <p className="text-xs text-[#9a858a]">
                              {
                                formatDate(
                                  item.created_at
                                )
                              }
                            </p>
                          </div>


                          <h3 className="mt-2 break-words font-semibold text-[#332e34]">
                            {
                              item.title
                            }
                          </h3>


                          <p className="mt-1 break-words text-sm leading-6 text-[#756369]">
                            {
                              item.message
                            }
                          </p>


                          {
                            isUnread
                            &&
                            onMarkRead
                            && (
                              <button
                                type="button"
                                disabled={
                                  busy
                                }
                                onClick={() => {
                                  onMarkRead(
                                    item.id
                                  );
                                }}
                                className="mt-4 min-h-10 rounded-xl border border-[#d8c8c1] px-3.5 py-2 text-xs font-semibold text-[#5f4d52] transition hover:border-[#7779de] hover:text-[#5f62c7] disabled:cursor-not-allowed disabled:opacity-50"
                              >
                                Mark as read
                              </button>
                            )
                          }
                        </div>
                      </div>
                    </li>
                  );
                }
              )
            }
          </ul>
        )
      }
    </section>
  );
}