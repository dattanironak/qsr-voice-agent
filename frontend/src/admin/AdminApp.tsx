import { useEffect, useState } from "react";
import type { AdminSession } from "./auth";
import { fetchMe, logout } from "./auth";
import { LoginForm } from "./LoginForm";
import { MenuManager } from "./MenuManager";
import { OrderHistory } from "./OrderHistory";
import "./admin.css";

type View = "menu" | "orders";

const VIEWS_BY_ROLE: Record<string, View[]> = {
  owner: ["menu", "orders"],
  treasurer: ["orders"],
};

const VIEW_LABEL: Record<View, string> = {
  menu: "Update Menu",
  orders: "Order History",
};

export default function AdminApp() {
  const [session, setSession] = useState<AdminSession | null | undefined>(undefined);
  const [view, setView] = useState<View>("orders");

  useEffect(() => {
    fetchMe()
      .then(setSession)
      .catch(() => setSession(null));
  }, []);

  useEffect(() => {
    if (!session) return;
    const views = VIEWS_BY_ROLE[session.role] ?? ["orders"];
    setView(views[0]);
  }, [session]);

  function handleLogout() {
    logout();
    setSession(null);
  }

  function handleUnauthorized() {
    setSession(null);
  }

  if (session === undefined) {
    return (
      <div className="admin-shell">
        <p className="muted-text">Loading…</p>
      </div>
    );
  }

  if (session === null) {
    return <LoginForm onLoggedIn={setSession} />;
  }

  const availableViews = VIEWS_BY_ROLE[session.role] ?? ["orders"];

  return (
    <div className="admin-shell">
      <header className="admin-header">
        <h1>Admin dashboard</h1>
        <div className="admin-session-bar">
          <span className="muted-text">
            {session.username} <span className="admin-role-badge">{session.role}</span>
          </span>
          <button type="button" className="admin-btn-secondary" onClick={handleLogout}>
            Log out
          </button>
          <a className="admin-back-link" href="/">
            ← Back to ordering
          </a>
        </div>
      </header>

      <nav className="admin-nav">
        {availableViews.map((v) => (
          <button
            key={v}
            type="button"
            className={`admin-nav-tab${v === view ? " active" : ""}`}
            onClick={() => setView(v)}
          >
            {VIEW_LABEL[v]}
          </button>
        ))}
      </nav>

      {view === "menu" && availableViews.includes("menu") && (
        <MenuManager onUnauthorized={handleUnauthorized} />
      )}
      {view === "orders" && (
        <OrderHistory role={session.role} onUnauthorized={handleUnauthorized} />
      )}
    </div>
  );
}
