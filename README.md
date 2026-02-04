# Tyrant

A simple application that records your microphone, transcribes the audio using Mistral AI's transcription API, and types the resulting text into your active window using `xdotool`.

## Prerequisites

- Python 3.x
- `xdotool` (install via your package manager, e.g., `sudo apt install xdotool`)
- PortAudio (required for `sounddevice`, e.g., `sudo apt install libportaudio2`)

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

### Recording Modes

1. **Manual (Default):**
   - Run `python src/main.py`.
   - Recording starts immediately.
   - Press `Ctrl+C` to stop.

2. **Push-To-Talk (PTT):**
   - Run `python src/main.py --ptt caps_lock`.
   - The script waits for you to hold the specified key.
   - Recording starts when you press the key and stops when you release it.

## Notes

- The default model used is `voxtral-mini-transcribe-2507`. You can override it by setting the `MODEL` environment variable.
- Ensure you have a window focused where you want the text to appear before the transcription finishes.
