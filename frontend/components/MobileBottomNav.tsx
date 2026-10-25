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
  supabase,
} from "@/lib/supabase/client";


const API_URL =
  (
    process.env
      .NEXT_PUBLIC_API_URL
    ??
    "http://127.0.0.1:8000"
  ).replace(
    /\/+$/,
    ""
  );


type UserRole =
  | "customer"
  | "staff"
  | "manager"
  | "admin";


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
  href: string
) {
  if (
    href === "/"
  ) {
    return (
      pathname === "/"
    );
  }


  return (
    pathname === href
    ||
    pathname.startsWith(
      `${href}/`
    )
  );
}


async function getRole(
  accessToken: string
): Promise<UserRole> {

  try {
    const controller =
      new AbortController();


    const timeout =
      window.setTimeout(
        () => {
          controller.abort();
        },
        10000
      );


    try {
      const response =
        await fetch(
          `${API_URL}/api/v1/me/role`,
          {
            method:
              "GET",

            headers: {
              Authorization:
                `Bearer ${accessToken}`,
            },

            cache:
              "no-store",

            signal:
              controller.signal,
          }
        );


      if (
        !response.ok
      ) {
        console.warn(
          "Role endpoint returned:",
          response.status,
        );


        return (
          "customer"
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


      return (
        "customer"
      );

    } finally {
      window.clearTimeout(
        timeout
      );
    }

  } catch (error) {
    /*
     * Navigation must never crash the entire
     * Next.js application.
     */
    console.warn(
      "Could not load user role:",
      error,
    );


    return (
      "customer"
    );
  }
}


function HomeIcon() {
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
        d="M3 11.5L12 4l9 7.5"
      />

      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M5.5 10.5V20h13v-9.5"
      />

      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M9.5 20v-5.5h5V20"
      />
    </svg>
  );
}


function AssistantIcon() {
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
        d="M7 18l-3 2v-4.5A7.5 7.5 0 014 5.5 7.5 7.5 0 0112 2a7.5 7.5 0 018 7.5 7.5 7.5 0 01-8 7.5H7z"
      />

      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M8 9.5h.01M12 9.5h.01M16 9.5h.01"
      />
    </svg>
  );
}


function CartIcon() {
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
        d="M3 4h2l2 11h10.5l2-7H6"
      />

      <circle
        cx="9"
        cy="19"
        r="1"
      />

      <circle
        cx="17"
        cy="19"
        r="1"
      />
    </svg>
  );
}


function OrdersIcon() {
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
        d="M6 3h12v18H6z"
      />

      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M9 8h6M9 12h6M9 16h4"
      />
    </svg>
  );
}


function ProfileIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      className="h-5 w-5"
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


const NAV_ITEMS = [
  {
    href:
      "/",

    label:
      "Home",

    icon:
      HomeIcon,
  },

  {
    href:
      "/cart",

    label:
      "Cart",

    icon:
      CartIcon,
  },

  {
    href:
      "/chat",

    label:
      "Assistant",

    icon:
      AssistantIcon,

    primary:
      true,
  },

  {
    href:
      "/orders",

    label:
      "Orders",

    icon:
      OrdersIcon,
  },

  {
    href:
      "/profile",

    label:
      "Profile",

    icon:
      ProfileIcon,
  },
];


export default function MobileBottomNav() {
  const pathname =
    usePathname();


  const [
    signedIn,
    setSignedIn,
  ] =
    useState(
      false
    );


  const [
    role,
    setRole,
  ] =
    useState<UserRole | null>(
      null
    );


  useEffect(
    () => {
      let cancelled =
        false;


      async function refresh() {
        try {
          const {
            data: {
              session,
            },
          } =
            await supabase
              .auth
              .getSession();


          if (
            cancelled
          ) {
            return;
          }


          if (
            !session
          ) {
            setSignedIn(
              false
            );

            setRole(
              null
            );

            return;
          }


          setSignedIn(
            true
          );


          const resolvedRole =
            await getRole(
              session
                .access_token
            );


          if (
            cancelled
          ) {
            return;
          }


          setRole(
            resolvedRole
          );

        } catch (error) {
          console.warn(
            "Mobile navigation refresh failed:",
            error,
          );


          if (
            !cancelled
          ) {
            setRole(
              "customer"
            );
          }
        }
      }


      void refresh();


      const {
        data: {
          subscription,
        },
      } =
        supabase
          .auth
          .onAuthStateChange(
            () => {
              void refresh();
            }
          );


      return () => {
        cancelled =
          true;

        subscription
          .unsubscribe();
      };
    },
    []
  );


  if (
    !signedIn
    ||
    !role
    ||
    isPrivilegedRole(
      role
    )
  ) {
    return null;
  }


  return (
    <>
      <div
        className="ri-mobile-nav-spacer md:hidden"
        aria-hidden="true"
      />


      <nav className="fixed inset-x-0 bottom-0 z-50 border-t border-[#e4dfe2] bg-white/95 px-2 pb-[max(0.35rem,env(safe-area-inset-bottom))] pt-1.5 shadow-[0_-8px_30px_rgba(51,46,52,0.08)] backdrop-blur-xl md:hidden">

        <div className="mx-auto grid max-w-lg grid-cols-5">

          {
            NAV_ITEMS.map(
              (
                item
              ) => {
                const Icon =
                  item.icon;


                const active =
                  isActivePath(
                    pathname,
                    item.href
                  );


                return (
                  <Link
                    key={
                      item.href
                    }
                    href={
                      item.href
                    }
                    className="flex min-w-0 flex-col items-center justify-center gap-1 py-1"
                  >

                    <span
                      className={
                        (
                          "flex h-8 w-10 "
                          +
                          "items-center justify-center "
                          +
                          "rounded-xl transition "
                        )
                        +
                        (
                          item.primary
                            ? (
                              active
                                ? (
                                  "bg-[#7779de] "
                                  +
                                  "text-white"
                                )
                                : (
                                  "bg-[#eeedfb] "
                                  +
                                  "text-[#5f62c7]"
                                )
                            )
                            : (
                              active
                                ? (
                                  "bg-[#eeedfb] "
                                  +
                                  "text-[#5f62c7]"
                                )
                                : (
                                  "text-[#716a73]"
                                )
                            )
                        )
                      }
                    >
                      <Icon />
                    </span>


                    <span
                      className={
                        (
                          "max-w-full truncate "
                          +
                          "text-[9px] font-medium "
                        )
                        +
                        (
                          active
                            ? (
                              "text-[#5f62c7]"
                            )
                            : (
                              "text-[#716a73]"
                            )
                        )
                      }
                    >
                      {
                        item.label
                      }
                    </span>

                  </Link>
                );
              }
            )
          }

        </div>

      </nav>
    </>
  );
}