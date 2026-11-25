import os
import subprocess
import shutil
import logging

from portal import get_portal, portal_supports, PortalError


class Output:
    """
    Interface for output classes.
    Any implementation must provide 'is_available' and 'type' methods.
    """

    def is_available(self) -> bool:
        """Check if the output method is available on the current system."""
        raise NotImplementedError

    def init(self):
        """Initialize the output method (e.g., request permissions)."""
        pass

    def type(self, text: str):
        """Type the given text."""
        raise NotImplementedError


def keysym_for(ch: str) -> int:
    """Map a character to an X keysym (layout independent)."""
    if ch == "\n":
        return 0xFF0D  # Return
    if ch == "\t":
        return 0xFF09  # Tab
    cp = ord(ch)
    if 0x20 <= cp <= 0x7E or 0xA0 <= cp <= 0xFF:
        return cp  # Latin-1 keysyms equal their code point
    return 0x01000000 + cp  # Unicode keysym


def token_path():
    state_home = os.getenv("XDG_STATE_HOME", os.path.expanduser("~/.local/state"))
    return os.path.join(state_home, "tyrant", "remote_desktop_token")


class OutputPortal(Output):
    """
    Output implementation using the XDG RemoteDesktop portal (Wayland).
    Sends keysyms, so the text comes out right regardless of keyboard layout.
    The desktop asks for permission once; a restore token skips the prompt
    on later starts.
    """

    IFACE = "org.freedesktop.portal.RemoteDesktop"
    DEVICE_KEYBOARD = 1
    PERSIST_UNTIL_REVOKED = 2

    def __init__(self):
        self._portal = None
        self._session = None

    def is_available(self) -> bool:
        return bool(os.getenv("WAYLAND_DISPLAY")) and portal_supports(self.IFACE)

    def init(self):
        from gi.repository import GLib

        self._portal = get_portal()
        if self._portal is None:
            raise PortalError("Desktop portal unavailable")
        session = self._portal.create_session(self.IFACE)

        options = {
            "types": GLib.Variant("u", self.DEVICE_KEYBOARD),
            "persist_mode": GLib.Variant("u", self.PERSIST_UNTIL_REVOKED),
        }
        restore_token = self._load_token()
        if restore_token:
            options["restore_token"] = GLib.Variant("s", restore_token)

        self._portal.request(self.IFACE, "SelectDevices", lambda token: GLib.Variant(
            "(oa{sv})", (session, {**options, "handle_token": GLib.Variant("s", token)})))
        results = self._portal.request(self.IFACE, "Start", lambda token: GLib.Variant(
            "(osa{sv})", (session, "", {"handle_token": GLib.Variant("s", token)})))

        if not results.get("devices", 0) & self.DEVICE_KEYBOARD:
            self._portal.close_session(session)
            raise PortalError("Keyboard access was not granted")
        if results.get("restore_token"):
            self._save_token(results["restore_token"])
        self._session = session

    @staticmethod
    def _load_token():
        try:
            with open(token_path()) as f:
                return f.read().strip() or None
        except OSError:
            return None

    @staticmethod
    def _save_token(token):
        path = token_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(token)
        except OSError as e:
            logging.warning(f"Could not save remote desktop restore token: {e}")

    def _send(self, text):
        from gi.repository import GLib

        for ch in text:
            keysym = keysym_for(ch)
            for state in (1, 0):  # press, release
                self._portal.call(self.IFACE, "NotifyKeyboardKeysym", GLib.Variant(
                    "(oa{sv}iu)", (self._session, {}, keysym, state)))

    def type(self, text: str):
        logging.info(f"Typing with portal: {text}")
        if self._session is None:
            self.init()
        try:
            self._send(text)
        except Exception as e:
            # Session may have been closed (e.g. permission revoked); retry once
            logging.warning(f"Remote desktop session failed ({e}), reconnecting.")
            self._session = None
            self.init()
            self._send(text)


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
    "portal": OutputPortal,
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
        instance.init()
        return instance

    output_classes = [
        OutputPortal,
        OutputXdotool,
        OutputNoop
    ]

    for cls in output_classes:
        instance = cls()
        if not instance.is_available():
            continue
        try:
            instance.init()
        except Exception as e:
            logging.warning(f"{cls.__name__} failed to start: {e}")
            continue
        logging.info(f"Using {cls.__name__} for output.")
        return instance
    return None
