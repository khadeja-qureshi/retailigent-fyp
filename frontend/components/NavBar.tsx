"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { getUnreadNotificationCount } from "@/lib/api";
import { supabase } from "@/lib/supabase/client";


const LINKS = [
  { href: "/cart", label: "Cart" },
  { href: "/wishlist", label: "Wishlist" },
  { href: "/reservations", label: "Reservations" },
  { href: "/orders", label: "Orders" },
  { href: "/smart-cart", label: "Smart Cart" },
  { href: "/alerts", label: "Alerts" },
];


export default function NavBar() {
  const [unread, setUnread] =
    useState(0);

  const [signedIn, setSignedIn] =
    useState(false);


  useEffect(() => {
    let cancelled = false;

    async function refresh() {
      const {
        data: { session },
      } = await supabase.auth.getSession();

      if (cancelled) {
        return;
      }

      setSignedIn(Boolean(session));

      if (!session) {
        setUnread(0);
        return;
      }

      try {
        const result =
          await getUnreadNotificationCount();

        if (!cancelled) {
          setUnread(result.unread_count);
        }
      } catch {
        // Badge is best-effort; ignore transient errors.
      }
    }

    void refresh();

    const id = window.setInterval(() => {
      void refresh();
    }, 10000);

    const onUpdated = () => {
      void refresh();
    };

    window.addEventListener(
      "notifications-updated",
      onUpdated
    );

    return () => {
      cancelled = true;
      window.clearInterval(id);
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
    <nav className="flex flex-wrap items-center gap-5 border-b border-neutral-800 bg-black px-6 py-3 text-sm text-neutral-300">

      {LINKS.map((link) => (
        <Link
          key={link.href}
          href={link.href}
          className="hover:text-white"
        >
          {link.label}
        </Link>
      ))}

      <Link
        href="/notifications"
        className="ml-auto flex items-center gap-2 hover:text-white"
        aria-label={`Notifications, ${unread} unread`}
      >
        Notifications

        {unread > 0 && (
          <span className="rounded-full bg-red-600 px-2 py-0.5 text-xs text-white">
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </Link>

    </nav>
  );
}
