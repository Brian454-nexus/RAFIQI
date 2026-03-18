## RAFIQI — JARVIS-style local assistant + LiveKit Agent UI

This repo has two main parts:

- **Local brain API** (FastAPI): `api_server.py` exposes `POST /chat` and runs your local intelligence/tools.
- **Agent UI** (Next.js + LiveKit Components): `frontend/` provides the voice/chat interface with the **Aura** visualizer.

To make the UI feel like a real “JARVIS”, you also run a **LiveKit Agent participant** (`livekit_agent.py`) that joins the room, bridges chat → brain → chat, and publishes spoken audio so Aura reacts.

### Quick start

1) Configure LiveKit credentials for the UI (token minting)

- Copy `frontend/.env.local.example` → `frontend/.env.local`
- Set `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`

2) Start the local brain API

```bash
python api_server.py
```

3) Start the LiveKit bridge agent

```bash
set LIVEKIT_URL=wss://YOUR-PROJECT.livekit.cloud
set LIVEKIT_API_KEY=...
set LIVEKIT_API_SECRET=...
set LIVEKIT_ROOM=rafiqi
python livekit_agent.py
```

4) Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open `/rafiqi`, connect to room `rafiqi`, and send a chat message. You should get a reply + agent voice + Aura animation.

### Notes

- **TTS**: `livekit_agent.py` uses the `piper` CLI + `voices/en_US-lessac-high.onnx`. If `piper` isn’t available, it will still reply via chat but won’t speak.
- **Brain URL**: override with `RAFIQI_BRAIN_URL` (defaults to `http://localhost:8000/chat`).

