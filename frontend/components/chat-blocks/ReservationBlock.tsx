"use client";

import {
  useEffect,
  useState,
} from "react";

import {
  Reservation,
} from "@/lib/api";


interface Props {
  reservation:
    Reservation;

  busy?: boolean;

  onRelease: (
    id: string
  ) => void;
}


function formatCountdown(
  seconds: number
) {
  const value =
    Math.max(
      seconds,
      0
    );

  const minutes =
    Math.floor(
      value / 60
    );

  const secs =
    value % 60;

  return `${minutes}:${secs
    .toString()
    .padStart(
      2,
      "0"
    )}`;
}


export default function ReservationBlock({
  reservation,
  busy = false,
  onRelease,
}: Props) {
  const [
    secondsLeft,
    setSecondsLeft,
  ] =
    useState(0);


  useEffect(() => {
    function update() {
      const milliseconds =
        new Date(
          reservation.expires_at
        ).getTime()
        -
        Date.now();

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

    const timer =
      window.setInterval(
        update,
        1000
      );


    return () => {
      window.clearInterval(
        timer
      );
    };
  }, [
    reservation.expires_at,
  ]);


  const active =
    reservation.status
    === "active";

  const expiredByClock =
    active
    &&
    secondsLeft
    <= 0;


  return (
    <article className="min-w-0 rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-4 shadow-sm sm:p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#7f2a3c]">
            Reservation
          </p>

          <h3 className="mt-2 break-words text-lg font-semibold text-[#332e34]">
            {
              reservation.product
                ?.name
              ??
              "Reserved item"
            }
          </h3>

          <p className="mt-1 break-all text-xs text-[#8c777c] sm:text-sm">
            {
              reservation.variant
                ?.sku
              ??
              reservation.variant_id
            }
          </p>
        </div>


        <span className="w-fit rounded-full bg-[#eeeafb] px-3 py-1.5 text-xs font-semibold capitalize text-[#5f62c7]">
          {
            reservation.status
          }
        </span>
      </div>


      <div className="mt-5 grid gap-3 text-sm sm:grid-cols-2">
        <div className="rounded-xl bg-white p-3">
          <span className="block text-xs text-[#8c777c]">
            Quantity
          </span>

          <strong className="mt-1 block text-[#332e34]">
            {
              reservation.quantity
            }
          </strong>
        </div>

        <div className="min-w-0 rounded-xl bg-white p-3">
          <span className="block text-xs text-[#8c777c]">
            Branch
          </span>

          <strong className="mt-1 block break-words text-[#332e34]">
            {
              reservation.branch
                ?.name
              ??
              reservation.branch_id
            }
          </strong>
        </div>
      </div>


      {
        reservation.branch
          ?.area
        && (
          <p className="mt-3 text-sm leading-6 text-[#756369]">
            {
              reservation.branch.area
            }
            {
              reservation.branch
                .city
                ? `, ${reservation.branch.city}`
                : ""
            }
          </p>
        )
      }


      {
        active
        &&
        !expiredByClock
        && (
          <div className="mt-5 rounded-xl border border-[#ecd5a4] bg-[#fff8e8] p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#8a6424]">
              Hold expires in
            </p>

            <p className="mt-1 text-2xl font-semibold text-[#8a6424]">
              {
                formatCountdown(
                  secondsLeft
                )
              }
            </p>
          </div>
        )
      }


      {
        expiredByClock
        && (
          <div className="mt-5 rounded-xl border border-[#ecd5a4] bg-[#fff8e8] p-3 text-sm text-[#8a6424]">
            This hold has reached its expiry time.
          </div>
        )
      }


      {
        active
        &&
        !expiredByClock
        && (
          <button
            type="button"
            disabled={
              busy
            }
            onClick={() => {
              onRelease(
                reservation.id
              );
            }}
            className="mt-5 min-h-11 w-full rounded-xl border border-[#7f2a3c] px-4 py-2.5 text-sm font-semibold text-[#7f2a3c] transition hover:bg-[#f7e9e8] disabled:opacity-50 sm:w-auto"
          >
            {
              busy
                ? "Releasing..."
                : "Release hold"
            }
          </button>
        )
      }
    </article>
  );
}