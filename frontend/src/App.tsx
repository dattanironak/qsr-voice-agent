import { useEffect, useState } from "react";
import { LiveKitRoom, RoomAudioRenderer, StartAudio } from "@livekit/components-react";
import "@livekit/components-styles";
import { createSessionToken, fetchMenu } from "./api";
import { OrderingExperience } from "./components/OrderingExperience";
import type { Menu, SessionToken } from "./types";
import "./App.css";

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

function App() {
  const [menu, setMenu] = useState<Menu | null>(null);
  const [menuError, setMenuError] = useState<string | null>(null);
  const [session, setSession] = useState<SessionToken | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [connectError, setConnectError] = useState<string | null>(null);
  const [orderJustEnded, setOrderJustEnded] = useState(false);

  useEffect(() => {
    fetchMenu()
      .then(setMenu)
      .catch((err) => setMenuError(errorMessage(err)));
  }, []);

  async function handleConnect() {
    setConnecting(true);
    setConnectError(null);
    setOrderJustEnded(false);
    try {
      const token = await createSessionToken();
      setSession(token);
    } catch (err) {
      setConnectError(errorMessage(err));
      setConnecting(false);
    }
  }

  return (
    <LiveKitRoom
      serverUrl={session?.livekit_url}
      token={session?.token}
      connect={session !== null}
      audio
      className="app-shell"
      onConnected={() => setConnecting(false)}
      onDisconnected={() => {
        setConnecting(false);
        // The agent closes the room itself right after the order-confirmation reply
        // (complete_order -> delete_room, before payment resolves — see agent.py's
        // _end_call_after_speech), so a disconnect while we had an active session means the
        // voice part of the flow finished, not an error — reset so "Start voice ordering" is
        // ready for a new order. Payment itself is still pending at this point; CheckoutPanel's
        // own polling (independent of the room) carries the order through to paid/failed.
        setSession((prevSession) => {
          if (prevSession !== null) {
            setOrderJustEnded(true);
          }
          return null;
        });
      }}
      onError={(err) => {
        setConnectError(errorMessage(err));
        setConnecting(false);
      }}
    >
      <RoomAudioRenderer />
      <StartAudio label="🔊 Tap to enable the assistant's voice" className="start-audio-btn" />
      <OrderingExperience
        menu={menu}
        menuError={menuError}
        connecting={connecting}
        connectError={connectError}
        hasSession={session !== null}
        orderJustEnded={orderJustEnded}
        onConnect={handleConnect}
      />
    </LiveKitRoom>
  );
}

export default App;
