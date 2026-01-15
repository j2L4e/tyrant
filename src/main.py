import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import tempfile
import os
from mistralai import Mistral
import subprocess
from dotenv import load_dotenv
import time
import logging
import argparse
import threading
from pynput import keyboard

def setup_logging(verbose):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format='%(levelname)s: %(message)s')

load_dotenv()

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MODEL_NAME = "voxtral-mini-transcribe-2507"

def record_audio(fs=16000, ptt_key=None):
    """
    Records audio from the microphone.
    If ptt_key is provided, it uses push-to-talk.
    Otherwise, it records until Ctrl+C.
    """
    recording = []
    
    def callback(indata, frames, time, status):
        if status:
            logging.warning(f"Audio status: {status}")
        if not ptt_key or is_recording.is_set():
            recording.append(indata.copy())

    if ptt_key:
        logging.info(f"Hold '{ptt_key}' to record.")
        is_recording = threading.Event()
        stop_event = threading.Event()

        def on_press(key):
            try:
                k = key.char  # single-char keys
            except AttributeError:
                k = key.name  # special keys
            
            if k == ptt_key and not is_recording.is_set():
                logging.info("Recording started...")
                is_recording.set()

        def on_release(key):
            try:
                k = key.char
            except AttributeError:
                k = key.name
            
            if k == ptt_key:
                logging.info("Recording stopped.")
                is_recording.clear()
                stop_event.set()
                return False  # Stop listener

        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            with sd.InputStream(samplerate=fs, channels=1, callback=callback):
                while not is_recording.is_set():
                    if not listener.running: # Handle case where key was released before we started waiting
                         break
                    time.sleep(0.01)
                
                # While we are recording, keep the stream open
                while is_recording.is_set():
                    time.sleep(0.01)
            
            listener.join()
    else:
        logging.info("Recording... Press Ctrl+C to stop.")
        try:
            with sd.InputStream(samplerate=fs, channels=1, callback=callback):
                while True:
                    time.sleep(0.1)
        except KeyboardInterrupt:
            logging.info("Stopped recording.")
    
    if not recording:
        return None, fs

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
        response = client.audio.transcriptions.complete(
            model=MODEL_NAME,
            file={
                "content": f,
                "file_name": os.path.basename(file_path),
            }
        )
    
    logging.debug(f"API Response: {response}")
    return response.text

def type_text(text):
    logging.info(f"Typing: {text}")
    subprocess.run(['xdotool', 'type', '--clearmodifiers', text])

def main():
    parser = argparse.ArgumentParser(description="Record microphone and transcribe using Mistral AI")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--ptt", help="Use push-to-talk with the specified key (e.g., 'ctrl', 'alt', 'caps_lock')")
    args = parser.parse_args()

    setup_logging(args.verbose)

    while True:
        try:
            audio_data, fs = record_audio(ptt_key=args.ptt)
            if audio_data is None:
                if args.ptt:
                    continue # Wait for next press if PTT
                else:
                    logging.info("No audio recorded.")
                    break

            temp_wav = save_temp_wav(audio_data, fs)
            logging.info("Transcribing...")
            text = transcribe_audio(temp_wav)
            logging.info(f"Transcribed text: {text}")
            type_text(text)
            os.unlink(temp_wav)
            logging.debug(f"Deleted temporary file {temp_wav}")
            
            if not args.ptt:
                break # In manual mode, we finish after one recording
        except KeyboardInterrupt:
            logging.info("Exiting...")
            break
        except Exception as e:
            logging.error(f"Error: {e}")
            if not args.ptt:
                break

if __name__ == "__main__":
    main()
