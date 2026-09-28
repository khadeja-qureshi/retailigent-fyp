"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { supabase } from "@/lib/supabase/client";


export default function LoginPage() {
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] =
    useState("");
  const [error, setError] =
    useState<string | null>(null);
  const [loading, setLoading] =
    useState(false);

  async function handleSubmit(
    event: FormEvent
  ) {
    event.preventDefault();

    setLoading(true);
    setError(null);

    const { error } =
      await supabase.auth.signInWithPassword({
        email,
        password,
      });

    setLoading(false);

    if (error) {
      setError(error.message);
      return;
    }

    router.push("/cart");
  }

  return (
    <main className="min-h-screen bg-neutral-950 text-white flex items-center justify-center p-6">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-md rounded-2xl border border-neutral-800 bg-neutral-900 p-8"
      >
        <h1 className="text-3xl font-semibold">
          Retailigent
        </h1>

        <p className="mt-2 text-neutral-400">
          Sign in to your account
        </p>

        <label className="mt-8 block text-sm">
          Email
        </label>

        <input
          type="email"
          value={email}
          onChange={(event) =>
            setEmail(event.target.value)
          }
          required
          className="mt-2 w-full rounded-lg border border-neutral-700 bg-neutral-950 p-3"
        />

        <label className="mt-5 block text-sm">
          Password
        </label>

        <input
          type="password"
          value={password}
          onChange={(event) =>
            setPassword(event.target.value)
          }
          required
          className="mt-2 w-full rounded-lg border border-neutral-700 bg-neutral-950 p-3"
        />

        {error && (
          <p className="mt-4 text-sm text-red-400">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={loading}
          className="mt-6 w-full rounded-lg bg-white p-3 font-medium text-black disabled:opacity-50"
        >
          {loading
            ? "Signing in..."
            : "Sign in"}
        </button>
      </form>
    </main>
  );
}