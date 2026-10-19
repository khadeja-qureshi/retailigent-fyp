"use client";

import {
  SmartCartRule,
} from "@/lib/api";


interface Props {
  rule:
    SmartCartRule;

  busy?: boolean;

  onPause: (
    id: string
  ) => void;

  onResume: (
    id: string
  ) => void;

  onCancel: (
    id: string
  ) => void;
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


export default function SmartCartRuleBlock({
  rule,
  busy = false,
  onPause,
  onResume,
  onCancel,
}: Props) {
  const active =
    rule.status
    === "active";

  const paused =
    rule.status
    === "paused";

  const completed =
    rule.status
    === "completed";

  const triggered =
    rule.status
    === "triggered";


  return (
    <article className="min-w-0 rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-4 shadow-sm sm:p-6">

      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#7f2a3c]">
            Smart Cart
          </p>

          <h3 className="mt-2 break-words text-lg font-semibold text-[#332e34] sm:text-xl">
            {
              rule.product
                ?.name
              ??
              "Smart Cart item"
            }
          </h3>

          <p className="mt-1 break-all text-xs text-[#8c777c] sm:text-sm">
            {
              rule.variant
                ?.sku
              ??
              rule.variant_id
            }
          </p>
        </div>


        <span className="w-fit shrink-0 rounded-full bg-[#eeeafb] px-3 py-1.5 text-xs font-semibold capitalize text-[#5f62c7]">
          {
            rule.status
          }
        </span>
      </div>


      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl bg-white p-3">
          <span className="block text-xs text-[#8c777c]">
            Quantity
          </span>

          <strong className="mt-1 block text-[#332e34]">
            {
              rule.quantity
            }
          </strong>
        </div>


        <div className="rounded-xl bg-white p-3">
          <span className="block text-xs text-[#8c777c]">
            Current price
          </span>

          <strong className="mt-1 block text-[#332e34]">
            {
              money(
                rule.effective_price
              )
            }
          </strong>
        </div>


        {
          rule.target_price
          != null
          && (
            <div className="rounded-xl bg-white p-3">
              <span className="block text-xs text-[#8c777c]">
                Target price
              </span>

              <strong className="mt-1 block text-[#332e34]">
                {
                  money(
                    rule.target_price
                  )
                }
              </strong>
            </div>
          )
        }


        {
          rule.min_discount_percentage
          != null
          && (
            <div className="rounded-xl bg-white p-3">
              <span className="block text-xs text-[#8c777c]">
                Minimum discount
              </span>

              <strong className="mt-1 block text-[#332e34]">
                {
                  rule.min_discount_percentage
                }
                %
              </strong>
            </div>
          )
        }


        <div className="rounded-xl bg-white p-3">
          <span className="block text-xs text-[#8c777c]">
            Mode
          </span>

          <strong className="mt-1 block text-[#332e34]">
            {
              rule.authorization_mode
              === "auto_buy"
                ? "Auto Buy"
                : "Notify Only"
            }
          </strong>
        </div>


        {
          rule.branch
          && (
            <div className="min-w-0 rounded-xl bg-white p-3">
              <span className="block text-xs text-[#8c777c]">
                Branch
              </span>

              <strong className="mt-1 block break-words text-[#332e34]">
                {
                  rule.branch.name
                }
              </strong>
            </div>
          )
        }
      </div>


      {
        completed
        && (
          <div className="mt-5 rounded-xl border border-[#cbdccf] bg-[#f0f8f2] p-4 text-sm leading-6 text-[#42664a]">
            Purchase completed automatically.
          </div>
        )
      }


      {
        triggered
        && (
          <div className="mt-5 rounded-xl border border-[#ecd5a4] bg-[#fff8e8] p-4 text-sm leading-6 text-[#8a6424]">
            Conditions matched. Processing action...
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
                  rule.id
                );
              }}
              className="min-h-11 w-full rounded-xl border border-[#7f2a3c] px-4 py-2.5 text-sm font-semibold text-[#7f2a3c] transition hover:bg-[#f7e9e8] disabled:opacity-50 sm:w-auto"
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
                  rule.id
                );
              }}
              className="min-h-11 w-full rounded-xl border border-[#7779de] px-4 py-2.5 text-sm font-semibold text-[#5f62c7] transition hover:bg-[#f0effc] disabled:opacity-50 sm:w-auto"
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
          (
            active
            ||
            paused
          )
          && (
            <button
              type="button"
              disabled={
                busy
              }
              onClick={() => {
                onCancel(
                  rule.id
                );
              }}
              className="min-h-11 w-full rounded-xl border border-[#e4aaa3] px-4 py-2.5 text-sm font-semibold text-[#b33d34] transition hover:bg-[#fff2ef] disabled:opacity-50 sm:w-auto"
            >
              {
                busy
                  ? "Working..."
                  : "Cancel"
              }
            </button>
          )
        }
      </div>
    </article>
  );
}