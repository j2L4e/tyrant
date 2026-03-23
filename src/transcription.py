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

    def transcribe(self, file_path: str) -> str:
        """Transcribe the given audio file."""
        raise NotImplementedError


class TranscriptionMistral(Transcription):
    """
    Transcription implementation using Mistral AI API.
    """

    def __init__(self, api_key: str = None, model_name: str = None):
        self.api_key = api_key or os.getenv("MISTRAL_API_KEY")
        self.model_name = model_name or os.getenv("MISTRAL_MODEL")

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
                )
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


def first_available_transcription():
    """
    Check for available transcription methods and return the first one found.
    """
    transcription_classes = [
        TranscriptionMistral,
        TranscriptionNoop
    ]

    for cls in transcription_classes:
        instance = cls()
        if instance.is_available():
            logging.info(f"Using {cls.__name__} for transcription.")
            return instance
    return None
