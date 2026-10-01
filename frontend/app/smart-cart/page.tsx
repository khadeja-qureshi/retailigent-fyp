"use client";

import {
  useCallback,
  useEffect,
  useState,
} from "react";

import Link from "next/link";

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
  const [data, setData] =
    useState<SmartCartRuleListResponse | null>(
      null
    );

  const [variantId, setVariantId] =
    useState("");

  const [branchId, setBranchId] =
    useState("");

  const [quantity, setQuantity] =
    useState(1);

  const [targetPrice, setTargetPrice] =
    useState("");

  const [
    minDiscountPercentage,
    setMinDiscountPercentage,
  ] = useState("");

  const [
    authorizationMode,
    setAuthorizationMode,
  ] =
    useState<SmartCartAuthorization>(
      "notify_only"
    );

  const [loading, setLoading] =
    useState(true);

  const [busy, setBusy] =
    useState<string | null>(null);

  const [error, setError] =
    useState<string | null>(null);


  const loadRules = useCallback(
    async (silent = false) => {
      try {
        if (!silent) {
          setLoading(true);
        }

        const result =
          await getSmartCartRules();

        setData(result);

        if (!silent) {
          setError(null);
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
          setLoading(false);
        }
      }
    },
    []
  );


  useEffect(() => {
    void loadRules();

    // Poll every 2 seconds.
    // This lets Active -> Triggered -> Completed
    // appear automatically without refreshing.
    const intervalId =
      window.setInterval(() => {
        void loadRules(true);
      }, 2000);

    return () => {
      window.clearInterval(
        intervalId
      );
    };
  }, [loadRules]);


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
      targetPrice.trim() !== "";

    const hasDiscount =
      minDiscountPercentage.trim() !== "";

    if (
      !hasTargetPrice &&
      !hasDiscount
    ) {
      setError(
        "Enter either a target price or a minimum discount percentage."
      );
      return;
    }

    if (
      hasTargetPrice &&
      Number(targetPrice) < 0
    ) {
      setError(
        "Target price cannot be negative."
      );
      return;
    }

    if (
      hasDiscount &&
      (
        Number(minDiscountPercentage) < 0 ||
        Number(minDiscountPercentage) > 100
      )
    ) {
      setError(
        "Discount percentage must be between 0 and 100."
      );
      return;
    }

    try {
      setBusy("create");
      setError(null);

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
            ? Number(targetPrice)
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

      await loadRules(true);

    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to create Smart Cart rule."
      );

    } finally {
      setBusy(null);
    }
  }


  async function handlePause(
    ruleId: string
  ) {
    try {
      setBusy(ruleId);
      setError(null);

      await pauseSmartCartRule(
        ruleId
      );

      await loadRules(true);

    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to pause Smart Cart rule."
      );

    } finally {
      setBusy(null);
    }
  }


  async function handleResume(
    ruleId: string
  ) {
    try {
      setBusy(ruleId);
      setError(null);

      await resumeSmartCartRule(
        ruleId
      );

      await loadRules(true);

    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to resume Smart Cart rule."
      );

    } finally {
      setBusy(null);
    }
  }


  async function handleCancel(
    ruleId: string
  ) {
    try {
      setBusy(ruleId);
      setError(null);

      await cancelSmartCartRule(
        ruleId
      );

      await loadRules(true);

    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to cancel Smart Cart rule."
      );

    } finally {
      setBusy(null);
    }
  }


  return (
    <main className="min-h-screen bg-black px-6 py-10 text-white">

      <div className="mx-auto max-w-4xl">

        <div className="mb-8 flex flex-col gap-5 md:flex-row md:items-start md:justify-between">

          <div>
            <p className="text-sm uppercase tracking-widest text-neutral-500">
              Retailigent
            </p>

            <h1 className="mt-2 text-3xl font-semibold">
              Smart Cart
            </h1>

            <p className="mt-2 max-w-xl text-neutral-400">
              Create intelligent purchase rules.
              Retailigent can notify you or
              automatically complete a mock purchase
              when your conditions are satisfied.
            </p>
          </div>


          <nav className="flex flex-wrap gap-4 text-sm text-neutral-300">

            <Link
              href="/cart"
              className="underline hover:text-white"
            >
              Cart
            </Link>

            <Link
              href="/alerts"
              className="underline hover:text-white"
            >
              Alerts
            </Link>

            <Link
              href="/orders"
              className="underline hover:text-white"
            >
              Orders
            </Link>

          </nav>

        </div>


        {error && (
          <div className="mb-6 rounded-xl border border-red-900 bg-red-950/30 p-4 text-red-300">
            {error}
          </div>
        )}


        <section className="mb-10 rounded-2xl border border-neutral-800 bg-neutral-900 p-6">

          <h2 className="text-xl font-semibold">
            Create Smart Cart rule
          </h2>

          <p className="mt-2 text-sm text-neutral-400">
            Provide a target price, minimum
            discount, or both.
          </p>


          <div className="mt-6">

            <label className="block text-sm font-medium">
              Variant UUID
            </label>

            <input
              value={variantId}
              onChange={(event) => {
                setVariantId(
                  event.target.value
                );
              }}
              placeholder="f1000000-0000-0000-0000-000000000003"
              className="mt-2 w-full rounded-lg border border-neutral-700 bg-neutral-950 p-3 outline-none focus:border-neutral-500"
            />

          </div>


          <div className="mt-5">

            <label className="block text-sm font-medium">
              Branch UUID
            </label>

            <input
              value={branchId}
              onChange={(event) => {
                setBranchId(
                  event.target.value
                );
              }}
              placeholder="Optional branch UUID"
              className="mt-2 w-full rounded-lg border border-neutral-700 bg-neutral-950 p-3 outline-none focus:border-neutral-500"
            />

            <p className="mt-2 text-xs text-neutral-500">
              Leave blank to let Retailigent
              choose an eligible branch.
            </p>

          </div>


          <div className="mt-5 grid gap-5 md:grid-cols-2">

            <div>
              <label className="block text-sm font-medium">
                Quantity
              </label>

              <input
                type="number"
                min={1}
                value={quantity}
                onChange={(event) => {
                  setQuantity(
                    Math.max(
                      1,
                      Number(
                        event.target.value
                      ) || 1
                    )
                  );
                }}
                className="mt-2 w-full rounded-lg border border-neutral-700 bg-neutral-950 p-3 outline-none focus:border-neutral-500"
              />
            </div>


            <div>
              <label className="block text-sm font-medium">
                Target price
              </label>

              <input
                type="number"
                min={0}
                value={targetPrice}
                onChange={(event) => {
                  setTargetPrice(
                    event.target.value
                  );
                }}
                placeholder="3000"
                className="mt-2 w-full rounded-lg border border-neutral-700 bg-neutral-950 p-3 outline-none focus:border-neutral-500"
              />
            </div>

          </div>


          <div className="mt-5">

            <label className="block text-sm font-medium">
              Minimum discount percentage
            </label>

            <input
              type="number"
              min={0}
              max={100}
              value={
                minDiscountPercentage
              }
              onChange={(event) => {
                setMinDiscountPercentage(
                  event.target.value
                );
              }}
              placeholder="Optional, e.g. 20"
              className="mt-2 w-full rounded-lg border border-neutral-700 bg-neutral-950 p-3 outline-none focus:border-neutral-500"
            />

          </div>


          <div className="mt-5">

            <label className="block text-sm font-medium">
              Authorization mode
            </label>

            <select
              value={authorizationMode}
              onChange={(event) => {
                const value =
                  event.target
                    .value as SmartCartAuthorization;

                setAuthorizationMode(
                  value
                );
              }}
              className="mt-2 w-full rounded-lg border border-neutral-700 bg-neutral-950 p-3 outline-none focus:border-neutral-500"
            >

              <option value="notify_only">
                Notify only
              </option>

              <option value="auto_buy">
                Auto Buy
              </option>

            </select>

          </div>


          {authorizationMode ===
            "auto_buy" && (
            <div className="mt-5 rounded-xl border border-amber-900 bg-amber-950/20 p-4 text-sm text-amber-200">

              Auto Buy authorizes Retailigent
              to complete a mock purchase when
              this rule matches and stock is
              available.

            </div>
          )}


          <button
            type="button"
            disabled={
              busy === "create"
            }
            onClick={() => {
              void handleCreate();
            }}
            className="mt-6 rounded-lg bg-white px-5 py-3 font-medium text-black transition hover:bg-neutral-200 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy === "create"
              ? "Creating..."
              : "Create rule"}
          </button>

        </section>


        <section>

          <div className="mb-4 flex items-center justify-between">

            <h2 className="text-xl font-semibold">
              Your Smart Cart rules
            </h2>

            <span className="text-xs text-neutral-500">
              Auto-refreshes every 2 seconds
            </span>

          </div>


          {loading && (
            <p className="text-neutral-400">
              Loading Smart Cart...
            </p>
          )}


          {!loading &&
            !error &&
            data?.items.length === 0 && (
              <div className="rounded-2xl border border-neutral-800 bg-neutral-900 p-6">

                <h3 className="text-lg font-semibold">
                  No Smart Cart rules yet
                </h3>

                <p className="mt-2 text-neutral-400">
                  Create your first rule above.
                </p>

              </div>
            )}


          {!loading &&
            data &&
            data.items.length > 0 && (
              <div className="space-y-5">

                {data.items.map(
                  (rule) => (
                    <SmartCartRuleBlock
                      key={rule.id}
                      rule={rule}
                      busy={
                        busy === rule.id
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
                )}

              </div>
            )}

        </section>

      </div>

    </main>
  );
}