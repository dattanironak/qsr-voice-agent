import type { Menu, Order, PayuCheckout, SessionToken } from "./types";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL ?? "http://localhost:8000";

export async function fetchMenu(): Promise<Menu> {
  const res = await fetch(`${BACKEND_URL}/menu`);
  if (!res.ok) {
    throw new Error(`GET /menu failed: ${res.status}`);
  }
  return res.json();
}

export async function fetchOrder(orderId: string): Promise<Order> {
  const res = await fetch(`${BACKEND_URL}/orders/${orderId}`);
  if (!res.ok) {
    throw new Error(`GET /orders/${orderId} failed: ${res.status}`);
  }
  return res.json();
}

export async function createPayuCheckout(orderId: string): Promise<PayuCheckout> {
  const res = await fetch(`${BACKEND_URL}/orders/${orderId}/payu/qr`, { method: "POST" });
  if (!res.ok) {
    throw new Error(`POST /orders/${orderId}/payu/qr failed: ${res.status}`);
  }
  return res.json();
}

export async function createSessionToken(customerName?: string): Promise<SessionToken> {
  const res = await fetch(`${BACKEND_URL}/session/token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ customer_name: customerName ?? null }),
  });
  if (!res.ok) {
    throw new Error(`POST /session/token failed: ${res.status}`);
  }
  return res.json();
}
