"use client";

import {
  FormEvent,
  useState,
} from "react";
import { useRouter } from "next/navigation";

import { supabase } from "@/lib/supabase/client";

type AuthMode = "signin" | "signup";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000";

const ROLE_REDIRECTS: Record<string, string> = {
  customer: "/",
  staff: "/admin/tickets",
  admin: "/admin",
};

export default function LoginPage() {
  const router = useRouter();

  const [mode, setMode] =
    useState<AuthMode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] =
    useState("");
  const [error, setError] =
    useState<string | null>(null);
  const [message, setMessage] =
    useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function switchMode(nextMode: AuthMode) {
    setMode(nextMode);
    setError(null);
    setMessage(null);
  }

  async function redirectByRole() {
    const {
      data: { session },
      error: sessionError,
    } = await supabase.auth.getSession();

    if (sessionError || !session?.access_token) {
      throw new Error(
        "Your session could not be verified. Please sign in again."
      );
    }

    const response = await fetch(
      `${API_URL}/api/v1/me/role`,
      {
        method: "GET",
        headers: {
          Authorization:
            `Bearer ${session.access_token}`,
        },
        cache: "no-store",
      }
    );

    if (!response.ok) {
      throw new Error(
        "We couldn't verify your account role. Please try again."
      );
    }

    const data: { role?: string } =
      await response.json();

    const destination =
      data.role
        ? ROLE_REDIRECTS[data.role]
        : undefined;

    if (!destination) {
      throw new Error(
        "Your account doesn't have a supported role. Please contact an administrator."
      );
    }

    router.replace(destination);
  }

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    setLoading(true);
    setError(null);
    setMessage(null);

    try {
      if (mode === "signup") {
        if (password.length < 8) {
          throw new Error(
            "Your password must contain at least 8 characters."
          );
        }

        if (password !== confirmPassword) {
          throw new Error(
            "The passwords do not match."
          );
        }

        const { data, error: signupError } =
          await supabase.auth.signUp({
            email: email.trim(),
            password,
          });

        if (signupError) {
          throw signupError;
        }

        if (!data.session) {
          setMessage(
            "Your account has been created. Check your email to confirm your account, then sign in."
          );
          setMode("signin");
          setPassword("");
          setConfirmPassword("");
          return;
        }

        // Public signup is customer-only. The database
        // trigger assigns the customer role.
        await redirectByRole();
        return;
      }

      const { error: signinError } =
        await supabase.auth.signInWithPassword({
          email: email.trim(),
          password,
        });

      if (signinError) {
        throw signinError;
      }

      await redirectByRole();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Something went wrong. Please try again."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-neutral-950 p-6 text-white">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-md rounded-2xl border border-neutral-800 bg-neutral-900 p-8"
      >
        <h1 className="text-3xl font-semibold">
          Retailigent
        </h1>

        <p className="mt-2 text-neutral-400">
          {mode === "signin"
            ? "Sign in to your account"
            : "Create your customer account"}
        </p>

        <div
          className="mt-7 grid grid-cols-2 rounded-lg border border-neutral-800 bg-neutral-950 p-1"
          aria-label="Authentication mode"
        >
          <button
            type="button"
            onClick={() => switchMode("signin")}
            aria-pressed={mode === "signin"}
            className={`rounded-md p-2 text-sm font-medium transition ${
              mode === "signin"
                ? "bg-white text-black"
                : "text-neutral-400 hover:text-white"
            }`}
          >
            Sign In
          </button>

          <button
            type="button"
            onClick={() => switchMode("signup")}
            aria-pressed={mode === "signup"}
            className={`rounded-md p-2 text-sm font-medium transition ${
              mode === "signup"
                ? "bg-white text-black"
                : "text-neutral-400 hover:text-white"
            }`}
          >
            Create Account
          </button>
        </div>

        <label
          htmlFor="email"
          className="mt-7 block text-sm"
        >
          Email
        </label>

        <input
          id="email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(event) =>
            setEmail(event.target.value)
          }
          required
          className="mt-2 w-full rounded-lg border border-neutral-700 bg-neutral-950 p-3 outline-none focus:border-neutral-400"
        />

        <label
          htmlFor="password"
          className="mt-5 block text-sm"
        >
          Password
        </label>

        <input
          id="password"
          type="password"
          autoComplete={
            mode === "signin"
              ? "current-password"
              : "new-password"
          }
          value={password}
          onChange={(event) =>
            setPassword(event.target.value)
          }
          minLength={mode === "signup" ? 8 : undefined}
          required
          className="mt-2 w-full rounded-lg border border-neutral-700 bg-neutral-950 p-3 outline-none focus:border-neutral-400"
        />

        {mode === "signup" && (
          <>
            <label
              htmlFor="confirmPassword"
              className="mt-5 block text-sm"
            >
              Confirm password
            </label>

            <input
              id="confirmPassword"
              type="password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(event) =>
                setConfirmPassword(event.target.value)
              }
              minLength={8}
              required
              className="mt-2 w-full rounded-lg border border-neutral-700 bg-neutral-950 p-3 outline-none focus:border-neutral-400"
            />

            <p className="mt-3 text-xs text-neutral-500">
              Public registration creates customer accounts only.
            </p>
          </>
        )}

        {error && (
          <p
            role="alert"
            className="mt-4 text-sm text-red-400"
          >
            {error}
          </p>
        )}

        {message && (
          <p
            role="status"
            className="mt-4 text-sm text-emerald-400"
          >
            {message}
          </p>
        )}

        <button
          type="submit"
          disabled={loading}
          className="mt-6 w-full rounded-lg bg-white p-3 font-medium text-black transition hover:bg-neutral-200 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading
            ? "Please wait..."
            : mode === "signin"
              ? "Sign In"
              : "Create Account"}
        </button>
      </form>
    </main>
  );
}
