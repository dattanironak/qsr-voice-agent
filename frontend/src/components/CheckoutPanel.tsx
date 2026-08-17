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

interface BoltResponse {
  response?: { txnStatus?: string };
}

declare global {
  interface Window {
    bolt?: {
      launch: (
        data: Record<string, string>,
        handlers: {
          responseHandler: (bolt: BoltResponse) => void;
          catchException: (bolt: BoltResponse) => void;
        }
      ) => void;
    };
  }
}

// PayU's hosted `/_payment` page refuses to be framed from origins outside its own partner
// allowlist (X-Frame-Options), so an inline iframe of the classic checkout page is blocked by the
// browser. Bolt is PayU's own on-page overlay SDK instead — it doesn't hit that restriction
// because PayU controls the overlay's rendering itself, not our iframe.
const BOLT_SCRIPT_PROD = "https://jssdk.payu.in/bolt/bolt.min.js";
const BOLT_SCRIPT_UAT = "https://jssdk-uat.payu.in/bolt/bolt.min.js";

const boltScriptPromises = new Map<string, Promise<void>>();

function loadBoltScript(src: string): Promise<void> {
  let promise = boltScriptPromises.get(src);
  if (!promise) {
    promise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = src;
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error("Failed to load the PayU payment SDK"));
      document.head.appendChild(script);
    });
    boltScriptPromises.set(src, promise);
  }
  return promise;
}

// Shown once the voice agent has confirmed the order and created it on the backend
// (order_update/order_created). Payment is UPI-only: PayU's Bolt SDK renders the hosted UPI QR
// as an on-page overlay the moment checkout fields are ready — no button click, no new tab, no
// navigating away — so the voice call widget stays visible and running underneath. The actual
// "paid" transition is still driven server-side by PayU's surl/furl callback (routers/payments.py)
// since the backend requests `mode=dropout`; this panel's own polling below just mirrors that
// status on screen.
export function CheckoutPanel({ order, onStatusChange }: CheckoutPanelProps) {
  const [checkout, setCheckout] = useState<PayuCheckout | null>(null);
  const [checkoutError, setCheckoutError] = useState<string | null>(null);
  const launchedTxnRef = useRef<string | null>(null);

  useEffect(() => {
    if (order.status !== "pending_payment") return;
    setCheckout(null);
    setCheckoutError(null);
    launchedTxnRef.current = null;
    createPayuCheckout(order.id)
      .then(setCheckout)
      .catch((err) => setCheckoutError(errorMessage(err)));
  }, [order.id, order.status]);

  useEffect(() => {
    if (!checkout || launchedTxnRef.current === checkout.fields.txnid) return;
    const scriptSrc = checkout.action_url.includes("test.payu.in") ? BOLT_SCRIPT_UAT : BOLT_SCRIPT_PROD;
    let cancelled = false;
    loadBoltScript(scriptSrc)
      .then(() => {
        if (cancelled || !window.bolt) return;
        launchedTxnRef.current = checkout.fields.txnid;
        window.bolt.launch(checkout.fields, {
          responseHandler: () => {
            // No client-side action needed — PayU's mode=dropout callback to surl/furl already
            // updates the order server-side, and this panel's polling below picks it up.
          },
          catchException: () =>
            setCheckoutError("Couldn't open the payment window. Please try again."),
        });
      })
      .catch((err) => setCheckoutError(errorMessage(err)));
    return () => {
      cancelled = true;
    };
  }, [checkout]);

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
          <p className="muted-text">Pay with any UPI app — scan the QR code that opens below.</p>
          {checkoutError && <p className="error-text">{checkoutError}</p>}
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
