"use client";

import * as React from "react";
import {
  LiveKitRoom,
  RoomAudioRenderer,
  SessionProvider,
  useSession,
} from "@livekit/components-react";
import { TokenSource } from "livekit-client";
import { AgentSessionView_01 } from "@/components/agent-session-block";
import { Button } from "@/components/ui/button";

type ConnectionState = "idle" | "connecting" | "connected" | "error";

async function fetchToken(opts: { identity: string; room: string }) {
  const res = await fetch("/api/token", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(opts),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Token request failed (${res.status})`);
  }
  const data = (await res.json()) as { token: string; url: string };
  if (!data?.token || !data?.url) throw new Error("Token response missing fields.");
  return data;
}

export function RafiqiClient() {
  const [identity, setIdentity] = React.useState("hp");
  const [room, setRoom] = React.useState("rafiqi");
  const [state, setState] = React.useState<ConnectionState>("idle");
  const [conn, setConn] = React.useState<{ token: string; url: string } | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  function LiveKitSessionWrapper({
    children,
  }: {
    children: React.ReactNode;
  }) {
    if (!conn) {
      // This should never happen because wrapper is only rendered when `conn` exists.
      return null;
    }

    // Create a fixed token source from the token we just fetched from `/api/token`.
    // This lets LiveKit Components generate SessionContext that hooks like
    // `useSessionContext()` can safely consume.
    const tokenSource = React.useMemo(
      () =>
        TokenSource.literal({
          serverUrl: conn.url,
          participantToken: conn.token,
        }),
      [conn.url, conn.token],
    );

    const session = useSession(tokenSource);

    return <SessionProvider session={session}>{children}</SessionProvider>;
  }

  const connect = async () => {
    try {
      setError(null);
      setState("connecting");
      const data = await fetchToken({ identity: identity.trim(), room: room.trim() });
      setConn(data);
      setState("connected");
    } catch (e) {
      setConn(null);
      setState("error");
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const disconnect = () => {
    setConn(null);
    setState("idle");
  };

  if (!conn) {
    return (
      <div className="mx-auto flex min-h-svh w-full max-w-3xl flex-col justify-center px-6 py-12">
        <div className="space-y-4">
          <div className="space-y-1">
            <h1 className="text-3xl font-semibold tracking-tight">RAFIQI</h1>
            <p className="text-muted-foreground">
              Connect to your LiveKit agent session. Aura is enabled by default.
            </p>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <label className="space-y-1">
              <div className="text-sm font-medium">Identity</div>
              <input
                value={identity}
                onChange={(e) => setIdentity(e.target.value)}
                className="border-input bg-background w-full rounded-md border px-3 py-2 text-sm"
                placeholder="e.g. hp"
              />
            </label>

            <label className="space-y-1">
              <div className="text-sm font-medium">Room</div>
              <input
                value={room}
                onChange={(e) => setRoom(e.target.value)}
                className="border-input bg-background w-full rounded-md border px-3 py-2 text-sm"
                placeholder="rafiqi"
              />
            </label>
          </div>

          {error && (
            <pre className="bg-muted text-foreground whitespace-pre-wrap rounded-lg border p-4 text-sm">
              {error}
            </pre>
          )}

          <div className="flex items-center gap-3">
            <Button onClick={connect} disabled={state === "connecting"}>
              {state === "connecting" ? "Connecting…" : "Connect"}
            </Button>
            <div className="text-muted-foreground text-sm">
              Needs `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`.
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <LiveKitRoom
      serverUrl={conn.url}
      token={conn.token}
      connect
      audio
      video
      onDisconnected={disconnect}
      className="h-svh w-full"
    >
      <RoomAudioRenderer />
      <LiveKitSessionWrapper>
        <AgentSessionView_01
          audioVisualizerType="aura"
          audioVisualizerColor="#1FD5F9"
          audioVisualizerColorShift={0.28}
          supportsVideoInput
          supportsScreenShare
          supportsChatInput
          className="h-full"
        />
      </LiveKitSessionWrapper>
    </LiveKitRoom>
  );
}

