"use client";

import Link from "next/link";

import {
  usePathname,
} from "next/navigation";

import {
  useEffect,
  useState,
} from "react";

import {
  getUnreadNotificationCount,
} from "@/lib/api";

import {
  supabase,
} from "@/lib/supabase/client";


const DESKTOP_LINKS = [
  {
    href: "/",
    label: "Home",
  },
  {
    href: "/chat",
    label: "Assistant",
  },
  {
    href: "/cart",
    label: "Cart",
  },
  {
    href: "/wishlist",
    label: "Wishlist",
  },
  {
    href: "/reservations",
    label: "Reservations",
  },
  {
    href: "/orders",
    label: "Orders",
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
    href: "/profile",
    label: "Profile",
  },
];


const MOBILE_MORE_LINKS = [
  {
    href: "/wishlist",
    label: "Wishlist",
    description:
      "Your saved products",
  },
  {
    href: "/reservations",
    label: "Reservations",
    description:
      "Branch inventory holds",
  },
  {
    href: "/smart-cart",
    label: "Smart Cart",
    description:
      "Automated shopping rules",
  },
  {
    href: "/alerts",
    label: "Product Alerts",
    description:
      "Price and stock monitoring",
  },
];


function isActivePath(
  pathname: string,
  href: string
) {
  if (href === "/") {
    return pathname === "/";
  }

  return (
    pathname === href
    ||
    pathname.startsWith(
      `${href}/`
    )
  );
}


function MenuIcon({
  open,
}: {
  open: boolean;
}) {
  if (open) {
    return (
      <svg
        viewBox="0 0 24 24"
        aria-hidden="true"
        className="h-5 w-5"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      >
        <path
          strokeLinecap="round"
          d="M6 6l12 12M18 6L6 18"
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
      strokeWidth="2"
    >
      <path
        strokeLinecap="round"
        d="M4 7h16M4 12h16M4 17h16"
      />
    </svg>
  );
}


function BellIcon() {
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


export default function NavBar() {
  const pathname =
    usePathname();

  const [
    unread,
    setUnread,
  ] =
    useState(0);

  const [
    signedIn,
    setSignedIn,
  ] =
    useState(false);

  const [
    menuOpen,
    setMenuOpen,
  ] =
    useState(false);


  useEffect(() => {
    let cancelled =
      false;


    async function refresh() {
      const {
        data: {
          session,
        },
      } =
        await supabase
          .auth
          .getSession();


      if (cancelled) {
        return;
      }


      setSignedIn(
        Boolean(session)
      );


      if (!session) {
        setUnread(0);

        return;
      }


      try {
        const result =
          await getUnreadNotificationCount();


        if (!cancelled) {
          setUnread(
            result.unread_count
          );
        }
      } catch {
        // Notification badge is best-effort.
      }
    }


    void refresh();


    const intervalId =
      window.setInterval(
        () => {
          void refresh();
        },
        10000
      );


    function handleNotificationsUpdated() {
      void refresh();
    }


    window.addEventListener(
      "notifications-updated",
      handleNotificationsUpdated
    );


    const {
      data: {
        subscription,
      },
    } =
      supabase.auth
        .onAuthStateChange(
          (
            _event,
            session
          ) => {
            if (cancelled) {
              return;
            }

            setSignedIn(
              Boolean(session)
            );

            if (!session) {
              setUnread(0);
            } else {
              void refresh();
            }
          }
        );


    return () => {
      cancelled = true;

      window.clearInterval(
        intervalId
      );

      window.removeEventListener(
        "notifications-updated",
        handleNotificationsUpdated
      );

      subscription.unsubscribe();
    };
  }, []);


  if (!signedIn) {
    return null;
  }


  const moreSectionActive =
    MOBILE_MORE_LINKS.some(
      (
        link
      ) =>
        isActivePath(
          pathname,
          link.href
        )
    );


  function closeMenu() {
    setMenuOpen(
      false
    );
  }


  return (
    <header className="sticky top-0 z-50 w-full border-b border-white/10 bg-[#332e34]/95 text-white shadow-lg shadow-black/10 backdrop-blur-xl">

      <div className="mx-auto flex min-h-16 w-full max-w-[1600px] items-center gap-3 px-4 sm:px-6">

        <Link
          href="/"
          onClick={
            closeMenu
          }
          className="group flex min-w-0 shrink-0 items-center gap-3"
        >
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-[#7779de] text-base font-bold text-white shadow-lg shadow-[#7779de]/25 transition group-hover:-translate-y-0.5">
            R
          </span>


          <div className="min-w-0">
            <p className="truncate text-sm font-semibold tracking-[0.18em] text-white">
              RETAILIGENT
            </p>

            <p className="hidden text-[10px] tracking-wide text-white/45 sm:block xl:hidden">
              Intelligent shopping
            </p>
          </div>
        </Link>


        <nav className="hidden min-w-0 flex-1 items-center justify-center gap-0.5 xl:flex">
          {
            DESKTOP_LINKS.map(
              (
                link
              ) => {
                const active =
                  isActivePath(
                    pathname,
                    link.href
                  );


                return (
                  <Link
                    key={
                      link.href
                    }
                    href={
                      link.href
                    }
                    className={
                      (
                        "shrink-0 rounded-xl "
                        +
                        "px-2.5 py-2 "
                        +
                        "text-sm transition "
                      )
                      +
                      (
                        active
                          ? (
                            "bg-[#7779de] "
                            +
                            "font-medium "
                            +
                            "text-white "
                            +
                            "shadow-md "
                            +
                            "shadow-[#7779de]/20"
                          )
                          : (
                            "text-white/70 "
                            +
                            "hover:bg-white/10 "
                            +
                            "hover:text-white"
                          )
                      )
                    }
                  >
                    {
                      link.label
                    }
                  </Link>
                );
              }
            )
          }
        </nav>


        <Link
          href="/notifications"
          className="ml-auto hidden shrink-0 items-center gap-2 rounded-xl px-3 py-2 text-sm text-white/80 transition hover:bg-white/10 hover:text-white xl:flex"
        >
          <BellIcon />

          <span>
            Notifications
          </span>

          {
            unread > 0
            && (
              <span className="flex min-h-5 min-w-5 items-center justify-center rounded-full bg-[#f54631] px-1.5 text-[10px] font-bold text-white">
                {
                  unread > 99
                    ? "99+"
                    : unread
                }
              </span>
            )
          }
        </Link>


        <div className="ml-auto flex items-center gap-2 xl:hidden">

          <Link
            href="/notifications"
            onClick={
              closeMenu
            }
            aria-label={
              unread > 0
                ? `${unread} unread notifications`
                : "Notifications"
            }
            className={
              (
                "relative flex h-10 w-10 "
                +
                "items-center justify-center "
                +
                "rounded-xl border "
                +
                "transition "
              )
              +
              (
                isActivePath(
                  pathname,
                  "/notifications"
                )
                  ? (
                    "border-[#7779de]/50 "
                    +
                    "bg-[#7779de]/20 "
                    +
                    "text-white"
                  )
                  : (
                    "border-white/10 "
                    +
                    "bg-white/5 "
                    +
                    "text-white/85 "
                    +
                    "hover:bg-white/10"
                  )
              )
            }
          >
            <BellIcon />


            {
              unread > 0
              && (
                <span className="absolute -right-1 -top-1 flex min-h-[18px] min-w-[18px] items-center justify-center rounded-full border-2 border-[#332e34] bg-[#f54631] px-1 text-[9px] font-bold leading-none text-white">
                  {
                    unread > 9
                      ? "9+"
                      : unread
                  }
                </span>
              )
            }
          </Link>


          <button
            type="button"
            aria-label={
              menuOpen
                ? "Close more navigation"
                : "Open more navigation"
            }
            aria-expanded={
              menuOpen
            }
            aria-controls="retailigent-mobile-menu"
            onClick={() => {
              setMenuOpen(
                (
                  current
                ) =>
                  !current
              );
            }}
            className={
              (
                "flex h-10 w-10 "
                +
                "items-center justify-center "
                +
                "rounded-xl border "
                +
                "transition "
              )
              +
              (
                menuOpen
                ||
                moreSectionActive
                  ? (
                    "border-[#7779de]/50 "
                    +
                    "bg-[#7779de]/20 "
                    +
                    "text-white"
                  )
                  : (
                    "border-white/10 "
                    +
                    "bg-white/5 "
                    +
                    "text-white/85 "
                    +
                    "hover:bg-white/10"
                  )
              )
            }
          >
            <MenuIcon
              open={
                menuOpen
              }
            />
          </button>
        </div>
      </div>


      {
        menuOpen
        && (
          <div
            id="retailigent-mobile-menu"
            className="border-t border-white/10 bg-[#332e34] shadow-2xl xl:hidden"
          >
            <div className="mx-auto w-full max-w-xl px-4 pb-5 pt-4 sm:px-6">

              <div className="mb-4 flex items-center justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-white/45">
                    More
                  </p>

                  <p className="mt-1 text-sm text-white/70">
                    Shopping tools and automation
                  </p>
                </div>


                <span className="rounded-full bg-white/5 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-white/55">
                  Retailigent
                </span>
              </div>


              <nav className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {
                  MOBILE_MORE_LINKS.map(
                    (
                      link
                    ) => {
                      const active =
                        isActivePath(
                          pathname,
                          link.href
                        );


                      return (
                        <Link
                          key={
                            link.href
                          }
                          href={
                            link.href
                          }
                          onClick={
                            closeMenu
                          }
                          className={
                            (
                              "group rounded-2xl border "
                              +
                              "px-4 py-3.5 "
                              +
                              "transition "
                            )
                            +
                            (
                              active
                                ? (
                                  "border-[#7779de]/60 "
                                  +
                                  "bg-[#7779de]/20"
                                )
                                : (
                                  "border-white/10 "
                                  +
                                  "bg-white/5 "
                                  +
                                  "hover:border-white/20 "
                                  +
                                  "hover:bg-white/10"
                                )
                            )
                          }
                        >
                          <div className="flex items-center justify-between gap-3">
                            <div className="min-w-0">
                              <p
                                className={
                                  (
                                    "text-sm font-semibold "
                                  )
                                  +
                                  (
                                    active
                                      ? "text-white"
                                      : "text-white/90"
                                  )
                                }
                              >
                                {
                                  link.label
                                }
                              </p>

                              <p className="mt-1 text-xs leading-5 text-white/45">
                                {
                                  link.description
                                }
                              </p>
                            </div>


                            <svg
                              viewBox="0 0 24 24"
                              aria-hidden="true"
                              className="h-4 w-4 shrink-0 text-white/35 transition group-hover:translate-x-0.5 group-hover:text-white/70"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="2"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                d="M9 5l7 7-7 7"
                              />
                            </svg>
                          </div>
                        </Link>
                      );
                    }
                  )
                }
              </nav>


              <Link
                href="/notifications"
                onClick={
                  closeMenu
                }
                className="mt-3 flex min-h-12 items-center justify-between rounded-2xl border border-white/10 bg-white/5 px-4 py-3 transition hover:bg-white/10"
              >
                <div className="flex items-center gap-3">
                  <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/10 text-white">
                    <BellIcon />
                  </span>

                  <div>
                    <p className="text-sm font-semibold text-white/90">
                      Notifications
                    </p>

                    <p className="text-xs text-white/45">
                      View Retailigent activity
                    </p>
                  </div>
                </div>


                {
                  unread > 0
                  && (
                    <span className="rounded-full bg-[#f54631] px-2.5 py-1 text-xs font-bold text-white">
                      {
                        unread > 99
                          ? "99+"
                          : unread
                      }
                    </span>
                  )
                }
              </Link>
            </div>
          </div>
        )
      }
    </header>
  );
}