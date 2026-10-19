"use client";

import Link from "next/link";

import {
  useCallback,
  useEffect,
  useState,
} from "react";

import SmartCartRuleBlock from "@/components/chat-blocks/SmartCartRuleBlock";

import {
  SmartCartAuthorization,
  SmartCartRuleListResponse,
  cancelSmartCartRule,
  createSmartCartRule,
  getSmartCartRules,
  pauseSmartCartRule,
  resumeSmartCartRule,
} from "@/lib/api";


export default function SmartCartPage() {
  const [
    data,
    setData,
  ] =
    useState<SmartCartRuleListResponse | null>(
      null
    );

  const [
    variantId,
    setVariantId,
  ] =
    useState("");

  const [
    branchId,
    setBranchId,
  ] =
    useState("");

  const [
    quantity,
    setQuantity,
  ] =
    useState(1);

  const [
    targetPrice,
    setTargetPrice,
  ] =
    useState("");

  const [
    minDiscountPercentage,
    setMinDiscountPercentage,
  ] =
    useState("");

  const [
    authorizationMode,
    setAuthorizationMode,
  ] =
    useState<SmartCartAuthorization>(
      "notify_only"
    );

  const [
    loading,
    setLoading,
  ] =
    useState(true);

  const [
    busy,
    setBusy,
  ] =
    useState<string | null>(
      null
    );

  const [
    error,
    setError,
  ] =
    useState<string | null>(
      null
    );


  const loadRules =
    useCallback(
      async (
        silent = false
      ) => {
        try {
          if (!silent) {
            setLoading(
              true
            );
          }

          const result =
            await getSmartCartRules();

          setData(
            result
          );

          if (!silent) {
            setError(
              null
            );
          }
        } catch (error) {
          if (!silent) {
            setError(
              error instanceof Error
                ? error.message
                : "Unable to load Smart Cart rules."
            );
          }
        } finally {
          if (!silent) {
            setLoading(
              false
            );
          }
        }
      },
      []
    );


  useEffect(() => {
    queueMicrotask(() => {
      void loadRules();
    });

    const intervalId =
      window.setInterval(
        () => {
          void loadRules(
            true
          );
        },
        5000
      );

    return () => {
      window.clearInterval(
        intervalId
      );
    };
  }, [
    loadRules,
  ]);


  async function handleCreate() {
    if (!variantId.trim()) {
      setError(
        "Variant UUID is required."
      );

      return;
    }

    if (quantity < 1) {
      setError(
        "Quantity must be at least 1."
      );

      return;
    }

    const hasTargetPrice =
      targetPrice.trim()
      !== "";

    const hasDiscount =
      minDiscountPercentage
        .trim()
      !== "";

    if (
      !hasTargetPrice
      &&
      !hasDiscount
    ) {
      setError(
        "Enter either a target price or a minimum discount percentage."
      );

      return;
    }

    if (
      hasTargetPrice
      &&
      Number(
        targetPrice
      ) < 0
    ) {
      setError(
        "Target price cannot be negative."
      );

      return;
    }

    if (
      hasDiscount
      &&
      (
        Number(
          minDiscountPercentage
        ) < 0
        ||
        Number(
          minDiscountPercentage
        ) > 100
      )
    ) {
      setError(
        "Discount percentage must be between 0 and 100."
      );

      return;
    }


    try {
      setBusy(
        "create"
      );

      setError(
        null
      );


      await createSmartCartRule({
        variant_id:
          variantId.trim(),

        branch_id:
          branchId.trim()
            ? branchId.trim()
            : null,

        quantity,

        target_price:
          hasTargetPrice
            ? Number(
                targetPrice
              )
            : null,

        min_discount_percentage:
          hasDiscount
            ? Number(
                minDiscountPercentage
              )
            : null,

        authorization_mode:
          authorizationMode,
      });


      setVariantId("");
      setBranchId("");
      setQuantity(1);
      setTargetPrice("");
      setMinDiscountPercentage("");

      setAuthorizationMode(
        "notify_only"
      );


      await loadRules(
        true
      );
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to create Smart Cart rule."
      );
    } finally {
      setBusy(
        null
      );
    }
  }


  async function handlePause(
    ruleId: string
  ) {
    try {
      setBusy(
        ruleId
      );

      setError(
        null
      );

      await pauseSmartCartRule(
        ruleId
      );

      await loadRules(
        true
      );
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to pause Smart Cart rule."
      );
    } finally {
      setBusy(
        null
      );
    }
  }


  async function handleResume(
    ruleId: string
  ) {
    try {
      setBusy(
        ruleId
      );

      setError(
        null
      );

      await resumeSmartCartRule(
        ruleId
      );

      await loadRules(
        true
      );
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to resume Smart Cart rule."
      );
    } finally {
      setBusy(
        null
      );
    }
  }


  async function handleCancel(
    ruleId: string
  ) {
    try {
      setBusy(
        ruleId
      );

      setError(
        null
      );

      await cancelSmartCartRule(
        ruleId
      );

      await loadRules(
        true
      );
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to cancel Smart Cart rule."
      );
    } finally {
      setBusy(
        null
      );
    }
  }


  return (
    <main className="min-h-[calc(100dvh-4rem)] overflow-x-hidden bg-[#f1e6de] text-[#2c1c20]">
      <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6 sm:py-8 lg:px-8 lg:py-10">

        <header className="mb-6 sm:mb-8">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#7f2a3c]">
                Intelligent automation
              </p>

              <h1 className="mt-2 text-3xl font-bold sm:text-4xl">
                Smart Cart
              </h1>

              <p className="mt-2 max-w-2xl text-sm leading-6 text-[#756369] sm:text-base">
                Create price and discount rules.
                Retailigent can notify you or complete
                an authorized mock purchase when your
                conditions are satisfied.
              </p>
            </div>

            <Link
              href="/chat"
              className="inline-flex min-h-11 w-full items-center justify-center rounded-xl bg-[#7f2a3c] px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-[#682132] sm:w-auto"
            >
              Ask assistant
            </Link>
          </div>


          <nav className="mt-5 flex gap-2 overflow-x-auto pb-1 sm:flex-wrap sm:overflow-visible">
            <Link
              href="/cart"
              className="shrink-0 rounded-full border border-[#d8c8c1] bg-[#fffaf7] px-4 py-2 text-sm font-medium text-[#5f4d52]"
            >
              Cart
            </Link>

            <Link
              href="/alerts"
              className="shrink-0 rounded-full border border-[#d8c8c1] bg-[#fffaf7] px-4 py-2 text-sm font-medium text-[#5f4d52]"
            >
              Alerts
            </Link>

            <Link
              href="/orders"
              className="shrink-0 rounded-full border border-[#d8c8c1] bg-[#fffaf7] px-4 py-2 text-sm font-medium text-[#5f4d52]"
            >
              Orders
            </Link>
          </nav>
        </header>


        {
          error
          && (
            <div className="mb-6 rounded-2xl border border-[#e4aaa3] bg-[#fff2ef] px-4 py-3 text-sm text-[#9b352e]">
              {
                error
              }
            </div>
          )
        }


        <section className="mb-8 rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-4 shadow-sm sm:p-6">
          <h2 className="text-xl font-semibold text-[#332e34]">
            Create Smart Cart rule
          </h2>

          <p className="mt-2 text-sm leading-6 text-[#756369]">
            Provide a target price, minimum discount,
            or both.
          </p>


          <div className="mt-6">
            <label className="block text-sm font-medium text-[#332e34]">
              Variant UUID
            </label>

            <input
              value={
                variantId
              }
              onChange={(
                event
              ) => {
                setVariantId(
                  event.target.value
                );
              }}
              placeholder="Variant UUID"
              className="mt-2 min-h-11 w-full min-w-0 rounded-xl border border-[#d8c8c1] bg-white px-3 py-2.5 text-base outline-none transition placeholder:text-[#ad999e] focus:border-[#7779de] sm:text-sm"
            />
          </div>


          <div className="mt-5">
            <label className="block text-sm font-medium text-[#332e34]">
              Branch UUID
            </label>

            <input
              value={
                branchId
              }
              onChange={(
                event
              ) => {
                setBranchId(
                  event.target.value
                );
              }}
              placeholder="Optional branch UUID"
              className="mt-2 min-h-11 w-full min-w-0 rounded-xl border border-[#d8c8c1] bg-white px-3 py-2.5 text-base outline-none transition placeholder:text-[#ad999e] focus:border-[#7779de] sm:text-sm"
            />

            <p className="mt-2 text-xs leading-5 text-[#8c777c]">
              Leave blank to let Retailigent choose
              an eligible branch.
            </p>
          </div>


          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-sm font-medium text-[#332e34]">
                Quantity
              </label>

              <input
                type="number"
                min={1}
                value={
                  quantity
                }
                onChange={(
                  event
                ) => {
                  setQuantity(
                    Math.max(
                      1,
                      Number(
                        event.target.value
                      )
                      ||
                      1
                    )
                  );
                }}
                className="mt-2 min-h-11 w-full rounded-xl border border-[#d8c8c1] bg-white px-3 py-2.5 text-base outline-none focus:border-[#7779de] sm:text-sm"
              />
            </div>


            <div>
              <label className="block text-sm font-medium text-[#332e34]">
                Target price
              </label>

              <input
                type="number"
                min={0}
                value={
                  targetPrice
                }
                onChange={(
                  event
                ) => {
                  setTargetPrice(
                    event.target.value
                  );
                }}
                placeholder="3000"
                className="mt-2 min-h-11 w-full rounded-xl border border-[#d8c8c1] bg-white px-3 py-2.5 text-base outline-none focus:border-[#7779de] sm:text-sm"
              />
            </div>
          </div>


          <div className="mt-5">
            <label className="block text-sm font-medium text-[#332e34]">
              Minimum discount percentage
            </label>

            <input
              type="number"
              min={0}
              max={100}
              value={
                minDiscountPercentage
              }
              onChange={(
                event
              ) => {
                setMinDiscountPercentage(
                  event.target.value
                );
              }}
              placeholder="Optional, e.g. 20"
              className="mt-2 min-h-11 w-full rounded-xl border border-[#d8c8c1] bg-white px-3 py-2.5 text-base outline-none focus:border-[#7779de] sm:text-sm"
            />
          </div>


          <div className="mt-5">
            <label className="block text-sm font-medium text-[#332e34]">
              Authorization mode
            </label>

            <select
              value={
                authorizationMode
              }
              onChange={(
                event
              ) => {
                setAuthorizationMode(
                  event.target
                    .value as SmartCartAuthorization
                );
              }}
              className="mt-2 min-h-11 w-full rounded-xl border border-[#d8c8c1] bg-white px-3 py-2.5 text-base outline-none focus:border-[#7779de] sm:text-sm"
            >
              <option value="notify_only">
                Notify only
              </option>

              <option value="auto_buy">
                Auto Buy
              </option>
            </select>
          </div>


          {
            authorizationMode
            === "auto_buy"
            && (
              <div className="mt-5 rounded-xl border border-[#ecd5a4] bg-[#fff8e8] p-4 text-sm leading-6 text-[#8a6424]">
                Auto Buy authorizes Retailigent to
                complete a mock purchase when this rule
                matches and stock is available.
              </div>
            )
          }


          <button
            type="button"
            disabled={
              busy
              === "create"
            }
            onClick={() => {
              void handleCreate();
            }}
            className="mt-6 min-h-11 w-full rounded-xl bg-[#ce4d42] px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-[#ad3d34] disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
          >
            {
              busy
              === "create"
                ? "Creating..."
                : "Create rule"
            }
          </button>
        </section>


        <section>
          <div className="mb-4 flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
            <h2 className="text-xl font-semibold text-[#332e34]">
              Your Smart Cart rules
            </h2>

            <span className="text-xs text-[#8c777c]">
              Auto-refreshes every 5 seconds
            </span>
          </div>


          {
            loading
            && (
              <div className="rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-5 text-sm text-[#756369] shadow-sm">
                Loading Smart Cart...
              </div>
            )
          }


          {
            !loading
            &&
            !error
            &&
            data?.items.length
            === 0
            && (
              <div className="rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-5 shadow-sm sm:p-6">
                <h3 className="text-lg font-semibold text-[#332e34]">
                  No Smart Cart rules yet
                </h3>

                <p className="mt-2 text-sm leading-6 text-[#756369]">
                  Create your first rule above.
                </p>
              </div>
            )
          }


          {
            !loading
            &&
            data
            &&
            data.items.length
            > 0
            && (
              <div className="space-y-4 sm:space-y-5">
                {
                  data.items.map(
                    (
                      rule
                    ) => (
                      <SmartCartRuleBlock
                        key={
                          rule.id
                        }
                        rule={
                          rule
                        }
                        busy={
                          busy
                          === rule.id
                        }
                        onPause={
                          handlePause
                        }
                        onResume={
                          handleResume
                        }
                        onCancel={
                          handleCancel
                        }
                      />
                    )
                  )
                }
              </div>
            )
          }
        </section>
      </div>
    </main>
  );
}