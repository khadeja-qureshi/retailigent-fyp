"use client";

import {
  useState,
} from "react";

import AlertBlock from "@/components/chat-blocks/AlertBlock";
import CartSummaryBlock from "@/components/chat-blocks/CartSummaryBlock";
import NotificationListBlock from "@/components/chat-blocks/NotificationListBlock";
import ProductCarouselBlock from "@/components/chat-blocks/ProductCarouselBlock";
import RecommendationBlock from "@/components/chat-blocks/RecommendationBlock";
import BranchMapBlock from "@/components/chat-blocks/BranchMapBlock";
import ReservationBlock from "@/components/chat-blocks/ReservationBlock";
import SmartCartRuleBlock from "@/components/chat-blocks/SmartCartRuleBlock";
import StockStatusBlock from "@/components/chat-blocks/StockStatusBlock";
import SupportEscalationBlock from "@/components/chat-blocks/SupportEscalationBlock";
import WishlistBlock from "@/components/chat-blocks/WishlistBlock";

import {
  cancelSmartCartRule,
  deleteAlert,
  markNotificationsRead,
  pauseAlert,
  pauseSmartCartRule,
  releaseReservation,
  removeCartItem,
  removeWishlistItem,
  resumeAlert,
  resumeSmartCartRule,
  updateCartItem,
} from "@/lib/api";

import type {
  AlertChatBlock,
  CartSummaryChatBlock,
  ChatOrderPayload,
  NotificationListChatBlock,
  RenderableBlock,
  ReservationChatBlock,
  SmartCartRuleChatBlock,
  WishlistChatBlock,
} from "@/lib/chat-types";


interface Props {
  block: RenderableBlock;
}


function ActionError({
  message,
}: {
  message: string | null;
}) {
  if (!message) {
    return null;
  }

  return (
    <p className="mt-2 rounded-lg border border-red-900 bg-red-950/30 px-3 py-2 text-sm text-red-300">
      {message}
    </p>
  );
}


function CartBlockAdapter({
  block,
}: {
  block: CartSummaryChatBlock;
}) {
  const [
    data,
    setData,
  ] = useState(block.data);

  const [
    busyItemId,
    setBusyItemId,
  ] = useState<string | null>(
    null
  );

  const [
    error,
    setError,
  ] = useState<string | null>(
    null
  );


  async function handleQuantityChange(
    itemId: string,
    quantity: number
  ) {
    if (busyItemId) {
      return;
    }

    setBusyItemId(itemId);
    setError(null);

    try {
      if (quantity <= 0) {
        await removeCartItem(
          itemId
        );

        setData(
          (current) => ({
            ...current,

            items:
              current.items.filter(
                (item) =>
                  item.id !==
                  itemId
              ),

            item_count:
              Math.max(
                0,
                current.item_count - 1
              ),
          })
        );

        return;
      }

      const updated =
        await updateCartItem(
          itemId,
          quantity
        );

      setData(updated);

    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Could not update cart."
      );

    } finally {
      setBusyItemId(null);
    }
  }


  async function handleRemove(
    itemId: string
  ) {
    if (busyItemId) {
      return;
    }

    setBusyItemId(itemId);
    setError(null);

    try {
      await removeCartItem(
        itemId
      );

      setData(
        (current) => ({
          ...current,

          items:
            current.items.filter(
              (item) =>
                item.id !==
                itemId
            ),

          item_count:
            Math.max(
              0,
              current.item_count - 1
            ),
        })
      );

    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Could not remove item."
      );

    } finally {
      setBusyItemId(null);
    }
  }


  return (
    <>
      <CartSummaryBlock
        data={data}
        busyItemId={busyItemId}
        onQuantityChange={
          handleQuantityChange
        }
        onRemove={
          handleRemove
        }
      />

      <ActionError
        message={error}
      />
    </>
  );
}


function WishlistBlockAdapter({
  block,
}: {
  block: WishlistChatBlock;
}) {
  const [
    data,
    setData,
  ] = useState(block.data);

  const [
    busyItemId,
    setBusyItemId,
  ] = useState<string | null>(
    null
  );

  const [
    error,
    setError,
  ] = useState<string | null>(
    null
  );


  async function handleRemove(
    itemId: string
  ) {
    setBusyItemId(itemId);
    setError(null);

    try {
      await removeWishlistItem(
        itemId
      );

      setData(
        (current) => ({
          ...current,

          items:
            current.items.filter(
              (item) =>
                item.id !==
                itemId
            ),

          count:
            Math.max(
              0,
              current.count - 1
            ),
        })
      );

    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : (
            "Could not remove "
            + "wishlist item."
          )
      );

    } finally {
      setBusyItemId(null);
    }
  }


  return (
    <>
      <WishlistBlock
        data={data}
        busyItemId={busyItemId}
        onRemove={handleRemove}
      />

      <ActionError
        message={error}
      />
    </>
  );
}


function ReservationBlockAdapter({
  block,
}: {
  block: ReservationChatBlock;
}) {
  const [
    reservation,
    setReservation,
  ] = useState(
    block.reservation
  );

  const [
    busy,
    setBusy,
  ] = useState(false);

  const [
    error,
    setError,
  ] = useState<string | null>(
    null
  );


  async function handleRelease(
    id: string
  ) {
    setBusy(true);
    setError(null);

    try {
      await releaseReservation(
        id
      );

      setReservation(
        (current) => ({
          ...current,

          status:
            "released",

          released_at:
            new Date()
              .toISOString(),
        })
      );

    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : (
            "Could not release "
            + "reservation."
          )
      );

    } finally {
      setBusy(false);
    }
  }


  return (
    <>
      <ReservationBlock
        reservation={reservation}
        busy={busy}
        onRelease={
          handleRelease
        }
      />

      <ActionError
        message={error}
      />
    </>
  );
}


function SmartCartBlockAdapter({
  block,
}: {
  block: SmartCartRuleChatBlock;
}) {
  const [
    rule,
    setRule,
  ] = useState(block.rule);

  const [
    busy,
    setBusy,
  ] = useState(false);

  const [
    error,
    setError,
  ] = useState<string | null>(
    null
  );


  async function perform(
    action: () =>
      Promise<typeof rule>
  ) {
    setBusy(true);
    setError(null);

    try {
      const updated =
        await action();

      setRule(updated);

    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : (
            "Could not update "
            + "Smart Cart rule."
          )
      );

    } finally {
      setBusy(false);
    }
  }


  return (
    <>
      <SmartCartRuleBlock
        rule={rule}
        busy={busy}

        onPause={(id) => {
          void perform(
            () =>
              pauseSmartCartRule(
                id
              )
          );
        }}

        onResume={(id) => {
          void perform(
            () =>
              resumeSmartCartRule(
                id
              )
          );
        }}

        onCancel={(id) => {
          void perform(
            () =>
              cancelSmartCartRule(
                id
              )
          );
        }}
      />

      <ActionError
        message={error}
      />
    </>
  );
}


function AlertBlockAdapter({
  block,
}: {
  block: AlertChatBlock;
}) {
  const [
    alert,
    setAlert,
  ] = useState(
    block.alert
  );

  const [
    deleted,
    setDeleted,
  ] = useState(false);

  const [
    busy,
    setBusy,
  ] = useState(false);

  const [
    error,
    setError,
  ] = useState<string | null>(
    null
  );


  async function handlePause(
    id: string
  ) {
    setBusy(true);
    setError(null);

    try {
      setAlert(
        await pauseAlert(id)
      );

    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Could not pause alert."
      );

    } finally {
      setBusy(false);
    }
  }


  async function handleResume(
    id: string
  ) {
    setBusy(true);
    setError(null);

    try {
      setAlert(
        await resumeAlert(id)
      );

    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Could not resume alert."
      );

    } finally {
      setBusy(false);
    }
  }


  async function handleDelete(
    id: string
  ) {
    setBusy(true);
    setError(null);

    try {
      await deleteAlert(id);

      setDeleted(true);

    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Could not delete alert."
      );

    } finally {
      setBusy(false);
    }
  }


  if (deleted) {
    return (
      <div className="rounded-xl border border-neutral-800 bg-neutral-900 p-4 text-sm text-neutral-400">
        Alert deleted.
      </div>
    );
  }


  return (
    <>
      <AlertBlock
        alert={alert}
        busy={busy}
        onPause={
          handlePause
        }
        onResume={
          handleResume
        }
        onDelete={
          handleDelete
        }
      />

      <ActionError
        message={error}
      />
    </>
  );
}


function NotificationBlockAdapter({
  block,
}: {
  block:
    NotificationListChatBlock;
}) {
  const [
    data,
    setData,
  ] = useState(
    block.data
  );

  const [
    busy,
    setBusy,
  ] = useState(false);

  const [
    error,
    setError,
  ] = useState<string | null>(
    null
  );


  async function handleMarkRead(
    id: string
  ) {
    setBusy(true);
    setError(null);

    try {
      const result =
        await markNotificationsRead(
          [id]
        );

      const now =
        new Date()
          .toISOString();

      setData(
        (current) => ({
          ...current,

          unread_count:
            result.unread_count,

          notifications:
            current.notifications.map(
              (item) =>
                item.id === id
                  ? {
                      ...item,
                      read_at:
                        item.read_at ??
                        now,
                    }
                  : item
            ),
        })
      );

    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : (
            "Could not mark "
            + "notification read."
          )
      );

    } finally {
      setBusy(false);
    }
  }


  async function handleMarkAllRead() {
    setBusy(true);
    setError(null);

    try {
      const result =
        await markNotificationsRead();

      const now =
        new Date()
          .toISOString();

      setData(
        (current) => ({
          ...current,

          unread_count:
            result.unread_count,

          notifications:
            current.notifications.map(
              (item) => ({
                ...item,
                read_at:
                  item.read_at ??
                  now,
              })
            ),
        })
      );

    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : (
            "Could not mark "
            + "notifications read."
          )
      );

    } finally {
      setBusy(false);
    }
  }


  return (
    <>
      <NotificationListBlock
        notifications={
          data.notifications
        }
        unreadCount={
          data.unread_count
        }
        busy={busy}

        onMarkRead={(id) => {
          void handleMarkRead(id);
        }}

        onMarkAllRead={() => {
          void handleMarkAllRead();
        }}
      />

      <ActionError
        message={error}
      />
    </>
  );
}


function ChatOrderConfirmation({
  order,
}: {
  order: ChatOrderPayload;
}) {
  return (
    <section className="rounded-2xl border border-green-900 bg-green-950/20 p-5">
      <p className="text-xs uppercase tracking-wide text-green-400">
        Purchase successful
      </p>

      <h3 className="mt-2 text-lg font-semibold">
        Order confirmed
      </h3>

      {order.order_id && (
        <p className="mt-3 text-sm text-neutral-300">
          Order ID:{" "}
          <strong>
            {order.order_id}
          </strong>
        </p>
      )}

      {order.variant_id && (
        <p className="mt-2 text-sm text-neutral-400">
          Variant:{" "}
          {order.variant_id}
        </p>
      )}

      {order.quantity != null && (
        <p className="mt-2 text-sm text-neutral-400">
          Quantity:{" "}
          {order.quantity}
        </p>
      )}

      <p className="mt-4 text-xs text-neutral-500">
        Purchase completed through the
        Retailigent mock purchase system.
      </p>
    </section>
  );
}


export default function BlockRenderer({
  block,
}: Props) {
  switch (block.type) {
    case "product_carousel":
      return (
        <ProductCarouselBlock
          block={block}
        />
      );

    case "recommendation":
      return (
        <RecommendationBlock block={block} />
      );

    case "branch_map":
      return (
        <BranchMapBlock block={block} />
      );

    case "stock_status":
      return (
        <StockStatusBlock
          block={block}
        />
      );

    case "cart_summary":
      return (
        <CartBlockAdapter
          block={block}
        />
      );

    case "wishlist":
      return (
        <WishlistBlockAdapter
          block={block}
        />
      );

    case "reservation":
      return (
        <ReservationBlockAdapter
          block={block}
        />
      );

    case "smart_cart_rule":
      return (
        <SmartCartBlockAdapter
          block={block}
        />
      );

    case "alert":
      return (
        <AlertBlockAdapter
          block={block}
        />
      );

    case "notification_list":
      return (
        <NotificationBlockAdapter
          block={block}
        />
      );

    case "support_escalation":
      return (
        <SupportEscalationBlock
          block={block}
        />
      );
    case "order_confirmation":
      return (
        <ChatOrderConfirmation
          order={block.order}
        />
      );

    default:
      return null;
  }
}
