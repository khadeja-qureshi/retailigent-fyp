"use client";

import {
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
  ] = useState("");

  const [
    branchId,
    setBranchId,
  ] = useState("");

  const [
    quantity,
    setQuantity,
  ] = useState(1);

  const [
    targetPrice,
    setTargetPrice,
  ] = useState("");

  const [
    authorizationMode,
    setAuthorizationMode,
  ] =
    useState<SmartCartAuthorization>(
      "notify_only"
    );

  const [
    error,
    setError,
  ] =
    useState<string | null>(null);

  const [
    busy,
    setBusy,
  ] =
    useState<string | null>(null);


  async function loadRules() {
    try {
      setError(null);

      setData(
        await getSmartCartRules()
      );
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to load Smart Cart rules."
      );
    }
  }


  useEffect(() => {
    loadRules();
  }, []);


  async function handleCreate() {
    if (!variantId.trim()) {
      setError(
        "Variant UUID is required."
      );
      return;
    }

    if (!targetPrice) {
      setError(
        "Enter a target price."
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
          Number(targetPrice),

        min_discount_percentage:
          null,

        authorization_mode:
          authorizationMode,
      });

      setVariantId("");
      setBranchId("");
      setQuantity(1);
      setTargetPrice("");

      await loadRules();

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
    id: string
  ) {
    try {
      setBusy(id);

      await pauseSmartCartRule(id);

      await loadRules();

    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to pause rule."
      );

    } finally {
      setBusy(null);
    }
  }


  async function handleResume(
    id: string
  ) {
    try {
      setBusy(id);

      await resumeSmartCartRule(id);

      await loadRules();

    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to resume rule."
      );

    } finally {
      setBusy(null);
    }
  }


  async function handleCancel(
    id: string
  ) {
    try {
      setBusy(id);

      await cancelSmartCartRule(id);

      await loadRules();

    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to cancel rule."
      );

    } finally {
      setBusy(null);
    }
  }


  return (
    <main className="min-h-screen bg-neutral-950 text-white">

      <div className="mx-auto max-w-3xl p-6 md:p-10">

        <div className="mb-8 flex items-center justify-between">

          <div>
            <p className="text-sm text-neutral-500">
              Retailigent
            </p>

            <h1 className="text-3xl font-semibold">
              Smart Cart
            </h1>

            <p className="mt-2 text-neutral-400">
              Create price rules and optionally
              allow Retailigent to purchase
              automatically.
            </p>
          </div>

          <nav className="flex gap-4 text-sm">
            <Link
              href="/alerts"
              className="underline"
            >
              Alerts
            </Link>

            <Link
              href="/orders"
              className="underline"
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


        <section className="mb-8 rounded-2xl border border-neutral-800 bg-neutral-900 p-6">

          <h2 className="text-xl font-semibold">
            Create Smart Cart rule
          </h2>

          <p className="mt-2 text-sm text-neutral-400">
            Auto Buy means Retailigent may complete
            the mock purchase when your condition
            matches.
          </p>


          <label className="mt-5 block text-sm">
            Variant UUID
          </label>

          <input
            value={variantId}
            onChange={(event) =>
              setVariantId(
                event.target.value
              )
            }
            className="mt-2 w-full rounded-lg border border-neutral-700 bg-neutral-950 p-3"
            placeholder="Variant UUID"
          />


          <label className="mt-5 block text-sm">
            Branch UUID
          </label>

          <input
            value={branchId}
            onChange={(event) =>
              setBranchId(
                event.target.value
              )
            }
            className="mt-2 w-full rounded-lg border border-neutral-700 bg-neutral-950 p-3"
            placeholder="Optional branch UUID"
          />


          <div className="mt-5 grid gap-4 md:grid-cols-2">

            <div>
              <label className="block text-sm">
                Quantity
              </label>

              <input
                type="number"
                min={1}
                value={quantity}
                onChange={(event) =>
                  setQuantity(
                    Math.max(
                      1,
                      Number(
                        event.target.value
                      )
                    )
                  )
                }
                className="mt-2 w-full rounded-lg border border-neutral-700 bg-neutral-950 p-3"
              />
            </div>


            <div>
              <label className="block text-sm">
                Target price
              </label>

              <input
                type="number"
                min={0}
                value={targetPrice}
                onChange={(event) =>
                  setTargetPrice(
                    event.target.value
                  )
                }
                className="mt-2 w-full rounded-lg border border-neutral-700 bg-neutral-950 p-3"
                placeholder="3000"
              />
            </div>

          </div>


          <label className="mt-5 block text-sm">
            Authorization mode
          </label>

          <select
            value={authorizationMode}
            onChange={(event) => {
  const value =
    event.target.value as SmartCartAuthorization;

  setAuthorizationMode(value);
}}
            className="mt-2 w-full rounded-lg border border-neutral-700 bg-neutral-950 p-3"
          >
            <option value="notify_only">
              Notify only
            </option>

            <option value="auto_buy">
              Auto Buy
            </option>
          </select>


          <button
            disabled={
              busy === "create"
            }
            onClick={handleCreate}
            className="mt-6 rounded-lg bg-white px-5 py-3 font-medium text-black disabled:opacity-50"
          >
            {busy === "create"
              ? "Creating..."
              : "Create rule"}
          </button>

        </section>


        <h2 className="mb-4 text-xl font-semibold">
          Your rules
        </h2>


        {!data ? (
          <p className="text-neutral-400">
            Loading Smart Cart...
          </p>

        ) : data.items.length === 0 ? (
          <p className="text-neutral-400">
            No Smart Cart rules yet.
          </p>

        ) : (
          <div className="space-y-4">

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

      </div>

    </main>
  );
}