"use client";

import {
  RetailAlert,
} from "@/lib/api";


interface Props {
  alert:
    RetailAlert;

  busy?: boolean;

  onPause: (
    id: string
  ) => void;

  onResume: (
    id: string
  ) => void;

  onDelete: (
    id: string
  ) => void;
}


function alertLabel(
  type:
    RetailAlert[
      "alert_type"
    ]
) {
  if (
    type
    === "price_drop"
  ) {
    return "Price drop";
  }

  if (
    type
    === "restock"
  ) {
    return "Restock";
  }

  return "Sale";
}


function money(
  value?:
    number
    | null
) {
  if (
    value == null
  ) {
    return "—";
  }

  return `Rs. ${value.toLocaleString()}`;
}


export default function AlertBlock({
  alert,
  busy = false,
  onPause,
  onResume,
  onDelete,
}: Props) {
  const triggered =
    Boolean(
      alert.triggered_at
    );

  const active =
    alert.is_active
    &&
    !triggered;

  const paused =
    !alert.is_active
    &&
    !triggered;


  return (
    <article className="min-w-0 rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-4 shadow-sm sm:p-6">

      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#7f2a3c]">
            Alert
          </p>

          <h3 className="mt-2 break-words text-lg font-semibold text-[#332e34] sm:text-xl">
            {
              alert.product
                ?.name
              ??
              "Product alert"
            }
          </h3>

          <p className="mt-1 break-all text-xs text-[#8c777c] sm:text-sm">
            {
              alert.variant
                ?.sku
              ??
              alert.variant_id
            }
          </p>
        </div>


        <span className="w-fit shrink-0 rounded-full bg-[#eeeafb] px-3 py-1.5 text-xs font-semibold text-[#5f62c7]">
          {
            triggered
              ? "Triggered"
              : active
                ? "Watching"
                : "Paused"
          }
        </span>
      </div>


      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl bg-white p-3">
          <span className="block text-xs text-[#8c777c]">
            Alert type
          </span>

          <strong className="mt-1 block text-[#332e34]">
            {
              alertLabel(
                alert.alert_type
              )
            }
          </strong>
        </div>


        {
          alert.target_price
          != null
          && (
            <div className="rounded-xl bg-white p-3">
              <span className="block text-xs text-[#8c777c]">
                Target
              </span>

              <strong className="mt-1 block text-[#332e34]">
                {
                  money(
                    alert.target_price
                  )
                }
              </strong>
            </div>
          )
        }


        {
          alert.effective_price
          != null
          && (
            <div className="rounded-xl bg-white p-3">
              <span className="block text-xs text-[#8c777c]">
                Current price
              </span>

              <strong className="mt-1 block text-[#332e34]">
                {
                  money(
                    alert.effective_price
                  )
                }
              </strong>
            </div>
          )
        }
      </div>


      {
        triggered
        && (
          <div className="mt-5 rounded-xl border border-[#cbdccf] bg-[#f0f8f2] p-4 text-sm leading-6 text-[#42664a]">
            Alert condition matched.
          </div>
        )
      }


      {
        paused
        && (
          <div className="mt-5 rounded-xl border border-[#d8c8c1] bg-white p-4 text-sm leading-6 text-[#756369]">
            Alert monitoring is paused.
          </div>
        )
      }


      <div className="mt-5 flex flex-col gap-2 sm:flex-row sm:flex-wrap">
        {
          active
          && (
            <button
              type="button"
              disabled={
                busy
              }
              onClick={() => {
                onPause(
                  alert.id
                );
              }}
              className="min-h-11 w-full rounded-xl border border-[#7f2a3c] px-4 py-2.5 text-sm font-semibold text-[#7f2a3c] transition hover:bg-[#f7e9e8] disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
            >
              {
                busy
                  ? "Working..."
                  : "Pause"
              }
            </button>
          )
        }


        {
          paused
          && (
            <button
              type="button"
              disabled={
                busy
              }
              onClick={() => {
                onResume(
                  alert.id
                );
              }}
              className="min-h-11 w-full rounded-xl border border-[#7779de] px-4 py-2.5 text-sm font-semibold text-[#5f62c7] transition hover:bg-[#f0effc] disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
            >
              {
                busy
                  ? "Working..."
                  : "Resume"
              }
            </button>
          )
        }


        {
          !triggered
          && (
            <button
              type="button"
              disabled={
                busy
              }
              onClick={() => {
                onDelete(
                  alert.id
                );
              }}
              className="min-h-11 w-full rounded-xl border border-[#e4aaa3] px-4 py-2.5 text-sm font-semibold text-[#b33d34] transition hover:bg-[#fff2ef] disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
            >
              {
                busy
                  ? "Working..."
                  : "Delete"
              }
            </button>
          )
        }
      </div>
    </article>
  );
}