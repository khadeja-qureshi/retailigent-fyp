import type {
  CartResponse,
  WishlistResponse,
  Reservation,
  SmartCartRule,
  RetailAlert,
  NotificationListResponse,
} from "@/lib/api";


export type ChatLanguage =
  | "english"
  | "roman_urdu"
  | "mixed";


export interface ProductCardData {
  product_id: string;
  variant_id: string;

  name: string;
  sku: string;

  brand?: string | null;
  material?: string | null;
  color?: string | null;
  size?: string | null;

  effective_price?:
    | number
    | null;

  image_url?:
    | string
    | null;

  max_available_at_one_branch?:
    | number
    | null;
}


export interface ProductCarouselBlock {
  type:
    "product_carousel";

  title: string;

  products:
    ProductCardData[];
}


export interface RecommendationChatBlock {
  type: "recommendation";
  title: string;
  products: ProductCardData[];
}


export interface BranchLocationData {
  branch_id: string;
  name: string;
  city: string;
  area?: string | null;
  address?: string | null;
  latitude?: number | null;
longitude?: number | null;
distance_km?: number | null;
phone?: string | null;
  opening_time?: string | null;
  closing_time?: string | null;
}


export interface BranchMapChatBlock {
  type: "branch_map";
  title: string;
  branches: BranchLocationData[];
}


export interface StockBranchItem {
  branch_id: string;

  branch_name: string;

  city?:
    | string
    | null;

  area?:
    | string
    | null;

  address?:
    | string
    | null;

  available_quantity:
    number;

  status:
    | "out_of_stock"
    | "low_stock"
    | "available";
}


export interface StockStatusBlock {
  type:
    "stock_status";

  variant_id: string;

  product_name?:
    | string
    | null;

  sku?:
    | string
    | null;

  branches:
    StockBranchItem[];
}


export interface CartSummaryChatBlock {
  type:
    "cart_summary";

  data:
    CartResponse;
}


export interface WishlistChatBlock {
  type:
    "wishlist";

  data:
    WishlistResponse;
}


export interface ReservationChatBlock {
  type:
    "reservation";

  reservation:
    Reservation;
}


export interface SmartCartRuleChatBlock {
  type:
    "smart_cart_rule";

  rule:
    SmartCartRule;
}


export interface AlertChatBlock {
  type:
    "alert";

  alert:
    RetailAlert;
}


export interface ChatOrderPayload {
  success?: boolean;

  order_id?:
    | string
    | null;

  purchase_attempt_id?:
    | string
    | null;

  reason_code?:
    | string
    | null;

  reason?:
    | string
    | null;

  variant_id?: string;

  quantity?: number;
}


export interface OrderConfirmationChatBlock {
  type:
    "order_confirmation";

  order:
    ChatOrderPayload;
}


export interface SupportEscalationChatBlock {
  type: "support_escalation";
  ticket_id: string;
  status:
    | "open"
    | "in_progress"
    | "waiting_customer"
    | "escalated"
    | "resolved"
    | "closed";
  subject: string;
  message: string;
}

export interface NotificationListChatBlock {
  type:
    "notification_list";

  data:
    NotificationListResponse;
}


export type RenderableBlock =
  | ProductCarouselBlock
  | RecommendationChatBlock
  | BranchMapChatBlock
  | StockStatusBlock
  | CartSummaryChatBlock
  | WishlistChatBlock
  | ReservationChatBlock
  | SmartCartRuleChatBlock
  | AlertChatBlock
  | OrderConfirmationChatBlock
  | NotificationListChatBlock
  | SupportEscalationChatBlock;


export interface ChatMessage {
  id: string;

  role:
    | "user"
    | "assistant";

  content: string;

  language?:
    ChatLanguage;

  blocks:
    RenderableBlock[];

  isStreaming?:
    boolean;

  created_at?:
    | string
    | null;
}


export interface ConversationSummary {
  id: string;

  title?:
    | string
    | null;

  language:
    ChatLanguage;

  created_at?:
    | string
    | null;

  updated_at?:
    | string
    | null;
}


export interface ConversationListResponse {
  conversations:
    ConversationSummary[];
}


export interface ConversationHistoryResponse {
  conversation:
    ConversationSummary;

  messages:
    ChatMessage[];
}


export interface ChatStreamEvent {
  event: string;

  data: unknown;
}


export interface ConversationEventData {
  conversation_id: string;
}


export interface MessageStartEventData {
  message_id: string;

  role:
    "assistant";

  language:
    ChatLanguage;
}


export interface MessageDeltaEventData {
  message_id: string;

  delta: string;
}


export interface BlockEventData {
  message_id: string;

  block:
    RenderableBlock;
}


export interface DoneEventData {
  conversation_id: string;

  message_id: string;

  language:
    ChatLanguage;

  block_count: number;
}


export interface ErrorEventData {
  message: string;
}
