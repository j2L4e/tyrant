import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import tempfile
import os
import base64
from mistralai import Mistral
import subprocess
from dotenv import load_dotenv
import time
import logging
import argparse

def setup_logging(verbose):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format='%(levelname)s: %(message)s')

load_dotenv()

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MODEL_NAME = "voxtral-mini-latest"

def record_audio(duration=None, fs=16000):
    """
    Records audio from the microphone. 
    If duration is None, it could be a push-to-talk or start/stop mechanism.
    For simplicity, let's start with a fixed duration or manual stop.
    """
    logging.info("Recording... Press Ctrl+C to stop.")
    recording = []
    try:
        def callback(indata, frames, time, status):
            if status:
                logging.warning(f"Audio status: {status}")
            recording.append(indata.copy())
        
        with sd.InputStream(samplerate=fs, channels=1, callback=callback):
            while True:
                time.sleep(0.1)
    except KeyboardInterrupt:
        logging.info("Stopped recording.")
    
    return np.concatenate(recording, axis=0), fs

def save_temp_wav(data, fs):
    temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    wav.write(temp_file.name, fs, data)
    logging.debug(f"Saved temporary audio to {temp_file.name}")
    return temp_file.name

def transcribe_audio(file_path):
    if not MISTRAL_API_KEY:
        raise ValueError("MISTRAL_API_KEY not found in environment variables")
    
    logging.debug(f"Sending request to Mistral API for file: {file_path}")
    client = Mistral(api_key=MISTRAL_API_KEY)
    
    with open(file_path, 'rb') as f:
        content = f.read()
    
    audio_base64 = base64.b64encode(content).decode('utf-8')

    response = client.chat.complete(
        model=MODEL_NAME,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "input_audio",
                    "input_audio": audio_base64,
                },
                {
                    "type": "text",
                    "text": "Transcribe the audio precisely without any additional comments."
                },
            ]
        }],
    )
    
    logging.debug(f"API Response: {response}")
    # The SDK response object has the transcription in its choices[0].message.content
    return response.choices[0].message.content

def type_text(text):
    logging.info(f"Typing: {text}")
    subprocess.run(['xdotool', 'type', '--clearmodifiers', text])

def main():
    parser = argparse.ArgumentParser(description="Record microphone and transcribe using Mistral AI")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    setup_logging(args.verbose)

    try:
        audio_data, fs = record_audio()
        temp_wav = save_temp_wav(audio_data, fs)
        logging.info("Transcribing...")
        text = transcribe_audio(temp_wav)
        logging.info(f"Transcribed text: {text}")
        type_text(text)
        os.unlink(temp_wav)
        logging.debug(f"Deleted temporary file {temp_wav}")
    except Exception as e:
        logging.error(f"Error: {e}")

if __name__ == "__main__":
    main()
