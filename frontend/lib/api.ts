import { supabase } from "@/lib/supabase/client";


const API_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000";


const API_TIMEOUT_MS = 15000;


// ---------------------------------------------------------------------------
// Shared product / pricing types
// ---------------------------------------------------------------------------

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


// ---------------------------------------------------------------------------
// Cart
// ---------------------------------------------------------------------------

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


// ---------------------------------------------------------------------------
// Wishlist
// ---------------------------------------------------------------------------

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


// ---------------------------------------------------------------------------
// Shared authenticated API request helper
// ---------------------------------------------------------------------------

async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {

  const {
    data: {
      session,
    },
  } =
    await supabase.auth
      .getSession();


  if (!session?.access_token) {
    throw new Error(
      "You must sign in before using this feature."
    );
  }


  const controller =
    new AbortController();


  const timeout =
    window.setTimeout(
      () => {
        controller.abort();
      },
      API_TIMEOUT_MS
    );


  try {
    const response =
      await fetch(
        `${API_URL}${path}`,
        {
          ...options,

          signal:
            controller.signal,

          cache:
            "no-store",

          headers: {
            "Content-Type":
              "application/json",

            Authorization:
              `Bearer ${session.access_token}`,

            ...(
              options.headers ??
              {}
            ),
          },
        }
      );


    if (
      response.status === 204
    ) {
      return undefined as T;
    }


    const contentType =
      response.headers.get(
        "content-type"
      ) ?? "";


    const payload =
      contentType.includes(
        "application/json"
      )
        ? await response.json()
        : await response.text();


    if (!response.ok) {

      let message =
        "API request failed";


      if (
        typeof payload === "string"
        &&
        payload.trim()
      ) {
        message =
          payload;
      }


      if (
        payload
        &&
        typeof payload === "object"
        &&
        "detail" in payload
      ) {
        const detail =
          (
            payload as {
              detail?: unknown;
            }
          ).detail;


        if (
          typeof detail === "string"
        ) {
          message =
            detail;
        }
        else if (
          detail !== undefined
        ) {
          message =
            JSON.stringify(
              detail
            );
        }
      }


      throw new Error(
        message
      );
    }


    return payload as T;

  } catch (caught) {

    if (
      caught instanceof DOMException
      &&
      caught.name === "AbortError"
    ) {
      throw new Error(
        "The server took too long to respond. Check that the Retailigent backend is running and try again."
      );
    }


    if (
      caught instanceof TypeError
    ) {
      throw new Error(
        "Could not connect to the Retailigent backend. Check that FastAPI is running on port 8000."
      );
    }


    throw caught;

  } finally {
    window.clearTimeout(
      timeout
    );
  }
}


// ---------------------------------------------------------------------------
// Cart API
// ---------------------------------------------------------------------------

export function getCart() {
  return apiFetch<CartResponse>(
    "/api/v1/cart"
  );
}


export function addCartItem(
  variantId: string,
  quantity: number
) {
  return apiFetch<CartResponse>(
    "/api/v1/cart/items",
    {
      method: "POST",

      body:
        JSON.stringify({
          variant_id:
            variantId,

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

      body:
        JSON.stringify({
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


// ---------------------------------------------------------------------------
// Wishlist API
// ---------------------------------------------------------------------------

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

      body:
        JSON.stringify({
          variant_id:
            variantId,
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


// ---------------------------------------------------------------------------
// Reservations
// ---------------------------------------------------------------------------

export interface ReservationBranch {
  id: string;
  name: string;
  city?: string | null;
  area?: string | null;
  address?: string | null;
}


export interface Reservation {
  id: string;

  customer_id: string;

  variant_id: string;

  branch_id: string;

  quantity: number;

  status:
    | "active"
    | "released"
    | "expired"
    | "cancelled"
    | "converted";

  expires_at: string;

  released_at?: string | null;

  created_at: string;

  product?: Product | null;

  variant?: Variant | null;

  branch?: ReservationBranch | null;
}


export interface ReservationListResponse {
  items: Reservation[];
  count: number;
}


export function getReservations() {
  return apiFetch<ReservationListResponse>(
    "/api/v1/reservations"
  );
}


export function createReservation(
  variantId: string,
  branchId: string,
  quantity: number,
  holdMinutes = 15
) {
  return apiFetch<Reservation>(
    "/api/v1/reservations",
    {
      method: "POST",

      body:
        JSON.stringify({
          variant_id:
            variantId,

          branch_id:
            branchId,

          quantity,

          hold_minutes:
            holdMinutes,
        }),
    }
  );
}


export function releaseReservation(
  reservationId: string
) {
  return apiFetch<{
    released: boolean;
    reservation_id: string;
  }>(
    `/api/v1/reservations/${reservationId}`,
    {
      method: "DELETE",
    }
  );
}


// ---------------------------------------------------------------------------
// Inventory
// ---------------------------------------------------------------------------

export interface InventoryBranch {
  id: string;
  name: string;

  city?: string | null;

  area?: string | null;

  address?: string | null;
}


export interface VariantInventoryRow {
  id: string;

  branch_id: string;

  variant_id: string;

  on_hand_quantity: number;

  reserved_quantity: number;

  safety_stock: number;

  available_quantity: number;

  status?: string;

  branch?: InventoryBranch | null;
}


export interface VariantInventoryResponse {
  variant_id: string;

  inventory: VariantInventoryRow[];

  count: number;
}


export function getVariantInventory(
  variantId: string
) {
  return apiFetch<VariantInventoryResponse>(
    `/api/v1/inventory/variant/${variantId}`
  );
}


// ---------------------------------------------------------------------------
// Orders
// ---------------------------------------------------------------------------

export interface OrderItem {
  variant_id: string;

  quantity: number;

  unit_price: number;

  line_total: number;

  product_snapshot: {
    product_name?: string;

    variant_sku?: string;

    price?: number;

    [key: string]:
      unknown;
  };
}


export interface Order {
  id: string;

  branch_id?: string | null;

  status: string;

  subtotal: number;

  discount: number;

  total: number;

  currency: string;

  source: string;

  created_at: string;

  items: OrderItem[];
}


export function getOrders() {
  return apiFetch<Order[]>(
    "/api/v1/orders"
  );
}


// ---------------------------------------------------------------------------
// Smart Cart
// ---------------------------------------------------------------------------

export type SmartCartAuthorization =
  | "notify_only"
  | "auto_buy";


export type SmartCartStatus =
  | "active"
  | "triggered"
  | "paused"
  | "completed"
  | "cancelled";


export interface SmartCartRule {
  id: string;

  customer_id: string;

  variant_id: string;

  branch_id?: string | null;

  quantity: number;

  target_price?: number | null;

  min_discount_percentage?: number | null;

  authorization_mode:
    SmartCartAuthorization;

  status:
    SmartCartStatus;

  triggered_at?: string | null;

  last_evaluated_at?: string | null;

  created_at: string;

  updated_at: string;

  effective_price?: number | null;

  product?: Product | null;

  variant?: Variant | null;

  branch?: {
    id: string;

    name: string;

    city?: string | null;

    area?: string | null;

    address?: string | null;
  } | null;
}


export interface SmartCartRuleListResponse {
  items: SmartCartRule[];

  count: number;
}


export function getSmartCartRules() {
  return apiFetch<SmartCartRuleListResponse>(
    "/api/v1/smart-cart"
  );
}


export function createSmartCartRule(
  payload: {
    variant_id: string;

    branch_id?: string | null;

    quantity: number;

    target_price?: number | null;

    min_discount_percentage?: number | null;

    authorization_mode:
      SmartCartAuthorization;
  }
) {
  return apiFetch<SmartCartRule>(
    "/api/v1/smart-cart",
    {
      method: "POST",

      body:
        JSON.stringify(
          payload
        ),
    }
  );
}


export function pauseSmartCartRule(
  ruleId: string
) {
  return apiFetch<SmartCartRule>(
    `/api/v1/smart-cart/${ruleId}/pause`,
    {
      method: "POST",
    }
  );
}


export function resumeSmartCartRule(
  ruleId: string
) {
  return apiFetch<SmartCartRule>(
    `/api/v1/smart-cart/${ruleId}/resume`,
    {
      method: "POST",
    }
  );
}


export function cancelSmartCartRule(
  ruleId: string
) {
  return apiFetch<SmartCartRule>(
    `/api/v1/smart-cart/${ruleId}/cancel`,
    {
      method: "POST",
    }
  );
}


// ---------------------------------------------------------------------------
// Alerts
// ---------------------------------------------------------------------------

export type AlertType =
  | "price_drop"
  | "restock"
  | "sale";


export interface RetailAlert {
  id: string;

  customer_id: string;

  variant_id: string;

  alert_type:
    AlertType;

  target_price?: number | null;

  is_active: boolean;

  created_at: string;

  triggered_at?: string | null;

  effective_price?: number | null;

  product?: Product | null;

  variant?: Variant | null;
}


export interface AlertListResponse {
  items: RetailAlert[];

  count: number;
}


export function getAlerts() {
  return apiFetch<AlertListResponse>(
    "/api/v1/alerts"
  );
}


export function createAlert(
  payload: {
    variant_id: string;

    alert_type:
      AlertType;

    target_price?: number | null;
  }
) {
  return apiFetch<RetailAlert>(
    "/api/v1/alerts",
    {
      method: "POST",

      body:
        JSON.stringify(
          payload
        ),
    }
  );
}


export function pauseAlert(
  alertId: string
) {
  return apiFetch<RetailAlert>(
    `/api/v1/alerts/${alertId}/pause`,
    {
      method: "POST",
    }
  );
}


export function resumeAlert(
  alertId: string
) {
  return apiFetch<RetailAlert>(
    `/api/v1/alerts/${alertId}/resume`,
    {
      method: "POST",
    }
  );
}


export function deleteAlert(
  alertId: string
) {
  return apiFetch<{
    deleted: boolean;

    alert_id: string;
  }>(
    `/api/v1/alerts/${alertId}`,
    {
      method: "DELETE",
    }
  );
}


// ---------------------------------------------------------------------------
// Notifications (Phase 10)
// ---------------------------------------------------------------------------

export interface AppNotification {
  id: string;

  type: string;

  title: string;

  message: string;

  metadata:
    Record<string, unknown>;

  read_at:
    string | null;

  created_at: string;
}


export interface NotificationListResponse {
  type:
    "notification_list";

  notifications:
    AppNotification[];

  unread_count:
    number;
}


export function getNotifications(
  unreadOnly = false
) {
  return apiFetch<NotificationListResponse>(
    `/api/v1/notifications?unread_only=${unreadOnly}`
  );
}


export function getUnreadNotificationCount() {
  return apiFetch<{
    unread_count: number;
  }>(
    "/api/v1/notifications/unread-count"
  );
}


export function markNotificationsRead(
  notificationIds?: string[]
) {
  return apiFetch<{
    updated: number;

    unread_count: number;
  }>(
    "/api/v1/notifications/read",
    {
      method: "POST",

      body:
        JSON.stringify({
          notification_ids:
            notificationIds ??
            null,
        }),
    }
  );
}