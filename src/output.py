import subprocess
import shutil
import logging


class Output:
    """
    Interface for output classes.
    Any implementation must provide 'is_available' and 'type' methods.
    """

    def is_available(self) -> bool:
        """Check if the output method is available on the current system."""
        raise NotImplementedError

    def type(self, text: str):
        """Type the given text."""
        raise NotImplementedError


class OutputXdotool(Output):
    """
    Output implementation using xdotool.
    """

    def is_available(self) -> bool:
        return shutil.which('xdotool') is not None

    def type(self, text: str):
        logging.info(f"Typing with xdotool: {text}")
        subprocess.run(['xdotool', 'type', '--clearmodifiers', text])


class OutputNoop(Output):
    """
    Dummy Output implementation.
    """

    def is_available(self) -> bool:
        return True

    def type(self, text: str):
        logging.info(f"Typing with noop: {text}")


def first_available_output():
    """
    Check for available output methods and return the first one found.
    Returns None if no output method is available.
    """
    output_classes = [
        OutputXdotool,
        OutputNoop
    ]

    for cls in output_classes:
        instance = cls()
        if instance.is_available():
            logging.info(f"Using {cls.__name__} for output.")
            return instance
    return None
