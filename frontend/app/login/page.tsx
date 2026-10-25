"use client";

import {
  FormEvent,
  useState,
} from "react";

import {
  useRouter,
} from "next/navigation";

import {
  supabase,
} from "@/lib/supabase/client";


type AuthMode =
  | "signin"
  | "signup";


const API_URL =
  process.env.NEXT_PUBLIC_API_URL
  ??
  "http://127.0.0.1:8000";


const ROLE_REDIRECTS:
Record<string, string> = {
  customer: "/",
  staff: "/admin",
  manager: "/admin",
  admin: "/admin",
};


export default function LoginPage() {
  const router =
    useRouter();

  const [
    mode,
    setMode,
  ] =
    useState<AuthMode>(
      "signin"
    );

  const [
    email,
    setEmail,
  ] =
    useState("");

  const [
    password,
    setPassword,
  ] =
    useState("");

  const [
    confirmPassword,
    setConfirmPassword,
  ] =
    useState("");

  const [
    error,
    setError,
  ] =
    useState<
      string | null
    >(null);

  const [
    message,
    setMessage,
  ] =
    useState<
      string | null
    >(null);

  const [
    loading,
    setLoading,
  ] =
    useState(false);


  function switchMode(
    nextMode: AuthMode
  ) {
    setMode(
      nextMode
    );

    setError(
      null
    );

    setMessage(
      null
    );
  }


  async function redirectByRole() {
    const {
      data: {
        session,
      },
      error:
        sessionError,
    } =
      await supabase.auth
        .getSession();

    if (
      sessionError
      ||
      !session?.access_token
    ) {
      throw new Error(
        "Your session could not be verified. "
        +
        "Please sign in again."
      );
    }


    const response =
      await fetch(
        `${API_URL}/api/v1/me/role`,
        {
          method: "GET",

          headers: {
            Authorization:
              `Bearer ${session.access_token}`,
          },

          cache:
            "no-store",
        }
      );


    if (!response.ok) {
      let detail =
        "We couldn't verify your account role.";

      try {
        const payload =
          await response.json();

        if (
          typeof payload.detail
          === "string"
        ) {
          detail =
            payload.detail;
        }
      } catch {
        // Keep fallback.
      }

      throw new Error(
        detail
      );
    }


    const data: {
      role?: string;
    } =
      await response.json();


    const destination =
      data.role
        ? ROLE_REDIRECTS[
            data.role
          ]
        : undefined;


    if (!destination) {
      throw new Error(
        "Your account doesn't have a "
        +
        "supported Retailigent role."
      );
    }


    router.replace(
      destination
    );

    router.refresh();
  }


  async function handleSubmit(
    event:
      FormEvent<
        HTMLFormElement
      >
  ) {
    event.preventDefault();

    setLoading(
      true
    );

    setError(
      null
    );

    setMessage(
      null
    );


    try {
      if (
        mode
        === "signup"
      ) {
        if (
          password.length
          < 8
        ) {
          throw new Error(
            "Your password must contain "
            +
            "at least 8 characters."
          );
        }

        if (
          password
          !== confirmPassword
        ) {
          throw new Error(
            "The passwords do not match."
          );
        }


        const {
          data,
          error:
            signupError,
        } =
          await supabase.auth
            .signUp({
              email:
                email.trim(),

              password,
            });


        if (
          signupError
        ) {
          throw signupError;
        }


        if (
          !data.session
        ) {
          setMessage(
            "Your account has been created. "
            +
            "Check your email to confirm your "
            +
            "account, then sign in."
          );

          setMode(
            "signin"
          );

          setPassword(
            ""
          );

          setConfirmPassword(
            ""
          );

          return;
        }


        await redirectByRole();

        return;
      }


      const {
        error:
          signinError,
      } =
        await supabase.auth
          .signInWithPassword({
            email:
              email.trim(),

            password,
          });


      if (
        signinError
      ) {
        throw signinError;
      }


      await redirectByRole();

    } catch (
      caught
    ) {
      setError(
        caught instanceof Error
          ? caught.message
          : (
            "Something went wrong. "
            +
            "Please try again."
          )
      );

    } finally {
      setLoading(
        false
      );
    }
  }


  return (
    <main className="flex min-h-screen items-center justify-center bg-[#f4efec] p-6 text-[#332e34]">

      <form
        onSubmit={
          handleSubmit
        }
        className="w-full max-w-md rounded-3xl border border-[#ded8e2] bg-white p-8 shadow-xl"
      >
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#7779de]">
          Retailigent
        </p>

        <h1 className="mt-2 text-3xl font-bold">
          {
            mode
            === "signin"
              ? "Welcome back"
              : "Create account"
          }
        </h1>

        <p className="mt-2 text-sm leading-6 text-[#716a73]">
          {
            mode
            === "signin"
              ? (
                "Sign in as a customer or "
                +
                "authorized staff member."
              )
              : (
                "Public signup creates a "
                +
                "customer account."
              )
          }
        </p>


        <div className="mt-7 grid grid-cols-2 rounded-xl bg-[#f4f1f5] p-1">
          <button
            type="button"
            onClick={() =>
              switchMode(
                "signin"
              )
            }
            className={
              (
                "rounded-lg px-3 py-2 "
                +
                "text-sm font-semibold transition "
              )
              +
              (
                mode
                === "signin"
                  ? (
                    "bg-white text-[#332e34] "
                    +
                    "shadow-sm"
                  )
                  : (
                    "text-[#716a73]"
                  )
              )
            }
          >
            Sign In
          </button>

          <button
            type="button"
            onClick={() =>
              switchMode(
                "signup"
              )
            }
            className={
              (
                "rounded-lg px-3 py-2 "
                +
                "text-sm font-semibold transition "
              )
              +
              (
                mode
                === "signup"
                  ? (
                    "bg-white text-[#332e34] "
                    +
                    "shadow-sm"
                  )
                  : (
                    "text-[#716a73]"
                  )
              )
            }
          >
            Create Account
          </button>
        </div>


        {
          error
          && (
            <div
              role="alert"
              className="mt-5 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800"
            >
              {
                error
              }
            </div>
          )
        }


        {
          message
          && (
            <div
              role="status"
              className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800"
            >
              {
                message
              }
            </div>
          )
        }


        <label className="mt-6 block text-sm font-semibold">
          Email

          <input
            type="email"
            required
            autoComplete="email"
            value={
              email
            }
            onChange={
              (
                event
              ) =>
                setEmail(
                  event.target.value
                )
            }
            className="mt-2 min-h-12 w-full rounded-xl border border-[#ded8e2] bg-white px-4 font-normal outline-none transition focus:border-[#7779de] focus:ring-2 focus:ring-[#7779de]/15"
            placeholder="you@example.com"
          />
        </label>


        <label className="mt-4 block text-sm font-semibold">
          Password

          <input
            type="password"
            required
            minLength={
              8
            }
            autoComplete={
              mode
              === "signin"
                ? (
                  "current-password"
                )
                : (
                  "new-password"
                )
            }
            value={
              password
            }
            onChange={
              (
                event
              ) =>
                setPassword(
                  event.target.value
                )
            }
            className="mt-2 min-h-12 w-full rounded-xl border border-[#ded8e2] bg-white px-4 font-normal outline-none transition focus:border-[#7779de] focus:ring-2 focus:ring-[#7779de]/15"
          />
        </label>


        {
          mode
          === "signup"
          && (
            <label className="mt-4 block text-sm font-semibold">
              Confirm password

              <input
                type="password"
                required
                minLength={
                  8
                }
                autoComplete="new-password"
                value={
                  confirmPassword
                }
                onChange={
                  (
                    event
                  ) =>
                    setConfirmPassword(
                      event.target.value
                    )
                }
                className="mt-2 min-h-12 w-full rounded-xl border border-[#ded8e2] bg-white px-4 font-normal outline-none transition focus:border-[#7779de] focus:ring-2 focus:ring-[#7779de]/15"
              />
            </label>
          )
        }


        <button
          type="submit"
          disabled={
            loading
          }
          className="mt-7 min-h-12 w-full rounded-xl bg-[#7779de] px-4 font-semibold text-white transition hover:bg-[#6567ca] disabled:cursor-wait disabled:opacity-60"
        >
          {
            loading
              ? (
                "Please wait..."
              )
              : mode
                === "signin"
                ? (
                  "Sign In"
                )
                : (
                  "Create Account"
                )
          }
        </button>


        {
          mode
          === "signin"
          && (
            <p className="mt-5 text-center text-xs leading-5 text-[#8a828b]">
              Staff and customers use the same
              sign-in page. Retailigent redirects
              you according to your assigned role.
            </p>
          )
        }
      </form>
    </main>
  );
}