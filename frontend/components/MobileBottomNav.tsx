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
      className="h-6 w-6"
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
    href: "/",
    label: "Home",
    icon: HomeIcon,
  },
  {
    href: "/cart",
    label: "Cart",
    icon: CartIcon,
  },
  {
    href: "/chat",
    label: "Assistant",
    icon: AssistantIcon,
    primary: true,
  },
  {
    href: "/orders",
    label: "Orders",
    icon: OrdersIcon,
  },
  {
    href: "/profile",
    label: "Profile",
    icon: ProfileIcon,
  },
];


export default function MobileBottomNav() {
  const pathname =
    usePathname();

  const [
    signedIn,
    setSignedIn,
  ] =
    useState(false);


  useEffect(() => {
    let active =
      true;


    void supabase.auth
      .getSession()
      .then(
        ({
          data,
        }) => {
          if (!active) {
            return;
          }

          setSignedIn(
            Boolean(
              data.session
            )
          );
        }
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
            if (!active) {
              return;
            }

            setSignedIn(
              Boolean(session)
            );
          }
        );


    return () => {
      active = false;

      subscription.unsubscribe();
    };
  }, []);


  if (!signedIn) {
    return null;
  }


  /*
   * The chat has a sticky composer at the bottom.
   * Hiding the mobile dock there prevents overlap and
   * gives the customer maximum typing space.
   */
  if (
    pathname === "/chat"
    ||
    pathname.startsWith(
      "/chat/"
    )
  ) {
    return null;
  }


  return (
    <>
      {/*
        Flow spacer:
        prevents the fixed navigation from covering
        the final content on mobile pages.
      */}
      <div
        aria-hidden="true"
        className="h-24 xl:hidden"
      />


      <div className="fixed inset-x-0 bottom-0 z-50 xl:hidden">
        <div className="mx-auto w-full max-w-md px-3 pb-[max(0.5rem,env(safe-area-inset-bottom))]">

          <nav className="grid grid-cols-5 items-end rounded-[1.7rem] border border-[#d8c8c1]/80 bg-[#fffaf7]/95 px-2 pb-2 pt-2 shadow-[0_-12px_35px_rgba(51,46,52,0.16)] backdrop-blur-xl">

            {
              NAV_ITEMS.map(
                (
                  item
                ) => {
                  const active =
                    isActivePath(
                      pathname,
                      item.href
                    );

                  const Icon =
                    item.icon;


                  if (
                    item.primary
                  ) {
                    return (
                      <Link
                        key={
                          item.href
                        }
                        href={
                          item.href
                        }
                        aria-label={
                          item.label
                        }
                        className="group flex min-w-0 flex-col items-center justify-end"
                      >
                        <span
                          className={
                            (
                              "-mt-7 flex "
                              +
                              "h-14 w-14 "
                              +
                              "items-center "
                              +
                              "justify-center "
                              +
                              "rounded-2xl "
                              +
                              "border-4 "
                              +
                              "border-[#f1e6de] "
                              +
                              "shadow-lg "
                              +
                              "transition "
                              +
                              "group-active:scale-95 "
                            )
                            +
                            (
                              active
                                ? (
                                  "bg-[#5f62c7] "
                                  +
                                  "text-white "
                                  +
                                  "shadow-[#7779de]/30"
                                )
                                : (
                                  "bg-[#7779de] "
                                  +
                                  "text-white "
                                  +
                                  "shadow-[#7779de]/25"
                                )
                            )
                          }
                        >
                          <Icon />
                        </span>

                        <span
                          className={
                            (
                              "mt-1.5 truncate "
                              +
                              "text-[10px] "
                              +
                              "font-semibold "
                            )
                            +
                            (
                              active
                                ? "text-[#5f62c7]"
                                : "text-[#756369]"
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


                  return (
                    <Link
                      key={
                        item.href
                      }
                      href={
                        item.href
                      }
                      aria-label={
                        item.label
                      }
                      className="group flex min-w-0 flex-col items-center justify-center rounded-2xl px-1 py-1.5 transition active:scale-95"
                    >
                      <span
                        className={
                          (
                            "flex h-8 w-8 "
                            +
                            "items-center "
                            +
                            "justify-center "
                            +
                            "rounded-xl "
                            +
                            "transition "
                          )
                          +
                          (
                            active
                              ? (
                                "bg-[#eeeafb] "
                                +
                                "text-[#5f62c7]"
                              )
                              : (
                                "text-[#8c777c] "
                                +
                                "group-hover:bg-[#f1e6de] "
                                +
                                "group-hover:text-[#332e34]"
                              )
                          )
                        }
                      >
                        <Icon />
                      </span>

                      <span
                        className={
                          (
                            "mt-1 truncate "
                            +
                            "text-[10px] "
                            +
                            "font-medium "
                          )
                          +
                          (
                            active
                              ? "text-[#5f62c7]"
                              : "text-[#8c777c]"
                          )
                        }
                      >
                        {
                          item.label
                        }
                      </span>


                      <span
                        aria-hidden="true"
                        className={
                          (
                            "mt-1 h-1 "
                            +
                            "rounded-full "
                            +
                            "transition-all "
                          )
                          +
                          (
                            active
                              ? (
                                "w-4 "
                                +
                                "bg-[#7779de]"
                              )
                              : (
                                "w-1 "
                                +
                                "bg-transparent"
                              )
                          )
                        }
                      />
                    </Link>
                  );
                }
              )
            }
          </nav>
        </div>
      </div>
    </>
  );
}