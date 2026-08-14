import { useEffect, useRef } from "react";
import { useLocalParticipant, useTranscriptions } from "@livekit/components-react";
import type { TextStreamData } from "@livekit/components-core";

interface TranscriptPanelProps {
  connected: boolean;
}

export function TranscriptPanel({ connected }: TranscriptPanelProps) {
  const { localParticipant } = useLocalParticipant();
  const segments = useTranscriptions();
  const scrollRef = useRef<HTMLDivElement>(null);

  // Transcription segments stream in incrementally (interim -> final) under the same stream id,
  // so keep only the latest text per id instead of appending duplicates.
  const byId = new Map<string, TextStreamData>();
  for (const segment of segments) {
    byId.set(segment.streamInfo.id, segment);
  }
  const ordered = Array.from(byId.values()).sort(
    (a, b) => a.streamInfo.timestamp - b.streamInfo.timestamp,
  );

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [ordered.length]);

  return (
    <div className="panel transcript-panel">
      <h2>Conversation</h2>
      {!connected ? (
        <p className="muted-text">Connect to see the live conversation here.</p>
      ) : (
        <div className="transcript-scroll" ref={scrollRef}>
          {ordered.length === 0 && <p className="muted-text">Say hello to get started…</p>}
          {ordered.map((segment) => {
            const isCustomer = segment.participantInfo.identity === localParticipant.identity;
            return (
              <div
                key={segment.streamInfo.id}
                className={`transcript-bubble ${isCustomer ? "from-customer" : "from-agent"}`}
              >
                <span className="transcript-speaker">{isCustomer ? "You" : "Assistant"}</span>
                <p>{segment.text}</p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
