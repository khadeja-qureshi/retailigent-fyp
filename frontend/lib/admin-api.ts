import {
  supabase,
} from "@/lib/supabase/client";


const API_URL = (
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000"
).replace(
  /\/+$/,
  ""
);


export async function adminRequest<T>(
  path: string
): Promise<T> {
  const {
    data: {
      session,
    },
  } =
    await supabase.auth
      .getSession();


  if (
    !session?.access_token
  ) {
    throw new Error(
      "Sign in with an authorized staff account."
    );
  }


  const controller =
    new AbortController();


  const timeout =
    window.setTimeout(
      () => {
        controller.abort();
      },
      15000
    );


  try {
    const response =
      await fetch(
        `${API_URL}${path}`,
        {
          method:
            "GET",

          headers: {
            Authorization:
              `Bearer ${session.access_token}`,
          },

          cache:
            "no-store",

          signal:
            controller.signal,
        }
      );


    const payload =
      await response
        .json()
        .catch(
          () => null
        );


    if (
      !response.ok
    ) {
      const detail =
        (
          payload
          &&
          typeof payload.detail
            === "string"
        )
          ? payload.detail
          : (
            `Request failed (${response.status}).`
          );


      throw new Error(
        detail
      );
    }


    return payload as T;

  } catch (error) {
    if (
      error
      instanceof DOMException
      &&
      error.name
      === "AbortError"
    ) {
      throw new Error(
        "The backend took too long to respond."
      );
    }


    if (
      error
      instanceof TypeError
      &&
      error.message
        .toLowerCase()
        .includes(
          "fetch"
        )
    ) {
      throw new Error(
        "Could not reach the Retailigent backend. Make sure FastAPI is running on http://127.0.0.1:8000."
      );
    }


    throw error;

  } finally {
    window.clearTimeout(
      timeout
    );
  }
}


export function formatDate(
  value?:
    | string
    | null
): string {
  if (!value) {
    return "—";
  }


  const date =
    new Date(
      value
    );


  if (
    Number.isNaN(
      date.getTime()
    )
  ) {
    return "—";
  }


  return date
    .toLocaleString();
}


export function formatMoney(
  value?:
    | number
    | string
    | null,

  currency =
    "PKR"
): string {
  const amount =
    Number(
      value
      ?? 0
    );


  if (
    !Number.isFinite(
      amount
    )
  ) {
    return "—";
  }


  return (
    new Intl.NumberFormat(
      undefined,
      {
        style:
          "currency",

        currency,

        maximumFractionDigits:
          2,
      }
    )
    .format(
      amount
    )
  );
}