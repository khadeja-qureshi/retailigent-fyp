import { supabase } from "@/lib/supabase/client";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000";


export interface AvailabilityHint {
  max_available_at_one_branch: number;
  has_stock: boolean;
}

export interface Pricing {
  base_price: number;
  effective_price: number;
  discount_amount: number;
}

export interface Product {
  id: string;
  name: string;
  sku: string;
  brand?: string | null;
}

export interface Variant {
  id: string;
  sku: string;
  product_id: string;
}

export interface CartItem {
  id: string;
  cart_id: string;
  variant_id: string;
  quantity: number;
  product?: Product;
  variant?: Variant;
  pricing?: Pricing;
  availability_hint?: AvailabilityHint;
}

export interface CartResponse {
  cart: {
    id: string;
    customer_id: string;
    status: string;
  } | null;
  items: CartItem[];
  item_count: number;
}

export interface WishlistItem {
  id: string;
  customer_id: string;
  variant_id: string;
  product?: Product;
  variant?: Variant;
  pricing?: Pricing;
  availability_hint?: AvailabilityHint;
}

export interface WishlistResponse {
  items: WishlistItem[];
  count: number;
}


async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.access_token) {
    throw new Error(
      "You must sign in before using this feature."
    );
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization:
        `Bearer ${session.access_token}`,
      ...(options.headers ?? {}),
    },
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType =
    response.headers.get("content-type") ?? "";

  const payload = contentType.includes(
    "application/json"
  )
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const message =
      typeof payload === "string"
        ? payload
        : payload?.detail ??
          "API request failed";

    throw new Error(message);
  }

  return payload as T;
}


export function getCart() {
  return apiFetch<CartResponse>("/api/v1/cart");
}

export function addCartItem(
  variantId: string,
  quantity: number
) {
  return apiFetch<CartResponse>(
    "/api/v1/cart/items",
    {
      method: "POST",
      body: JSON.stringify({
        variant_id: variantId,
        quantity,
      }),
    }
  );
}

export function updateCartItem(
  itemId: string,
  quantity: number
) {
  return apiFetch<CartResponse>(
    `/api/v1/cart/items/${itemId}`,
    {
      method: "PATCH",
      body: JSON.stringify({
        quantity,
      }),
    }
  );
}

export function removeCartItem(
  itemId: string
) {
  return apiFetch<void>(
    `/api/v1/cart/items/${itemId}`,
    {
      method: "DELETE",
    }
  );
}


export function getWishlist() {
  return apiFetch<WishlistResponse>(
    "/api/v1/wishlist"
  );
}

export function addWishlistItem(
  variantId: string
) {
  return apiFetch<WishlistResponse>(
    "/api/v1/wishlist",
    {
      method: "POST",
      body: JSON.stringify({
        variant_id: variantId,
      }),
    }
  );
}

export function removeWishlistItem(
  itemId: string
) {
  return apiFetch<void>(
    `/api/v1/wishlist/${itemId}`,
    {
      method: "DELETE",
    }
  );
}