import { useEffect, useState } from "react";
import type { Order } from "../types";
import { fetchAdminOrders } from "./api";
import { UnauthorizedError } from "./auth";

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

function formatItems(order: Order): string {
  return order.items.map((item) => `${item.quantity}× ${item.name}`).join(", ");
}

interface OrderHistoryProps {
  role: string;
  onUnauthorized: () => void;
}

export function OrderHistory({ role, onUnauthorized }: OrderHistoryProps) {
  const [orders, setOrders] = useState<Order[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    fetchAdminOrders()
      .then(setOrders)
      .catch((err) => {
        if (err instanceof UnauthorizedError) {
          onUnauthorized();
          return;
        }
        setLoadError(errorMessage(err));
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (loadError) {
    return <p className="error-text">Couldn't load order history: {loadError}</p>;
  }

  if (!orders) {
    return <p className="muted-text">Loading…</p>;
  }

  return (
    <section className="admin-main panel">
      <div className="admin-main-header">
        <h2>Order history</h2>
        {role === "treasurer" && <span className="muted-text">Showing today's orders</span>}
      </div>

      {orders.length === 0 ? (
        <p className="muted-text">No orders yet.</p>
      ) : (
        <table className="admin-items-table">
          <thead>
            <tr>
              <th>Pickup</th>
              <th>Items</th>
              <th>Total</th>
              <th>Status</th>
              <th>Placed</th>
            </tr>
          </thead>
          <tbody>
            {orders.map((order) => (
              <tr key={order.id}>
                <td>{order.pickup_token}</td>
                <td className="admin-order-items">{formatItems(order)}</td>
                <td>₹{order.total.toFixed(2)}</td>
                <td>
                  <span className={`admin-order-status admin-order-status-${order.status}`}>
                    {order.status.replace(/_/g, " ")}
                  </span>
                </td>
                <td className="muted-text">{new Date(order.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
