# Tyrant

A simple application that records your microphone, transcribes the audio using Mistral AI's transcription API, and types the resulting text into your active window.

## Features

- **Push-To-Talk (PTT):** Record only when a specific key is held.
- **System Tray Icon:** Easy access to Mute/Unmute and Quit.
- **Pluggable Output, Transcription & Notification Methods:** Automatically detects available tools for typing, transcription, and system notifications.

## Prerequisites

- Python 3.x
- PortAudio (required for `sounddevice`, e.g., `sudo apt install libportaudio2`)
- `xdotool` (optional, for automatic typing on Linux/X11)
- `notify-send` (optional, for system notifications on Linux)
- Mistral API Key (optional, if using Mistral transcription)

## Installation

1. Clone the repository.
2. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

Create a `.env` file in the root directory and add your Mistral AI API key and optionally the model name. You can also provide a comma-separated list of context bias terms to help the transcriber prefer specific words (e.g., product names, acronyms):
```env
MISTRAL_API_KEY=your_api_key_here
MISTRAL_MODEL=voxtral-mini-2602
MISTRAL_CONTEXT_BIAS=Kubernetes,K8s,PostgreSQL
```

- `MISTRAL_CONTEXT_BIAS` is optional. When set, Tyrant passes these terms to Mistral as a context bias so the transcript is more likely to include them as spoken. Use a short, focused list; terms are case-sensitive and separated by commas.

### Whisper (Local) Configuration

When `faster-whisper` is installed, local transcription is used by default (no API key required). Configure it with optional `.env` variables:
```env
WHISPER_MODEL=base
WHISPER_DEVICE=auto
WHISPER_COMPUTE_TYPE=auto
```

- `WHISPER_MODEL`: Model size — `tiny`, `base`, `small`, `medium`, `large-v3` (default: `base`). Larger models are more accurate but slower and use more memory.
- `WHISPER_DEVICE`: `auto`, `cpu`, or `cuda` (default: `auto`).
- `WHISPER_COMPUTE_TYPE`: `auto`, `float16`, `int8`, `int8_float16` (default: `auto`).

The model is downloaded automatically on first use.

## Usage

Run the application:
```bash
python src/main.py
```

Options:
- `-v`, `--verbose`: Enable verbose logging.
- `--ptt KEY`: Use push-to-talk with the specified key (e.g., `ctrl`, `shift`, `caps_lock`).

### System Tray

When running, a tray icon appears showing the current status (Idle, Recording, Transcribing, Muted).
- **Right-click** the icon to Mute/Unmute or Quit the application.

### Recording Modes

1. **Manual (Default):**
   - Run `python src/main.py`.
   - Recording starts immediately.
   - Press `Ctrl+C` or use the tray menu to stop.

2. **Push-To-Talk (PTT):**
   - Run `python src/main.py --ptt caps_lock`.
   - The script waits for you to hold the specified key.
   - Recording starts when you press the key and stops when you release it.

## Output, Transcription & Notification Methods

The application uses a flexible system for output, transcription, and notifications, defined in `src/output.py`, `src/transcription.py`, and `src/notification.py`. It automatically selects the first available method for each.

### Forcing a Specific Module

You can force a specific module via environment variables. If the forced module is not available (missing dependencies, missing API key, etc.), Tyrant will exit with an error on startup.

```env
TRANSCRIPTION=whisper    # or: mistral, noop
OUTPUT=xdotool           # or: noop
NOTIFICATION=notify-send # or: noop
```

When these variables are not set, the first available module is used automatically (see priority order below).

### Output Methods
1.  **xdotool**: Uses `xdotool` to type text. (Requires `xdotool` installed).
2.  **noop**: A fallback that only logs the transcription if no typing tool is found.

### Transcription Methods
1.  **whisper**: Local transcription using [faster-whisper](https://github.com/SYSTRAN/faster-whisper). (Requires `faster-whisper` installed, no API key needed).
2.  **mistral**: Uses Mistral AI's API. (Requires `MISTRAL_API_KEY` in `.env`).
3.  **noop**: A fallback that returns a placeholder string if no transcription service is configured.

### Notification Methods
1.  **notify-send**: Uses `notify-send` to show system notifications. (Requires `libnotify-bin` or equivalent).
2.  **noop**: A fallback that only logs notifications if no notification tool is found.

### Implementing Custom Methods

You can easily add new methods by inheriting from the `Output`, `Transcription`, or `Notification` base classes and implementing the required interface (`is_available()` and `type(text)`, `transcribe(file_path)`, or `notify(title, message)`). Register the new class in the corresponding `*_MODULES` dict to make it available via the env var.

## Notes

- Ensure you have a window focused where you want the text to appear before the transcription finishes (if using `xdotool`).

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
