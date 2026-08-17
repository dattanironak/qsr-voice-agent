import { useTrackToggle, useVoiceAssistant } from "@livekit/components-react";
import { Track } from "livekit-client";

const STATE_LABEL: Record<string, string> = {
  disconnected: "Not connected",
  connecting: "Connecting…",
  "pre-connect-buffering": "Connecting…",
  initializing: "Getting ready…",
  idle: "Idle",
  listening: "Listening…",
  thinking: "Thinking…",
  speaking: "Speaking…",
  failed: "Connection failed",
};

interface VoiceControlsProps {
  connected: boolean;
  canEndConversation: boolean;
  onEndConversation: () => void;
}

export function VoiceControls({ connected, canEndConversation, onEndConversation }: VoiceControlsProps) {
  const { state } = useVoiceAssistant();
  const { toggle, enabled, pending } = useTrackToggle({ source: Track.Source.Microphone });

  if (!connected) {
    return null;
  }

  return (
    <div className="panel voice-controls">
      <div className={`agent-state agent-state-${state}`}>
        <span className="agent-state-dot" />
        {STATE_LABEL[state] ?? state}
      </div>
      <div className="voice-controls-actions">
        <button
          type="button"
          className="mic-toggle-btn"
          disabled={pending}
          onClick={() => toggle()}
        >
          {enabled ? "Mute mic" : "Unmute mic"}
        </button>
        {canEndConversation && (
          <button type="button" className="end-conversation-btn" onClick={onEndConversation}>
            End conversation
          </button>
        )}
      </div>
    </div>
  );
}
