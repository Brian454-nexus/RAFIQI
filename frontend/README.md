This is the **Rafiqi Agent UI** (Next.js) — a LiveKit-based voice/chat interface.

It includes a shader-driven **Aura** voice waveform/visualizer.

## Getting Started

### 1) Configure LiveKit credentials (server-side)

- Copy `frontend/.env.local.example` to `frontend/.env.local`
- Fill in:
  - `LIVEKIT_URL`
  - `LIVEKIT_API_KEY`
  - `LIVEKIT_API_SECRET`

These are used only by the Next.js route `src/app/api/token/route.ts` to mint room tokens.

### 2) Install and run the dev server

From `frontend/`:

```bash
npm install
npm run dev
```

Open `http://localhost:3000`, then go to `/rafiqi`.

### 3) Connect to a room that has an Agent

The UI will join the LiveKit room you specify and render:

- A **control bar** (mic/cam/screenshare/chat)
- A **chat transcript**
- The **Aura** visualizer (default)

Important: the UI expects there to be a LiveKit **Agent** (or any participant) in the room that can respond (publish audio and/or data messages). This repo currently provides the UI and a local brain HTTP API (`api_server.py`); you can run an Agent elsewhere that calls back into the local brain API.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
