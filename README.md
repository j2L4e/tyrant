# Mistral Dictate

A simple application that records your microphone, transcribes the audio using Mistral AI's transcription API, and types the resulting text into your active window using `xdotool`.

## Prerequisites

- Python 3.x
- `xdotool` (install via your package manager, e.g., `sudo apt install xdotool`)
- PortAudio (required for `sounddevice`, e.g., `sudo apt install libportaudio2`)

## Installation

1. Clone the repository.
2. Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

Create a `.env` file in the root directory and add your Mistral AI API key:
```env
MISTRAL_API_KEY=your_api_key_here
```

## Usage

Run the application:
```bash
python src/main.py
```

Options:
- `-v`, `--verbose`: Enable verbose logging to see debug information (e.g., API requests and temporary file paths).

- The script will start recording. 
- Speak into your microphone.
- Press `Ctrl+C` to stop recording.
- The transcription will be sent to Mistral AI.
- Once the transcription is received, it will be typed into your currently focused window using `xdotool`.

## Notes

- The default model used is `mistral-embed`. You may need to update `MODEL_NAME` in `src/main.py` if Mistral releases a specific "Voxtral" model identifier.
- Ensure you have a window focused where you want the text to appear before the transcription finishes.
