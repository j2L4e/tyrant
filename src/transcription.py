import os
import logging
from mistralai import Mistral
from mistralai.models import File


class Transcription:
    """
    Interface for transcription classes.
    Any implementation must provide 'is_available' and 'transcribe' methods.
    """

    def is_available(self) -> bool:
        """Check if the transcription method is available and configured."""
        raise NotImplementedError

    def init(self):
        """Initialize the transcription method (e.g., download models)."""
        pass

    def transcribe(self, file_path: str) -> str:
        """Transcribe the given audio file."""
        raise NotImplementedError


class TranscriptionWhisper(Transcription):
    """
    Transcription implementation using faster-whisper for local inference.
    """

    def __init__(self):
        self.model_size = os.getenv("WHISPER_MODEL", "base")
        self.device = os.getenv("WHISPER_DEVICE", "auto")
        self.compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "auto")
        self._model = None

    def is_available(self) -> bool:
        try:
            import faster_whisper  # noqa: F401
            return True
        except ImportError:
            return False

    def _load_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel
            from faster_whisper.utils import download_model
            try:
                download_model(self.model_size, local_files_only=True)
            except Exception:
                logging.info(f"Downloading Whisper model '{self.model_size}'...")
            logging.info(
                f"Loading Whisper model '{self.model_size}' "
                f"(device={self.device}, compute_type={self.compute_type})"
            )
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            logging.info(f"Whisper model '{self.model_size}' ready.")

    def init(self):
        self._load_model()

    def transcribe(self, file_path: str) -> str:
        import numpy as np
        import scipy.io.wavfile as wavfile
        sample_rate, audio_data = wavfile.read(file_path)
        if not np.issubdtype(audio_data.dtype, np.floating):
            audio_data = audio_data.astype(np.float32) / np.iinfo(audio_data.dtype).max
        segments, info = self._model.transcribe(audio_data, beam_size=5)
        text = "".join(segment.text for segment in segments).strip()
        logging.debug(
            f"Whisper transcription (lang={info.language}, "
            f"prob={info.language_probability:.2f}): {text}"
        )
        return text


class TranscriptionMistral(Transcription):
    """
    Transcription implementation using Mistral AI API.
    """

    def __init__(self, api_key: str = None, model_name: str = None):
        self.api_key = api_key or os.getenv("MISTRAL_API_KEY")
        self.model_name = model_name or os.getenv("MISTRAL_MODEL")
        self.context_bias = os.getenv("MISTRAL_CONTEXT_BIAS").split(",") if os.getenv("MISTRAL_CONTEXT_BIAS") else []

    def is_available(self) -> bool:
        return bool(self.api_key)

    def transcribe(self, file_path: str) -> str:
        if not self.api_key:
            raise ValueError("MISTRAL_API_KEY not found")

        logging.debug(f"Sending request to Mistral API for file: {file_path}")
        client = Mistral(api_key=self.api_key)

        with open(file_path, 'rb') as f:
            response = client.audio.transcriptions.complete(
                model=self.model_name,
                file=File(
                    content=f.read(),
                    file_name=os.path.basename(file_path),
                ),
                context_bias=self.context_bias
            )

        logging.debug(f"API Response: {response}")
        replacements = {
            " slash ": "/",
            " dot ": ".",
            " dash ": "-",
            " underscore ": "_",
            " asterisk ": "*",
            " plus ": "+",
            " equals ": "=",
        }

        text = response.text
        for old, new in replacements.items():
            text = text.replace(old, new)

        return text
class TranscriptionNoop(Transcription):
    """
    Dummy Transcription implementation.
    """

    def is_available(self) -> bool:
        return True

    def transcribe(self, file_path: str) -> str:
        logging.info(f"Transcription noop for: {file_path}")
        return "[No transcription available]"


TRANSCRIPTION_MODULES = {
    "whisper": TranscriptionWhisper,
    "mistral": TranscriptionMistral,
    "noop": TranscriptionNoop,
}


def use_transcription(forced=None):
    """
    Check for available transcription methods and return the first one found.
    If forced is set, use that module or raise an error.
    """
    if forced:
        forced = forced.lower()
        if forced not in TRANSCRIPTION_MODULES:
            raise RuntimeError(
                f"Unknown transcription module '{forced}'. "
                f"Available: {', '.join(TRANSCRIPTION_MODULES)}"
            )
        instance = TRANSCRIPTION_MODULES[forced]()
        if not instance.is_available():
            raise RuntimeError(
                f"Transcription module '{forced}' is not available. "
                f"Check its dependencies."
            )
        logging.info(f"Using {instance.__class__.__name__} for transcription (forced).")
        instance.init()
        return instance

    transcription_classes = [
        TranscriptionWhisper,
        TranscriptionMistral,
        TranscriptionNoop
    ]

    for cls in transcription_classes:
        instance = cls()
        if instance.is_available():
            logging.info(f"Using {cls.__name__} for transcription.")
            instance.init()
            return instance
    return None
