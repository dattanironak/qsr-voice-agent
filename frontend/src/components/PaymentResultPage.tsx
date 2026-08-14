import { useEffect, useState } from "react";
import { fetchOrder } from "../api";
import type { Order } from "../types";

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

// Standalone page PayU's redirect (surl/furl, via the backend) lands on after payment, opened in
// its own tab — the voice-ordering tab keeps the call running independently and finds out about
// the outcome itself (order_update data message + its own polling). This page's only job is to
// give the customer a clear receipt/failure message here, then let them close the tab.
export function PaymentResultPage({ orderId }: { orderId: string }) {
  const params = new URLSearchParams(window.location.search);
  const redirectStatus = params.get("status"); // "success" | "failed" — set by the backend redirect

  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (orderId === "unknown") return;
    fetchOrder(orderId)
      .then(setOrder)
      .catch((err) => setError(errorMessage(err)));
  }, [orderId]);

  const paid = order?.status === "paid" || (order === null && redirectStatus === "success");

  return (
    <div className="payment-result-page">
      {orderId === "unknown" ? (
        <>
          <h1>Something went wrong</h1>
          <p className="muted-text">
            We couldn't match this payment to an order. If money was deducted, please show your
            payment confirmation to the staff at the counter.
          </p>
        </>
      ) : error ? (
        <>
          <h1>Couldn't load your order</h1>
          <p className="error-text">{error}</p>
        </>
      ) : paid ? (
        <>
          <h1>Payment received!</h1>
          {order && (
            <p>
              Your pickup code is <strong>{order.pickup_token}</strong> — listen for it at the
              counter. Total paid: ₹{order.total.toFixed(2)}.
            </p>
          )}
          <p className="muted-text">You can close this tab now.</p>
        </>
      ) : (
        <>
          <h1>Payment didn't go through</h1>
          <p className="muted-text">
            Please pay at the counter with the staff instead, or go back to the voice ordering
            tab to try again.
          </p>
        </>
      )}
    </div>
  );
}
