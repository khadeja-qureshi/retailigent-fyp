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


const LINKS = [
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
        // Badge is best-effort.
      }
    }


    void refresh();


    const id =
      window.setInterval(
        () => {
          void refresh();
        },
        10000
      );


    const onUpdated = () => {
      void refresh();
    };


    window.addEventListener(
      "notifications-updated",
      onUpdated
    );


    return () => {
      cancelled = true;

      window.clearInterval(
        id
      );

      window.removeEventListener(
        "notifications-updated",
        onUpdated
      );
    };
  }, []);


  if (!signedIn) {
    return null;
  }


  return (
    <header className="sticky top-0 z-50 border-b border-white/10 bg-[#332e34]/95 text-white shadow-lg shadow-black/5 backdrop-blur-xl">
      <div className="mx-auto flex min-h-16 max-w-[1600px] items-center gap-4 px-4 sm:px-6">
        <Link
          href="/"
          className="group mr-2 flex shrink-0 items-center gap-3"
        >
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#7779de] font-semibold text-white shadow-lg shadow-[#7779de]/20 transition group-hover:-translate-y-0.5">
            R
          </span>

          <span className="hidden text-sm font-semibold tracking-[0.19em] text-white sm:block">
            RETAILIGENT
          </span>
        </Link>


        <nav className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto py-2">
          {LINKS.map(
            (link) => {
              const active =
                link.href === "/"
                  ? pathname === "/"
                  : (
                    pathname === link.href
                    ||
                    pathname.startsWith(
                      `${link.href}/`
                    )
                  );

              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={
                    (
                      "shrink-0 rounded-xl "
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
                          "font-medium "
                          +
                          "text-white "
                          +
                          "shadow-md "
                          +
                          "shadow-[#7779de]/20"
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
                  {link.label}
                </Link>
              );
            }
          )}
        </nav>


        <Link
          href="/notifications"
          className={
            (
              "ml-auto hidden shrink-0 "
              +
              "items-center gap-2 "
              +
              "rounded-xl px-3 py-2 "
              +
              "text-sm text-white/80 "
              +
              "transition hover:bg-white/10 "
              +
              "hover:text-white sm:flex"
            )
          }
        >
          Notifications

          {unread > 0 && (
            <span className="rounded-full bg-[#f54631] px-2 py-0.5 text-xs font-semibold text-white">
              {
                unread > 99
                  ? "99+"
                  : unread
              }
            </span>
          )}
        </Link>
      </div>
    </header>
  );
}