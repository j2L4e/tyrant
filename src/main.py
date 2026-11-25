import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import tempfile
import os
from dotenv import load_dotenv
import time
import logging
import argparse
import threading
import pystray
from pystray import MenuItem as item
from tray import create_idle_icon, create_muted_icon, create_recording_icon, create_transcribing_icon
from output import use_output
from transcription import use_transcription
from notification import use_notification
from hotkey import use_hotkey, PRESS, RELEASE

MIN_PTT_DURATION = 2.0
MAX_ERROR_DELAY = 30

def setup_logging(verbose):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format='%(levelname)s: %(message)s')

load_dotenv()

def record_audio(fs=16000, hotkey=None, tray_icon=None, icons=None, muted=None, stop_event=None):
    """
    Records audio from the microphone.
    If hotkey is provided, it uses push-to-talk.
    Otherwise, it records until Ctrl+C.
    """
    recording = []

    def callback(indata, frames, time, status):
        if status:
            logging.warning(f"Audio status: {status}")
        recording.append(indata.copy())

    if hotkey:
        logging.info("Hold the push-to-talk key to record.")
        start_time = hotkey.wait(PRESS, stop_event)
        if start_time is None:
            return None, fs  # stopped while waiting
        if muted and muted.is_set():
            hotkey.wait(RELEASE, stop_event)
            return None, fs  # Don't record when muted

        logging.info("Recording started...")
        if tray_icon and icons:
            tray_icon.icon = icons['recording']
        try:
            with sd.InputStream(samplerate=fs, channels=1, callback=callback):
                end_time = hotkey.wait(RELEASE, stop_event)
        finally:
            if tray_icon and icons:
                tray_icon.icon = icons['idle']

        duration = (end_time or time.monotonic()) - start_time
        logging.info(f"Recording stopped. Duration: {duration:.2f}s")
        if duration <= MIN_PTT_DURATION:
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

def run_transcription_loop(args, tray_icon, icons, stop_event, muted, output, transcription, notification, hotkey=None):
    error_delay = 0
    while not stop_event.is_set():
        try:
            if muted.is_set() and not hotkey:
                time.sleep(0.1)
                continue
            audio_data, fs = record_audio(hotkey=hotkey, tray_icon=tray_icon, icons=icons, muted=muted, stop_event=stop_event)
            if audio_data is None:
                if hotkey:
                    continue # Wait for next press if PTT
                else:
                    logging.info("No audio recorded.")
                    break

            temp_wav = save_temp_wav(audio_data, fs)
            logging.info("Transcribing...")
            if tray_icon and icons:
                tray_icon.icon = icons['transcribing']
            text = transcription.transcribe(temp_wav)
            if tray_icon and icons:
                tray_icon.icon = icons['idle']
            logging.info(f"Transcribed text: {text}")
            output.type(text)
            os.unlink(temp_wav)
            logging.debug(f"Deleted temporary file {temp_wav}")
            error_delay = 0

            if not hotkey:
                break # In manual mode, we finish after one recording
        except KeyboardInterrupt:
            logging.info("Exiting transcription loop...")
            break
        except Exception as e:
            logging.error(f"{e}")
            if not hotkey:
                notification.notify("Error", f"{e}")
                break
            # Back off on repeated errors (e.g. audio not ready yet after login)
            # and only notify about the first one.
            if error_delay == 0:
                notification.notify("Error", f"{e}")
            error_delay = min(max(error_delay * 2, 1), MAX_ERROR_DELAY)
            logging.info(f"Retrying in {error_delay}s.")
            stop_event.wait(error_delay)
    
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

    output = use_output(os.getenv("OUTPUT"))
    transcription = use_transcription(os.getenv("TRANSCRIPTION"))
    notification = use_notification(os.getenv("NOTIFICATION"))

    hotkey = None
    if args.ptt:
        hotkey = use_hotkey(args.ptt, os.getenv("HOTKEY"))
        if hotkey is None:
            raise RuntimeError("No push-to-talk method available on this system.")

    # Start transcription in a separate thread
    transcription_thread = threading.Thread(target=run_transcription_loop, args=(args, icon, icons, stop_event, muted, output, transcription, notification, hotkey))
    transcription_thread.daemon = True
    transcription_thread.start()

    # Run the tray icon (blocking call)
    try:
        icon.run()
    except KeyboardInterrupt:
        logging.info("Keyboard interrupt, exiting...")
        stop_event.set()
        icon.stop()
    finally:
        if hotkey:
            hotkey.close()

if __name__ == "__main__":
    main()
