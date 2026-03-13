# Speech-to-text functionality using OpenAI's Whisper model
import os
import tempfile

import numpy as np
import sounddevice as sd
import soundfile as sf
from faster_whisper import WhisperModel

# Load model once at startup (base.en = English only, fast)
# Options: tiny, base, small, medium, large-v3, distil-large-v3, etc.
# Default here: CPU INT8 for broad compatibility.
model = WhisperModel("base.en", device="cpu", compute_type="int8")


def listen(seconds: int = 5, sample_rate: int = 16000) -> str:
    """Record audio from microphone and transcribe it."""
    print("Listening...")
    audio = sd.rec(
        int(seconds * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
    )
    sd.wait()  # Wait until recording is done

    tmp_path = None
    try:
        # Save to a temp file and transcribe
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_path = f.name
            sf.write(tmp_path, audio, sample_rate)

        segments, _ = model.transcribe(
            tmp_path,
            language="en",
            vad_filter=True,
        )
        text = " ".join(s.text for s in segments).strip()
        print(f"You said: {text}")
        return text
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass