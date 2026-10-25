"use client";

import Link from "next/link";

import {
  usePathname,
  useRouter,
} from "next/navigation";

import {
  useEffect,
  useRef,
  useState,
} from "react";

import {
  getUnreadNotificationCount,
} from "@/lib/api";

import {
  supabase,
} from "@/lib/supabase/client";


const API_URL =
  process.env.NEXT_PUBLIC_API_URL
  ??
  "http://127.0.0.1:8000";


type UserRole =
  | "customer"
  | "staff"
  | "manager"
  | "admin";


const CUSTOMER_LINKS = [
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
];


const ADMIN_LINKS = [
  {
    href: "/admin",
    label: "Dashboard",
    exact: true,
  },
  {
    href: "/admin/tickets",
    label: "Tickets",
  },
  {
    href: "/admin/feedback",
    label: "Feedback",
  },
  {
    href: "/admin/analytics",
    label: "Analytics",
  },
  {
    href: "/admin/ask",
    label: "Assistant",
  },
  {
    href: "/admin/audit-logs",
    label: "Audit Logs",
  },
];


function isPrivilegedRole(
  role: UserRole | null
) {
  return (
    role === "staff"
    ||
    role === "manager"
    ||
    role === "admin"
  );
}


function isActivePath(
  pathname: string,
  href: string,
  exact = false
) {
  if (exact) {
    return pathname === href;
  }


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


function UserIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      className="h-4 w-4"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
    >
      <circle
        cx="12"
        cy="8"
        r="3.5"
      />

      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M5 20c.7-4 3.1-6 7-6s6.3 2 7 6"
      />
    </svg>
  );
}


function BellIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      className="h-4 w-4"
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


function MenuIcon({
  open,
}: {
  open: boolean;
}) {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      className="h-5 w-5"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
    >
      {
        open
          ? (
            <path
              strokeLinecap="round"
              d="M6 6l12 12M18 6L6 18"
            />
          )
          : (
            <path
              strokeLinecap="round"
              d="M4 7h16M4 12h16M4 17h16"
            />
          )
      }
    </svg>
  );
}


async function getRole(
  accessToken: string
): Promise<UserRole> {
  const response =
    await fetch(
      `${API_URL}/api/v1/me/role`,
      {
        headers: {
          Authorization:
            `Bearer ${accessToken}`,
        },

        cache:
          "no-store",
      }
    );


  if (!response.ok) {
    throw new Error(
      "Unable to load account role."
    );
  }


  const payload =
    await response.json();


  const role =
    payload?.role;


  if (
    role === "staff"
    ||
    role === "manager"
    ||
    role === "admin"
  ) {
    return role;
  }


  return "customer";
}


export default function NavBar() {
  const pathname =
    usePathname();

  const router =
    useRouter();


  const accountRef =
    useRef<HTMLDivElement | null>(
      null
    );


  const [
    signedIn,
    setSignedIn,
  ] =
    useState(false);


  const [
    role,
    setRole,
  ] =
    useState<UserRole | null>(
      null
    );


  const [
    email,
    setEmail,
  ] =
    useState<string | null>(
      null
    );


  const [
    unread,
    setUnread,
  ] =
    useState(0);


  const [
    mobileMenuOpen,
    setMobileMenuOpen,
  ] =
    useState(false);


  const [
    accountOpen,
    setAccountOpen,
  ] =
    useState(false);


  const privileged =
    isPrivilegedRole(
      role
    );


  useEffect(() => {
    let cancelled =
      false;


    async function refreshSession() {
      const {
        data: {
          session,
        },
      } =
        await supabase.auth
          .getSession();


      if (cancelled) {
        return;
      }


      if (!session) {
        setSignedIn(
          false
        );

        setRole(
          null
        );

        setEmail(
          null
        );

        setUnread(
          0
        );

        return;
      }


      setSignedIn(
        true
      );

      setEmail(
        session.user.email
        ??
        null
      );


      try {
        const resolvedRole =
          await getRole(
            session.access_token
          );


        if (cancelled) {
          return;
        }


        setRole(
          resolvedRole
        );


        if (
          resolvedRole
          === "customer"
        ) {
          try {
            const result =
              await getUnreadNotificationCount();


            if (!cancelled) {
              setUnread(
                result.unread_count
              );
            }

          } catch {
            if (!cancelled) {
              setUnread(
                0
              );
            }
          }

        } else {
          setUnread(
            0
          );
        }

      } catch {
        if (!cancelled) {
          setRole(
            "customer"
          );
        }
      }
    }


    void refreshSession();


    const {
      data: {
        subscription,
      },
    } =
      supabase.auth
        .onAuthStateChange(
          () => {
            void refreshSession();
          }
        );


    function handleNotificationsUpdated() {
      void refreshSession();
    }


    window.addEventListener(
      "notifications-updated",
      handleNotificationsUpdated
    );


    return () => {
      cancelled =
        true;

      subscription.unsubscribe();

      window.removeEventListener(
        "notifications-updated",
        handleNotificationsUpdated
      );
    };
  }, []);


  useEffect(() => {
    function handleOutsideClick(
      event: MouseEvent
    ) {
      if (
        accountRef.current
        &&
        !accountRef.current.contains(
          event.target as Node
        )
      ) {
        setAccountOpen(
          false
        );
      }
    }


    document.addEventListener(
      "mousedown",
      handleOutsideClick
    );


    return () => {
      document.removeEventListener(
        "mousedown",
        handleOutsideClick
      );
    };
  }, []);


  useEffect(() => {
    setMobileMenuOpen(
      false
    );

    setAccountOpen(
      false
    );
  }, [
    pathname,
  ]);


  if (!signedIn) {
    return null;
  }


  const navigation =
    privileged
      ? ADMIN_LINKS
      : CUSTOMER_LINKS;


  async function handleLogout() {
    setAccountOpen(
      false
    );

    setMobileMenuOpen(
      false
    );


    await supabase.auth
      .signOut();


    router.replace(
      "/login"
    );

    router.refresh();
  }


  return (
    <header className="sticky top-0 z-50 h-14 w-full border-b border-white/10 bg-[#332e34]/95 text-white shadow-md shadow-black/10 backdrop-blur-xl">

      <div className="mx-auto flex h-full w-full max-w-[1600px] items-center gap-3 px-4 sm:px-5">

        <Link
          href={
            privileged
              ? "/admin"
              : "/"
          }
          className="flex shrink-0 items-center gap-2.5"
        >
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#7779de] text-sm font-bold text-white shadow-md shadow-[#7779de]/20">
            R
          </span>


          <div className="leading-none">
            <p className="text-sm font-semibold tracking-[0.15em] text-white">
              RETAILIGENT
            </p>

            {
              privileged
              && (
                <p className="mt-1 text-[9px] font-semibold uppercase tracking-[0.16em] text-[#aaaaff]">
                  Staff
                </p>
              )
            }
          </div>
        </Link>


        <nav className="hidden min-w-0 flex-1 items-center justify-center gap-0.5 lg:flex">

          {
            navigation.map(
              (
                item
              ) => {
                const exact =
                  "exact" in item
                    ? Boolean(
                      item.exact
                    )
                    : false;


                const active =
                  isActivePath(
                    pathname,
                    item.href,
                    exact
                  );


                return (
                  <Link
                    key={
                      item.href
                    }
                    href={
                      item.href
                    }
                    className={
                      (
                        "shrink-0 rounded-lg "
                        +
                        "px-3 py-2 "
                        +
                        "text-sm transition "
                      )
                      +
                      (
                        active
                          ? (
                            "bg-[#7779de] "
                            +
                            "font-semibold "
                            +
                            "text-white"
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
                      item.label
                    }
                  </Link>
                );
              }
            )
          }

        </nav>


        {
          !privileged
          && (
            <Link
              href="/notifications"
              aria-label={
                unread > 0
                  ? `${unread} unread notifications`
                  : "Notifications"
              }
              className="relative ml-auto hidden items-center gap-2 rounded-lg px-2.5 py-2 text-sm text-white/75 transition hover:bg-white/10 hover:text-white lg:flex"
            >
              <BellIcon />

              <span>
                Notifications
              </span>


              {
                unread > 0
                && (
                  <span className="flex min-h-5 min-w-5 items-center justify-center rounded-full bg-[#f54631] px-1.5 text-[9px] font-bold text-white">
                    {
                      unread > 99
                        ? "99+"
                        : unread
                    }
                  </span>
                )
              }
            </Link>
          )
        }


        <div
          ref={
            accountRef
          }
          className={
            privileged
              ? "relative ml-auto hidden lg:block"
              : "relative hidden lg:block"
          }
        >
          <button
            type="button"
            onClick={() => {
              setAccountOpen(
                (
                  current
                ) =>
                  !current
              );
            }}
            aria-expanded={
              accountOpen
            }
            className="flex h-9 items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-white/85 transition hover:bg-white/10 hover:text-white"
          >
            <UserIcon />

            <span>
              Account
            </span>

            <span
              className={
                (
                  "text-xs transition-transform "
                )
                +
                (
                  accountOpen
                    ? "rotate-180"
                    : ""
                )
              }
            >
              ▾
            </span>
          </button>


          {
            accountOpen
            && (
              <div className="absolute right-0 top-[calc(100%+0.5rem)] w-64 overflow-hidden rounded-xl border border-[#e5e0e3] bg-white text-[#332e34] shadow-xl">

                <div className="border-b border-[#eee9ec] px-4 py-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#7779de]">
                    {
                      privileged
                        ? "Staff account"
                        : "Customer account"
                    }
                  </p>


                  {
                    email
                    && (
                      <p className="mt-1 truncate text-xs text-[#716a73]">
                        {
                          email
                        }
                      </p>
                    )
                  }
                </div>


                <div className="p-2">

                  {
                    privileged
                      ? (
                        <Link
                          href="/admin"
                          className="block rounded-lg px-3 py-2.5 text-sm font-medium transition hover:bg-[#f5f3f5]"
                        >
                          Staff dashboard
                        </Link>
                      )
                      : (
                        <Link
                          href="/profile"
                          className="block rounded-lg px-3 py-2.5 text-sm font-medium transition hover:bg-[#f5f3f5]"
                        >
                          Profile
                        </Link>
                      )
                  }


                  <button
                    type="button"
                    onClick={() => {
                      void handleLogout();
                    }}
                    className="mt-1 w-full rounded-lg px-3 py-2.5 text-left text-sm font-medium text-[#b4382d] transition hover:bg-[#fff0ed]"
                  >
                    Logout
                  </button>

                </div>

              </div>
            )
          }

        </div>


        <button
          type="button"
          onClick={() => {
            setMobileMenuOpen(
              (
                current
              ) =>
                !current
            );
          }}
          aria-expanded={
            mobileMenuOpen
          }
          aria-label={
            mobileMenuOpen
              ? "Close navigation"
              : "Open navigation"
          }
          className="ml-auto flex h-9 w-9 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-white lg:hidden"
        >
          <MenuIcon
            open={
              mobileMenuOpen
            }
          />
        </button>

      </div>


      {
        mobileMenuOpen
        && (
          <div className="absolute left-0 right-0 top-14 border-t border-white/10 bg-[#332e34] shadow-xl lg:hidden">

            <div className="max-h-[calc(100dvh-3.5rem)] overflow-y-auto px-4 py-4">

              <nav className="grid gap-1">

                {
                  navigation.map(
                    (
                      item
                    ) => {
                      const exact =
                        "exact" in item
                          ? Boolean(
                            item.exact
                          )
                          : false;


                      const active =
                        isActivePath(
                          pathname,
                          item.href,
                          exact
                        );


                      return (
                        <Link
                          key={
                            item.href
                          }
                          href={
                            item.href
                          }
                          className={
                            (
                              "rounded-xl "
                              +
                              "px-3 py-2.5 "
                              +
                              "text-sm transition "
                            )
                            +
                            (
                              active
                                ? (
                                  "bg-[#7779de] "
                                  +
                                  "font-semibold "
                                  +
                                  "text-white"
                                )
                                : (
                                  "text-white/75 "
                                  +
                                  "hover:bg-white/10 "
                                  +
                                  "hover:text-white"
                                )
                            )
                          }
                        >
                          {
                            item.label
                          }
                        </Link>
                      );
                    }
                  )
                }


                {
                  !privileged
                  && (
                    <Link
                      href="/notifications"
                      className="flex items-center justify-between rounded-xl px-3 py-2.5 text-sm text-white/75 transition hover:bg-white/10 hover:text-white"
                    >
                      <span>
                        Notifications
                      </span>


                      {
                        unread > 0
                        && (
                          <span className="rounded-full bg-[#f54631] px-2 py-0.5 text-[10px] font-bold text-white">
                            {
                              unread > 99
                                ? "99+"
                                : unread
                            }
                          </span>
                        )
                      }
                    </Link>
                  )
                }

              </nav>


              <div className="mt-4 border-t border-white/10 pt-4">

                {
                  email
                  && (
                    <p className="mb-2 truncate px-3 text-xs text-white/45">
                      {
                        email
                      }
                    </p>
                  )
                }


                {
                  !privileged
                  && (
                    <Link
                      href="/profile"
                      className="block rounded-xl px-3 py-2.5 text-sm text-white/75 transition hover:bg-white/10 hover:text-white"
                    >
                      Profile
                    </Link>
                  )
                }


                <button
                  type="button"
                  onClick={() => {
                    void handleLogout();
                  }}
                  className="mt-1 w-full rounded-xl px-3 py-2.5 text-left text-sm font-medium text-[#ff9d91] transition hover:bg-white/10"
                >
                  Logout
                </button>

              </div>

            </div>

          </div>
        )
      }

    </header>
  );
}