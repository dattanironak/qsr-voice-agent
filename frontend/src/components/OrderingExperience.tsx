import { useCallback, useEffect, useState } from "react";
import { ConnectionState } from "livekit-client";
import { useConnectionState, useDataChannel, useRoomContext, useVoiceAssistant } from "@livekit/components-react";
import type { ReceivedDataMessage } from "@livekit/components-core";
import { CartPanel } from "./CartPanel";
import { CheckoutPanel } from "./CheckoutPanel";
import { Header } from "./Header";
import { MenuPanel } from "./MenuPanel";
import { TranscriptPanel } from "./TranscriptPanel";
import { VoiceControls } from "./VoiceControls";
import { EMPTY_CART } from "../types";
import type { Cart, CartUpdateMessage, Menu, MenuItem, OrderUpdateMessage, SelectedOption } from "../types";

interface OrderingExperienceProps {
  menu: Menu | null;
  menuError: string | null;
  connecting: boolean;
  connectError: string | null;
  hasSession: boolean;
  orderJustEnded: boolean;
  onConnect: () => void;
}

function isCart(value: unknown): value is Cart {
  return !!value && typeof value === "object" && Array.isArray((value as Cart).items);
}

interface CheckoutOrder {
  id: string;
  pickup_token: string;
  total: number;
  status: string;
}

export function OrderingExperience({
  menu,
  menuError,
  connecting,
  connectError,
  hasSession,
  orderJustEnded,
  onConnect,
}: OrderingExperienceProps) {
  const [cart, setCart] = useState<Cart>(EMPTY_CART);
  const [cartError, setCartError] = useState<string | null>(null);
  const [order, setOrder] = useState<CheckoutOrder | null>(null);
  const connectionState = useConnectionState();
  const connected = connectionState === ConnectionState.Connected;

  // The LiveKitRoom tree (and this component) stays mounted across a disconnect, so clear out
  // the previous order's cart/checkout state right as a *new* session starts, rather than as the
  // old one ends — that way the final cart/order stays on screen (for the post-call banner)
  // right up until the customer starts another order.
  useEffect(() => {
    if (hasSession) {
      setCart(EMPTY_CART);
      setCartError(null);
      setOrder(null);
    }
  }, [hasSession]);

  // The agent publishes cart_update after every mutation (voice, tap, or RPC), so this is the
  // single source of truth for cart state regardless of which path changed it.
  const onCartMessage = useCallback((msg: ReceivedDataMessage<"cart_update">) => {
    try {
      const decoded = new TextDecoder().decode(msg.payload);
      const parsed = JSON.parse(decoded) as CartUpdateMessage;
      if (parsed.type === "cart_update") {
        setCart(parsed.cart);
      }
    } catch (err) {
      console.error("Failed to parse cart_update payload", err);
    }
  }, []);
  useDataChannel("cart_update", onCartMessage);

  // The agent publishes order_update once complete_order creates the order (order_created) and
  // again once payment resolves (order_status) — this is what switches the UI from menu/cart
  // browsing into the checkout screen. CheckoutPanel also polls the backend directly for the
  // same status, since the LiveKit data channel and the agent's own polling are best-effort.
  const onOrderMessage = useCallback((msg: ReceivedDataMessage<"order_update">) => {
    try {
      const decoded = new TextDecoder().decode(msg.payload);
      const parsed = JSON.parse(decoded) as OrderUpdateMessage;
      setOrder(parsed.order);
    } catch (err) {
      console.error("Failed to parse order_update payload", err);
    }
  }, []);
  useDataChannel("order_update", onOrderMessage);

  const handleOrderStatusChange = useCallback((status: string) => {
    setOrder((prev) => (prev ? { ...prev, status } : prev));
  }, []);

  // Tap-driven cart edits go straight to the agent over RPC (cart.add/update/remove) instead of
  // a chat message, so they land in ~100-300ms instead of waiting on a full LLM conversational
  // turn — that round trip is what "realtime" add/remove means here. Called directly on the
  // room's local participant rather than the useRpc() hook: that hook expects a SessionContext
  // provider we don't set up (we use the classic LiveKitRoom/RoomContext pattern), and throws
  // "No session provided" at runtime despite type-checking fine.
  const { agent } = useVoiceAssistant();
  const room = useRoomContext();
  const canMutateCart = connected && agent !== undefined;

  async function callCartRpc(method: "cart.add" | "cart.update" | "cart.remove", payload: unknown) {
    if (!agent) return;
    setCartError(null);
    try {
      const response = await room.localParticipant.performRpc({
        destinationIdentity: agent.identity,
        method,
        payload: JSON.stringify(payload),
      });
      const parsed = JSON.parse(response) as Cart | { error: string };
      if (isCart(parsed)) {
        setCart(parsed);
      } else {
        setCartError(parsed.error);
      }
    } catch (err) {
      console.error(`Cart RPC ${method} failed`, err);
      setCartError("Couldn't reach the assistant — try again.");
    }
  }

  async function handleAddToOrder(item: MenuItem, quantity: number, selections: SelectedOption[]) {
    await callCartRpc("cart.add", {
      item_name: item.name,
      quantity,
      customizations: selections.map((s) => ({ group_name: s.groupName, option_name: s.optionName })),
    });
  }

  async function handleChangeQuantity(lineId: number, quantity: number) {
    if (quantity < 1) {
      await callCartRpc("cart.remove", { line_id: lineId });
      return;
    }
    await callCartRpc("cart.update", { line_id: lineId, quantity });
  }

  async function handleRemoveLine(lineId: number) {
    await callCartRpc("cart.remove", { line_id: lineId });
  }

  return (
    <div className="app-layout">
      <Header
        connected={connected}
        connecting={connecting}
        error={connectError}
        hasSession={hasSession}
        onConnect={onConnect}
      />
      {orderJustEnded && !hasSession && (
        <p className="order-ended-banner">
          {order?.status === "paid"
            ? `Thanks! Payment received — your pickup code is ${order.pickup_token}. Listen for it at the counter.`
            : order?.status === "payment_failed"
              ? "Your order was placed, but payment didn't go through — please pay at the counter with the staff."
              : "Thanks! Your order is placed — collect your receipt and pay at the counter."}{" "}
          Tap "Start voice ordering" above for a new order.
        </p>
      )}
      <main className="layout">
        {order ? (
          <CheckoutPanel order={order} onStatusChange={handleOrderStatusChange} />
        ) : (
          <MenuPanel
            menu={menu}
            menuError={menuError}
            connected={canMutateCart}
            onAddToOrder={handleAddToOrder}
          />
        )}
        <aside className="sidebar">
          <VoiceControls connected={connected} />
          <TranscriptPanel connected={connected} />
          <CartPanel
            cart={cart}
            connected={connected}
            canMutate={canMutateCart && !order}
            error={cartError}
            onChangeQuantity={handleChangeQuantity}
            onRemoveLine={handleRemoveLine}
          />
        </aside>
      </main>
    </div>
  );
}
