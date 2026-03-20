"""
LiveKit "bridge agent" for RAFIQI.

What it does:
- Joins a LiveKit room as a participant ("rafiqi-agent")
- Receives chat messages from the Agent UI (LiveKit Components `useChat()`)
- For each user message, calls the local brain API (`api_server.py` -> POST /chat)
- Sends the reply back to the room as a chat data message
- Publishes a local audio track and plays TTS audio (Piper) into the room

Prereqs:
- Set env vars: LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
- Run the local brain API: `python api_server.py` (default: http://localhost:8000/chat)
- Ensure `piper` CLI is installed and `voices/en_US-lessac-high.onnx` exists
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.request
from urllib.parse import urlparse
from dataclasses import dataclass
from typing import Any, Optional

from dotenv import load_dotenv

import numpy as np
import soundfile as sf
from livekit import rtc
from livekit.api import AccessToken, VideoGrants


# Resolve default voice model paths relative to repo root.
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
VOICE_MODEL = os.getenv(
    "PIPER_VOICE_MODEL",
    os.path.join(REPO_ROOT, "voices", "en_US-lessac-high.onnx"),
)
VOICE_CONFIG = os.getenv(
    "PIPER_VOICE_CONFIG",
    os.path.join(REPO_ROOT, "voices", "en_US-lessac-high.onnx.json"),
)

DEFAULT_BRAIN_URL = os.getenv("RAFIQI_BRAIN_URL", "http://localhost:8000/chat")
DEFAULT_ROOM = os.getenv("LIVEKIT_ROOM", "rafiqi")
DEFAULT_IDENTITY = os.getenv("LIVEKIT_IDENTITY", "rafiqi-agent")
DEFAULT_CHAT_TOPIC = os.getenv("LIVEKIT_CHAT_TOPIC", "lk-chat")

# LiveKit typical audio is 48kHz mono
LK_SAMPLE_RATE = 48000
LK_CHANNELS = 1
FRAME_MS = 20
SAMPLES_PER_CHANNEL = int(LK_SAMPLE_RATE * FRAME_MS / 1000)  # 960 @ 48kHz


@dataclass
class ChatPayload:
    """Parsed chat payload from LiveKit Components Chat."""

    message: str


def _env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        missing = [k for k in ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET") if not os.getenv(k)]
        hint = f"Missing required env var: {name}."
        if missing:
            hint += f" Still missing: {', '.join(missing)}."
        hint += " Tip: set them in your terminal, or ensure `frontend/.env.local` exists."
        raise RuntimeError(hint)
    return value


def _safe_decode(data: Any) -> str:
    if isinstance(data, (bytes, bytearray)):
        return data.decode("utf-8", errors="replace")
    return str(data)


def _parse_chat_message(raw: str) -> Optional[ChatPayload]:
    """
    `useChat().send("text")` in LiveKit Components typically sends a JSON payload on topic "lk-chat".
    We accept both:
    - Plain string: "hello"
    - JSON: {"message":"hello", ...}
    """
    raw = raw.strip()
    if not raw:
        return None
    if raw.startswith("{"):
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict):
                # Accept multiple common payload shapes from text chat and voice
                # transcription providers.
                candidate_keys = (
                    "message",
                    "text",
                    "transcript",
                    "utterance",
                    "content",
                    "final",
                )
                for key in candidate_keys:
                    msg = obj.get(key)
                    if isinstance(msg, str) and msg.strip():
                        return ChatPayload(message=msg.strip())

                # Some publishers nest the actual content under payload/data.
                for container_key in ("payload", "data"):
                    nested = obj.get(container_key)
                    if isinstance(nested, dict):
                        for key in candidate_keys:
                            msg = nested.get(key)
                            if isinstance(msg, str) and msg.strip():
                                return ChatPayload(message=msg.strip())
        except Exception:
            return None
    return ChatPayload(message=raw)

def _piper_ready() -> tuple[bool, str]:
    if not shutil.which("piper"):
        return False, "Missing `piper` executable on PATH."
    if not os.path.exists(VOICE_MODEL):
        voice_dir = os.path.dirname(os.path.abspath(VOICE_MODEL)) or os.getcwd()
        try:
            existing = sorted(os.listdir(voice_dir))
        except Exception:
            existing = []
        hint = (
            f"Missing Piper voice model: {VOICE_MODEL}. "
            f"Looking in '{voice_dir}'. "
            f"Found: {', '.join(existing[:20]) if existing else '(no files)'}"
        )
        return False, hint
    if not os.path.exists(VOICE_CONFIG):
        return False, f"Missing Piper voice config: {VOICE_CONFIG}"
    return True, "ok"


def brain_chat(text: str, url: str = DEFAULT_BRAIN_URL, timeout_s: float = 30.0) -> str:
    body = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        data = resp.read().decode("utf-8", errors="replace")
    try:
        parsed = json.loads(data)
        reply = parsed.get("reply")
        if isinstance(reply, str) and reply.strip():
            return reply.strip()
    except Exception:
        pass
    return data.strip() or "Sorry — no response."


def synthesize_wav_piper(text: str) -> tuple[np.ndarray, int]:
    """
    Synthesize with the `piper` CLI into a temp wav and load it.
    Returns (mono_float32_samples, sample_rate).
    """
    if not text.strip():
        return np.zeros((0,), dtype=np.float32), LK_SAMPLE_RATE

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav_path = f.name

    try:
        cmd = ["piper", "-m", VOICE_MODEL]
        if os.path.exists(VOICE_CONFIG):
            cmd += ["-c", VOICE_CONFIG]
        cmd += ["-f", wav_path]

        subprocess.run(cmd, input=text.encode("utf-8"), check=True)

        audio, sr = sf.read(wav_path, dtype="float32", always_2d=False)
        if audio is None:
            return np.zeros((0,), dtype=np.float32), sr
        if audio.ndim == 2:
            audio = np.mean(audio, axis=1)
        return audio.astype(np.float32, copy=False), int(sr)
    finally:
        try:
            os.unlink(wav_path)
        except OSError:
            pass


def resample_mono(audio: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    if src_sr == dst_sr or audio.size == 0:
        return audio
    # Linear interpolation resampler (good enough for TTS voice playback)
    duration = audio.size / float(src_sr)
    dst_len = max(1, int(round(duration * dst_sr)))
    src_x = np.linspace(0.0, duration, num=audio.size, endpoint=False, dtype=np.float64)
    dst_x = np.linspace(0.0, duration, num=dst_len, endpoint=False, dtype=np.float64)
    return np.interp(dst_x, src_x, audio).astype(np.float32, copy=False)


def float_to_int16_pcm(audio: np.ndarray) -> bytes:
    if audio.size == 0:
        return b""
    audio = np.clip(audio, -1.0, 1.0)
    pcm = (audio * 32767.0).astype(np.int16)
    return pcm.tobytes()


async def play_tts_into_room(source: rtc.AudioSource, text: str) -> None:
    audio, sr = synthesize_wav_piper(text)
    audio = resample_mono(audio, sr, LK_SAMPLE_RATE)
    pcm_bytes = float_to_int16_pcm(audio)
    if not pcm_bytes:
        return

    bytes_per_sample = 2
    frame_bytes = LK_CHANNELS * SAMPLES_PER_CHANNEL * bytes_per_sample

    # Stream frames in real time
    for i in range(0, len(pcm_bytes), frame_bytes):
        chunk = pcm_bytes[i : i + frame_bytes]
        if len(chunk) < frame_bytes:
            chunk = chunk + b"\x00" * (frame_bytes - len(chunk))

        frame = rtc.AudioFrame(
            chunk,
            LK_SAMPLE_RATE,
            LK_CHANNELS,
            SAMPLES_PER_CHANNEL,
        )
        await source.capture_frame(frame)
        await asyncio.sleep(SAMPLES_PER_CHANNEL / LK_SAMPLE_RATE)


async def connect_with_retry(
    room: rtc.Room,
    lk_url: str,
    token: str,
    *,
    attempts: int = 6,
    base_backoff_s: float = 1.0,
    room_options: Optional["rtc.RoomOptions"] = None,
) -> None:
    last_exc: Optional[BaseException] = None
    for n in range(1, attempts + 1):
        try:
            if room_options is None:
                await room.connect(lk_url, token)
            else:
                await room.connect(lk_url, token, options=room_options)
            return
        except Exception as e:
            last_exc = e
            sleep_s = base_backoff_s * (2 ** (n - 1))
            # Cap backoff so we don't wait too long during development.
            sleep_s = min(sleep_s, 15.0)
            print(f"[agent] connect attempt {n}/{attempts} failed: {e!r}. Retrying in {sleep_s:.1f}s…")
            await asyncio.sleep(sleep_s)
    assert last_exc is not None
    raise last_exc


async def main() -> None:
    # Load credentials from the frontend env template if they're not already set.
    # This avoids having to manually `set LIVEKIT_URL=...` in every terminal.
    try:
        load_dotenv(os.path.join(REPO_ROOT, "frontend", ".env.local"), override=False)
        load_dotenv(os.path.join(REPO_ROOT, ".env.local"), override=False)
    except Exception:
        # Don't fail startup just because dotenv couldn't load; we still have _env() checks below.
        pass

    lk_url = _env("LIVEKIT_URL")
    api_key = _env("LIVEKIT_API_KEY")
    api_secret = _env("LIVEKIT_API_SECRET")

    room_name = os.getenv("LIVEKIT_ROOM", DEFAULT_ROOM)
    identity = os.getenv("LIVEKIT_IDENTITY", DEFAULT_IDENTITY)
    brain_url = os.getenv("RAFIQI_BRAIN_URL", DEFAULT_BRAIN_URL)
    chat_topic = os.getenv("LIVEKIT_CHAT_TOPIC", DEFAULT_CHAT_TOPIC)

    piper_ok, piper_msg = _piper_ready()
    if not piper_ok:
        print(f"[agent] TTS disabled: {piper_msg}")
    else:
        print("[agent] TTS enabled (piper found)")

    # Create a room client
    loop = asyncio.get_running_loop()
    room = rtc.Room(loop=loop)

    # Create and publish an audio track for agent TTS
    audio_source = rtc.AudioSource(LK_SAMPLE_RATE, LK_CHANNELS)
    audio_track = rtc.LocalAudioTrack.create_audio_track("rafiqi-tts", audio_source)

    token = (
        AccessToken(api_key, api_secret)
        .with_identity(identity)
        .with_name("Rafiqi Agent")
        .with_grants(VideoGrants(room_join=True, room=room_name))
        .to_jwt()
    )

    parsed = urlparse(lk_url)
    print(
        f"[agent] connecting to room='{room_name}' as '{identity}' "
        f"serverUrl='{lk_url}' host='{parsed.hostname or lk_url}'"
    )
    # Shorter connect timeout helps keep the agent responsive during transient network hiccups.
    room_options = None
    try:
        room_options = rtc.RoomOptions(connect_timeout=20)
    except Exception:
        room_options = None

    await connect_with_retry(room, lk_url, token, room_options=room_options)

    publish_opts = rtc.TrackPublishOptions()
    publish_opts.source = rtc.TrackSource.SOURCE_MICROPHONE
    await room.local_participant.publish_track(audio_track, publish_opts)

    last_seen_ts = 0.0
    speak_lock = asyncio.Lock()
    queue: asyncio.Queue[str] = asyncio.Queue()

    async def worker() -> None:
        while True:
            msg = await queue.get()
            try:
                print(f"[agent] user: {msg}")
                try:
                    reply = brain_chat(msg, url=brain_url)
                except Exception as e:
                    reply = f"Sorry — the local brain API failed: {e}"

                # Send chat reply back to room
                try:
                    await room.local_participant.publish_data(
                        json.dumps({"message": reply}).encode("utf-8"),
                        reliable=True,
                        topic=chat_topic,
                    )
                except Exception:
                    await room.local_participant.publish_data(reply.encode("utf-8"), reliable=True)

                # Speak reply into the room (drives Aura)
                if piper_ok:
                    async with speak_lock:
                        try:
                            await play_tts_into_room(audio_source, reply)
                        except Exception as e:
                            print(f"[agent] TTS failed: {e}")
            finally:
                queue.task_done()

    worker_task = asyncio.create_task(worker())

    @room.on("data_received")
    def on_data_received(packet: rtc.DataPacket) -> None:
        nonlocal last_seen_ts

        # best-effort filter: ignore our own messages
        if packet.participant and packet.participant.identity == identity:
            return

        pkt_topic = getattr(packet, "topic", None)

        raw = _safe_decode(packet.data)
        payload = _parse_chat_message(raw)
        if not payload:
            return

        # throttle very fast repeats (e.g. reconnection replays)
        now = time.time()
        if now - last_seen_ts < 0.2:
            return
        last_seen_ts = now

        print(
            f"[agent] recv topic='{pkt_topic or '(none)'}' from="
            f"'{getattr(packet.participant, 'identity', 'unknown')}' msg='{payload.message[:120]}'"
        )
        queue.put_nowait(payload.message)

    print("[agent] connected. Waiting for chat messages…")
    try:
        while True:
            await asyncio.sleep(1)
    finally:
        worker_task.cancel()
        await room.disconnect()


if __name__ == "__main__":
    asyncio.run(main())

