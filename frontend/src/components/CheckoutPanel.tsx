import { useEffect, useRef, useState } from "react";
import { createPayuCheckout, fetchOrder } from "../api";
import type { PayuCheckout } from "../types";

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

interface CheckoutOrder {
  id: string;
  pickup_token: string;
  total: number;
  status: string;
}

interface CheckoutPanelProps {
  order: CheckoutOrder;
  onStatusChange: (status: string) => void;
}

// Shown once the voice agent has confirmed the order and created it on the backend
// (order_update/order_created). Payment is UPI-only: PayU's hosted checkout, restricted to the
// UPI payment method, is opened in a new tab so the voice call in this tab keeps running while
// the customer scans the QR with any UPI app. This panel polls order status itself (independent
// of the agent's own polling) purely to update the on-screen status live.
export function CheckoutPanel({ order, onStatusChange }: CheckoutPanelProps) {
  const [checkout, setCheckout] = useState<PayuCheckout | null>(null);
  const [checkoutError, setCheckoutError] = useState<string | null>(null);
  const formRef = useRef<HTMLFormElement>(null);

  useEffect(() => {
    if (order.status !== "pending_payment") return;
    setCheckout(null);
    setCheckoutError(null);
    createPayuCheckout(order.id)
      .then(setCheckout)
      .catch((err) => setCheckoutError(errorMessage(err)));
  }, [order.id, order.status]);

  useEffect(() => {
    if (order.status !== "pending_payment") return;
    const interval = setInterval(() => {
      fetchOrder(order.id)
        .then((fresh) => onStatusChange(fresh.status))
        .catch(() => {
          // transient network hiccup — the agent's own polling still drives the call, this is
          // just the on-screen status mirror, so silently retry next tick
        });
    }, 2000);
    return () => clearInterval(interval);
  }, [order.id, order.status, onStatusChange]);

  return (
    <div className="panel checkout-panel">
      <h2>Checkout</h2>
      <p className="checkout-total">Total: ₹{order.total.toFixed(2)}</p>

      {order.status === "pending_payment" && (
        <>
          <p className="muted-text">
            Pay with any UPI app — tap below to open PayU's payment page in a new tab and scan
            the QR code there.
          </p>
          {checkoutError && <p className="error-text">{checkoutError}</p>}
          {checkout && (
            <form ref={formRef} action={checkout.action_url} method="POST" target="_blank">
              {Object.entries(checkout.fields).map(([name, value]) => (
                <input key={name} type="hidden" name={name} value={value} />
              ))}
              <button type="submit" className="checkout-pay-btn">
                Pay ₹{order.total.toFixed(2)} via UPI
              </button>
            </form>
          )}
          <p className="muted-text checkout-waiting">Waiting for payment confirmation…</p>
        </>
      )}

      {order.status === "paid" && (
        <p className="checkout-success">
          Payment received! Your pickup code is <strong>{order.pickup_token}</strong> — listen
          for it at the counter.
        </p>
      )}

      {order.status === "payment_failed" && (
        <p className="checkout-failure">
          Payment didn't go through. Please pay at the counter with the staff instead.
        </p>
      )}
    </div>
  );
}
