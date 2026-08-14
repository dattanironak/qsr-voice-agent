interface HeaderProps {
  connected: boolean;
  connecting: boolean;
  error: string | null;
  hasSession: boolean;
  onConnect: () => void;
}

export function Header({ connected, connecting, error, hasSession, onConnect }: HeaderProps) {
  const busy = connecting || (hasSession && !connected);

  return (
    <header className="app-header">
      <h1>Order here</h1>
      <div className="connect-area">
        {connected ? (
          <span className="status-pill status-connected">● Connected</span>
        ) : (
          <button type="button" className="connect-btn" disabled={busy} onClick={onConnect}>
            {busy ? "Connecting…" : "Start voice ordering"}
          </button>
        )}
        {error && <span className="error-text">{error}</span>}
      </div>
    </header>
  );
}
