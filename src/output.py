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


OUTPUT_MODULES = {
    "xdotool": OutputXdotool,
    "noop": OutputNoop,
}


def use_output(forced=None):
    """
    Check for available output methods and return the first one found.
    If forced is set, use that module or raise an error.
    """
    if forced:
        forced = forced.lower()
        if forced not in OUTPUT_MODULES:
            raise RuntimeError(
                f"Unknown output module '{forced}'. "
                f"Available: {', '.join(OUTPUT_MODULES)}"
            )
        instance = OUTPUT_MODULES[forced]()
        if not instance.is_available():
            raise RuntimeError(
                f"Output module '{forced}' is not available. "
                f"Check its dependencies."
            )
        logging.info(f"Using {instance.__class__.__name__} for output (forced).")
        return instance

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
