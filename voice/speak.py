import os
import platform
import subprocess
import tempfile

import sounddevice as sd
import soundfile as sf

# Piper TTS voice configuration
VOICE_MODEL = "voices/en_US-lessac-high.onnx"
VOICE_CONFIG = "voices/en_US-lessac-high.onnx.json"


def speak(text: str) -> None:
    """Convert text to speech with Piper and play it."""
    if not text:
        return

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav_path = f.name

    try:
        # Ask Piper to synthesize directly to a WAV file.
        cmd = [
            "piper",
            "-m",
            VOICE_MODEL,
        ]
        if os.path.exists(VOICE_CONFIG):
            cmd += ["-c", VOICE_CONFIG]
        cmd += ["-f", wav_path]

        subprocess.run(
            cmd,
            input=text.encode("utf-8"),
            check=True,
        )

        system = platform.system()
        if system == "Linux":
            # Let the system player handle the WAV file.
            subprocess.run(["aplay", wav_path], check=False)
        else:
            data, samplerate = sf.read(wav_path)
            sd.play(data, samplerate)
            sd.wait()
    finally:
        if os.path.exists(wav_path):
            try:
                os.unlink(wav_path)
            except OSError:
                pass
