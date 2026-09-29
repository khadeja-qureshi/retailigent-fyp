"use client";

import {
  useEffect,
  useState,
} from "react";

import {
  Reservation,
} from "@/lib/api";


interface Props {
  reservation: Reservation;
  busy?: boolean;

  onRelease: (
    id: string
  ) => void;
}


function formatCountdown(
  seconds: number
) {
  const value = Math.max(
    seconds,
    0
  );

  const minutes = Math.floor(
    value / 60
  );

  const secs = value % 60;

  return `${minutes}:${secs
    .toString()
    .padStart(2, "0")}`;
}


export default function ReservationBlock({
  reservation,
  busy = false,
  onRelease,
}: Props) {
  const [
    secondsLeft,
    setSecondsLeft,
  ] = useState(0);

  useEffect(() => {
    function update() {
      const milliseconds =
        new Date(
          reservation.expires_at
        ).getTime()
        - Date.now();

      setSecondsLeft(
        Math.max(
          0,
          Math.ceil(
            milliseconds / 1000
          )
        )
      );
    }

    update();

    const timer = window.setInterval(
      update,
      1000
    );

    return () =>
      window.clearInterval(timer);

  }, [reservation.expires_at]);


  const active =
    reservation.status === "active";

  const expiredByClock =
    active && secondsLeft <= 0;


  return (
    <article className="rounded-2xl border border-neutral-800 bg-neutral-900 p-5">

      <p className="text-xs uppercase tracking-wide text-neutral-500">
        Reservation
      </p>

      <h3 className="mt-2 text-lg font-semibold">
        {reservation.product?.name ??
          "Reserved item"}
      </h3>

      <p className="mt-1 text-sm text-neutral-500">
        {reservation.variant?.sku ??
          reservation.variant_id}
      </p>

      <div className="mt-5 space-y-2 text-sm">

        <p>
          Quantity:{" "}
          <strong>
            {reservation.quantity}
          </strong>
        </p>

        <p>
          Branch:{" "}
          <strong>
            {reservation.branch?.name ??
              reservation.branch_id}
          </strong>
        </p>

        {reservation.branch?.area && (
          <p className="text-neutral-400">
            {reservation.branch.area}
            {reservation.branch.city
              ? `, ${reservation.branch.city}`
              : ""}
          </p>
        )}

        <p>
          Status:{" "}
          <strong className="capitalize">
            {reservation.status}
          </strong>
        </p>

      </div>

      {active && !expiredByClock && (
        <div className="mt-5 rounded-xl bg-amber-950/40 p-4">

          <p className="text-xs uppercase text-amber-300">
            Hold expires in
          </p>

          <p className="mt-1 text-2xl font-semibold text-amber-300">
            {formatCountdown(
              secondsLeft
            )}
          </p>

        </div>
      )}

      {expiredByClock && (
        <p className="mt-5 text-amber-400">
          This hold has reached its expiry time.
        </p>
      )}

      {active && !expiredByClock && (
        <button
          disabled={busy}
          onClick={() =>
            onRelease(
              reservation.id
            )
          }
          className="mt-5 rounded-lg border border-neutral-700 px-4 py-2 hover:bg-neutral-800 disabled:opacity-50"
        >
          {busy
            ? "Releasing..."
            : "Release hold"}
        </button>
      )}

    </article>
  );
}