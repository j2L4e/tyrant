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
import pystray
from pystray import MenuItem as item
from tray import create_idle_icon, create_muted_icon, create_recording_icon, create_transcribing_icon

def setup_logging(verbose):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format='%(levelname)s: %(message)s')

load_dotenv()

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MODEL_NAME = "voxtral-mini-transcribe-2507"

def record_audio(fs=16000, ptt_key=None, tray_icon=None, icons=None, muted=None):
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
        start_time = [0]
        duration = [0]

        def on_press(key):
            try:
                k = key.char  # single-char keys
            except AttributeError:
                k = key.name  # special keys
            
            if k == ptt_key and not is_recording.is_set():
                if muted and muted.is_set():
                    return  # Don't record when muted
                logging.info("Recording started...")
                if tray_icon and icons:
                    tray_icon.icon = icons['recording']
                start_time[0] = time.time()
                is_recording.set()

        def on_release(key):
            try:
                k = key.char
            except AttributeError:
                k = key.name
            
            if k == ptt_key:
                duration[0] = time.time() - start_time[0]
                logging.info(f"Recording stopped. Duration: {duration[0]:.2f}s")
                if tray_icon and icons:
                    tray_icon.icon = icons['idle']
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
        
        if duration[0] <= 2.0:
            logging.info("Recording too short, discarding.")
            return None, fs
    else:
        logging.info("Recording... Press Ctrl+C to stop.")
        if tray_icon and icons:
            tray_icon.icon = icons['recording']
        try:
            with sd.InputStream(samplerate=fs, channels=1, callback=callback):
                while True:
                    time.sleep(0.1)
        except KeyboardInterrupt:
            logging.info("Stopped recording.")
        finally:
            if tray_icon and icons:
                tray_icon.icon = icons['idle']
    
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

def run_transcription_loop(args, tray_icon, icons, stop_event, muted):
    while not stop_event.is_set():
        try:
            if muted.is_set():
                time.sleep(0.1)
                continue
            audio_data, fs = record_audio(ptt_key=args.ptt, tray_icon=tray_icon, icons=icons, muted=muted)
            if audio_data is None:
                if args.ptt:
                    time.sleep(0.1)
                    continue # Wait for next press if PTT
                else:
                    logging.info("No audio recorded.")
                    break

            temp_wav = save_temp_wav(audio_data, fs)
            logging.info("Transcribing...")
            if tray_icon and icons:
                tray_icon.icon = icons['transcribing']
            text = transcribe_audio(temp_wav)
            if tray_icon and icons:
                tray_icon.icon = icons['idle']
            logging.info(f"Transcribed text: {text}")
            type_text(text)
            os.unlink(temp_wav)
            logging.debug(f"Deleted temporary file {temp_wav}")
            
            if not args.ptt:
                break # In manual mode, we finish after one recording
        except KeyboardInterrupt:
            logging.info("Exiting transcription loop...")
            break
        except Exception as e:
            logging.error(f"Error: {e}")
            if not args.ptt:
                break
    
    if tray_icon:
        tray_icon.stop()

def main():
    parser = argparse.ArgumentParser(description="Record microphone and transcribe using Mistral AI")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--ptt", help="Use push-to-talk with the specified key (e.g., 'ctrl', 'alt', 'caps_lock')")
    args = parser.parse_args()

    setup_logging(args.verbose)

    icons = {
        'idle': create_idle_icon(),
        'recording': create_recording_icon(),
        'transcribing': create_transcribing_icon(),
        'muted': create_muted_icon()
    }

    muted = threading.Event()

    stop_event = threading.Event()

    def on_quit(icon, item):
        logging.info("Quit selected in tray menu.")
        stop_event.set()
        icon.stop()

    def on_mute(icon, item):
        if muted.is_set():
            muted.clear()
            icon.icon = icons['idle']
            logging.info("Unmuted.")
        else:
            muted.set()
            icon.icon = icons['muted']
            logging.info("Muted.")

    def get_mute_text(item):
        return "Unmute" if muted.is_set() else "Mute"

    menu = pystray.Menu(
        item(get_mute_text, on_mute),
        item('Quit', on_quit)
    )
    icon = pystray.Icon("Tyrant", icons['idle'], "Tyrant", menu)

    # Start transcription in a separate thread
    transcription_thread = threading.Thread(target=run_transcription_loop, args=(args, icon, icons, stop_event, muted))
    transcription_thread.daemon = True
    transcription_thread.start()

    # Run the tray icon (blocking call)
    try:
        icon.run()
    except KeyboardInterrupt:
        logging.info("Keyboard interrupt, exiting...")
        stop_event.set()
        icon.stop()

if __name__ == "__main__":
    main()
