import { useState } from "react";
import type { AdminSession } from "./auth";
import { login } from "./auth";

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

interface LoginFormProps {
  onLoggedIn: (session: AdminSession) => void;
}

export function LoginForm({ onLoggedIn }: LoginFormProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const session = await login(username, password);
      onLoggedIn(session);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="admin-shell admin-login-shell">
      <form className="admin-form admin-login-form panel" onSubmit={handleSubmit}>
        <h1>Admin login</h1>
        {error && <p className="error-text">{error}</p>}
        <label className="admin-field">
          <span>Username</span>
          <input
            autoFocus
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
          />
        </label>
        <label className="admin-field">
          <span>Password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
          />
        </label>
        <button type="submit" className="admin-btn-primary" disabled={submitting}>
          {submitting ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
