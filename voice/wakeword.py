import pyaudio
import numpy as np
from openwakeword.model import Model
from openwakeword.utils import download_models

# Available built-in wake words (model names):
# "hey jarvis", "alexa", "hey mycroft", "ok nabu", etc.
WAKE_WORD = "hey jarvis"
THRESHOLD = 0.5  # 0.0 to 1.0 — higher = less sensitive

# Ensure bundled models are present, then load with VAD enabled.
download_models()
oww_model = Model(vad_threshold=0.5)


def wait_for_wake_word() -> bool:
    """Block until the wake word is detected."""
    audio = pyaudio.PyAudio()
    stream = audio.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=16000,
        input=True,
        frames_per_buffer=1280,
    )
    print(f'Waiting for wake word: "{WAKE_WORD}"...')

    try:
        while True:
            chunk = stream.read(1280, exception_on_overflow=False)
            audio_data = np.frombuffer(chunk, dtype=np.int16)
            prediction = oww_model.predict(audio_data)
            score = prediction[WAKE_WORD]
            if score >= THRESHOLD:
                print("Wake word detected!")
                return True
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()