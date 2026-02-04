# Tyrant

A simple application that records your microphone, transcribes the audio using Mistral AI's transcription API, and types the resulting text into your active window.

## Features

- **Push-To-Talk (PTT):** Record only when a specific key is held.
- **System Tray Icon:** Easy access to Mute/Unmute and Quit.
- **Pluggable Output & Transcription Methods:** Automatically detects available tools for typing and transcription.

## Prerequisites

- Python 3.x
- PortAudio (required for `sounddevice`, e.g., `sudo apt install libportaudio2`)
- `xdotool` (optional, for automatic typing on Linux/X11)
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

Create a `.env` file in the root directory and add your Mistral AI API key and optionally the model name:
```env
MISTRAL_API_KEY=your_api_key_here
MODEL_NAME=voxtral-mini-transcribe-2507
```

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

## Output & Transcription Methods

The application uses a flexible system for both output and transcription, defined in `src/output.py` and `src/transcription.py`. It automatically selects the first available method for each:

### Output Methods
1.  **OutputXdotool**: Uses `xdotool` to type text. (Requires `xdotool` installed).
2.  **OutputNoop**: A fallback that only logs the transcription if no typing tool is found.

### Transcription Methods
1.  **TranscriptionMistral**: Uses Mistral AI's API. (Requires `MISTRAL_API_KEY` in `.env`).
2.  **TranscriptionNoop**: A fallback that returns a placeholder string if no transcription service is configured.

### Implementing Custom Methods

You can easily add new methods by inheriting from the `Output` or `Transcription` base classes and implementing the required interface (`is_available()` and `type(text)` or `transcribe(file_path)`).

## Notes

- The default model used is `voxtral-mini-transcribe-2507`.
- Ensure you have a window focused where you want the text to appear before the transcription finishes (if using `xdotool`).
