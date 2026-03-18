import { NextResponse } from "next/server";
import { AccessToken } from "livekit-server-sdk";

export async function POST(req: Request) {
  const url = process.env.LIVEKIT_URL;
  const apiKey = process.env.LIVEKIT_API_KEY;
  const apiSecret = process.env.LIVEKIT_API_SECRET;

  if (!url || !apiKey || !apiSecret) {
    return new NextResponse(
      [
        "Missing LiveKit server env vars.",
        "Set LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET in frontend/.env.local",
      ].join("\n"),
      { status: 500 },
    );
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    body = {};
  }

  const identity = (body as any)?.identity?.toString?.() ?? "user";
  const room = (body as any)?.room?.toString?.() ?? "rafiqi";

  const at = new AccessToken(apiKey, apiSecret, {
    identity,
    ttl: "6h",
  });
  at.addGrant({
    room,
    roomJoin: true,
    canPublish: true,
    canSubscribe: true,
    canPublishData: true,
  });

  return NextResponse.json({ token: await at.toJwt(), url });
}

