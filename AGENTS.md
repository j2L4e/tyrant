# AGENTS.md

This file provides guidance to coding agents when working with code in this repository.

## Project

Tyrant is a speech-to-text dictation app. It's aim is being cross-OS but existing modules are for linux. It records microphone audio, transcribes it (locally via faster-whisper or remotely via Mistral AI), and types the result into the active window using xdotool. It runs a system tray icon for status and supports push-to-talk mode.

## Commands

```bash
# Run
python src/main.py                        # manual mode (record once)
python src/main.py --ptt caps_lock        # push-to-talk mode
python src/main.py --verbose              # debug logging

# Test (unittest, not pytest)
python -m unittest discover tests -v      # all tests
python -m unittest tests.test_main -v     # single file
python -m unittest tests.test_main.TestDictate.test_record_audio_ppt_short -v  # single test

# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

No linter or formatter is configured.

## Architecture

All source lives in `src/`. There is no package structure — modules import each other directly via `sys.path` manipulation.

**Pluggable module system**: Output, transcription, and notification each follow the same pattern:
- Abstract base class with `is_available()` and one action method
- Concrete implementations registered in a `*_MODULES` dict with priority ordering
- `use_*()` factory function that auto-selects the first available or forces one via env var (`TRANSCRIPTION`, `OUTPUT`, `NOTIFICATION`)

| Module | Implementations (by priority) |
|---|---|
| `transcription.py` | `whisper` (local faster-whisper) → `mistral` (API) → `noop` |
| `output.py` | `xdotool` → `noop` |
| `notification.py` | `notify-send` → `noop` |

**Threading model**: Main thread runs the pystray tray icon event loop (blocking). A daemon thread runs `run_transcription_loop()` which handles recording → transcription → output. Muting is coordinated via `threading.Event`.

**Audio**: Records at 16 kHz mono via sounddevice, saves to temp WAV files. PTT mode uses pynput keyboard listener and filters recordings under 2 seconds.

## Testing

Uses `unittest` with `unittest.mock`. All external dependencies (sounddevice, pynput, subprocess, Mistral API) are patched. Test files add `src/` to `sys.path` manually.

## Configuration

Via `.env` file (loaded by python-dotenv). See `.env.example` for all options. Key vars: `MISTRAL_API_KEY`, `WHISPER_MODEL`, `MISTRAL_CONTEXT_BIAS`.
