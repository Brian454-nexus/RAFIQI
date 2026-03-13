# Speech-to-text functionality using OpenAI's Whisper model
import sounddevice as sd
import numpy as np
import soundfile as sf
import tempfile
import os
from faster_whisper import WhisperModel
 
# Load model once at startup (base.en = English only, fast)
# Options: tiny, base, small, medium (bigger = more accurate but slower)
model = WhisperModel('base.en', device='cpu', compute_type='int8')
 
def listen(seconds=5, sample_rate=16000):
    """Record audio from microphone and transcribe it."""
    print('Listening...')
    audio = sd.rec(
        int(seconds * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype='float32'
    )
    sd.wait()  # Wait until recording is done
    
    # Save to a temp file and transcribe
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        sf.write(f.name, audio, sample_rate)
        segments, _ = model.transcribe(f.name, language='en')
        text = ' '.join([s.text for s in segments]).strip()
        os.unlink(f.name)
       
       print(f'You said: {text}')
    return text