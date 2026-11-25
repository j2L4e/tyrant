import os
import sys
import time
import queue
import logging

from portal import get_portal, portal_supports, PortalError

PRESS = "press"
RELEASE = "release"


class Hotkey:
    """
    Interface for push-to-talk hotkey classes.
    Any implementation must provide 'is_available' and 'init'; it reports key
    events by calling '_emit(PRESS)' / '_emit(RELEASE)'.
    """

    def __init__(self):
        self._events = queue.Queue()

    def is_available(self) -> bool:
        """Check if the hotkey method is available on the current system."""
        raise NotImplementedError

    def init(self, key: str):
        """Start listening for the given key (pynput-style name, e.g. 'scroll_lock')."""
        raise NotImplementedError

    def close(self):
        """Stop listening."""
        pass

    def _emit(self, kind):
        self._events.put((kind, time.monotonic()))

    def wait(self, kind, stop_event=None, poll=0.1):
        """
        Block until an event of the given kind arrives and return its
        monotonic timestamp. Other events are discarded. Returns None if
        stop_event gets set first.
        """
        while not (stop_event and stop_event.is_set()):
            try:
                event_kind, timestamp = self._events.get(timeout=poll)
            except queue.Empty:
                continue
            if event_kind == kind:
                return timestamp
        return None


# pynput key names that don't map to an XKB keysym by capitalizing each word
_KEYSYM_EXCEPTIONS = {
    "print_screen": "Print",
    "page_up": "Prior",
    "page_down": "Next",
    "esc": "Escape",
    "enter": "Return",
}


def to_keysym_name(key: str) -> str:
    """Translate a pynput key name (e.g. 'scroll_lock') to an XKB keysym name ('Scroll_Lock')."""
    if len(key) == 1:
        return key
    if key in _KEYSYM_EXCEPTIONS:
        return _KEYSYM_EXCEPTIONS[key]
    return "_".join(part.capitalize() for part in key.split("_"))


class HotkeyPortal(Hotkey):
    """
    Hotkey implementation using the XDG GlobalShortcuts portal (Wayland).
    The desktop asks the user to confirm the shortcut on first use; the key
    can be changed later in the desktop's shortcut settings.
    """

    IFACE = "org.freedesktop.portal.GlobalShortcuts"
    SHORTCUT_ID = "ptt"

    def __init__(self):
        super().__init__()
        self._portal = None
        self._session = None

    def is_available(self) -> bool:
        return bool(os.getenv("WAYLAND_DISPLAY")) and portal_supports(self.IFACE)

    def init(self, key: str):
        from gi.repository import GLib

        self._portal = get_portal()
        if self._portal is None:
            raise PortalError("Desktop portal unavailable")
        self._session = self._portal.create_session(self.IFACE)
        self._portal.subscribe(self.IFACE, "Activated", self._on_activated)
        self._portal.subscribe(self.IFACE, "Deactivated", self._on_deactivated)

        trigger = to_keysym_name(key)
        results = self._portal.request(
            self.IFACE, "BindShortcuts",
            lambda token: GLib.Variant("(oa(sa{sv})sa{sv})", (
                self._session,
                [(self.SHORTCUT_ID, {
                    "description": GLib.Variant("s", "Tyrant push-to-talk"),
                    "preferred_trigger": GLib.Variant("s", trigger),
                })],
                "",
                {"handle_token": GLib.Variant("s", token)},
            )),
        )
        bound = dict(results.get("shortcuts", []))
        if self.SHORTCUT_ID not in bound:
            raise PortalError("Push-to-talk shortcut was not bound")
        assigned = bound[self.SHORTCUT_ID].get("trigger_description") or "unassigned"
        logging.info(f"Push-to-talk bound via portal (preferred '{trigger}', assigned: {assigned}).")

    def _on_activated(self, session, shortcut_id, _timestamp, _options):
        if session == self._session and shortcut_id == self.SHORTCUT_ID:
            self._emit(PRESS)

    def _on_deactivated(self, session, shortcut_id, _timestamp, _options):
        if session == self._session and shortcut_id == self.SHORTCUT_ID:
            self._emit(RELEASE)

    def close(self):
        if self._portal and self._session:
            self._portal.close_session(self._session)
            self._session = None


class HotkeyPynput(Hotkey):
    """
    Hotkey implementation using pynput (X11, Windows, macOS).
    """

    def __init__(self):
        super().__init__()
        self._listener = None
        self._key = None

    def is_available(self) -> bool:
        if sys.platform.startswith("linux") and not os.getenv("DISPLAY"):
            return False
        try:
            import pynput  # noqa: F401
            return True
        except Exception:
            return False

    def init(self, key: str):
        from pynput import keyboard

        self._key = key
        self._listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self._listener.start()
        logging.info(f"Push-to-talk listening for '{key}' via pynput.")

    @staticmethod
    def _key_name(key):
        try:
            return key.char  # single-char keys
        except AttributeError:
            return key.name  # special keys

    def _on_press(self, key):
        if self._key_name(key) == self._key:
            self._emit(PRESS)

    def _on_release(self, key):
        if self._key_name(key) == self._key:
            self._emit(RELEASE)

    def close(self):
        if self._listener:
            self._listener.stop()
            self._listener = None


HOTKEY_MODULES = {
    "portal": HotkeyPortal,
    "pynput": HotkeyPynput,
}


def use_hotkey(key, forced=None):
    """
    Return a started hotkey listener for the given key.
    Tries available methods in priority order, falling back to the next one
    if starting fails. If forced is set, use that module or raise an error.
    """
    if forced:
        forced = forced.lower()
        if forced not in HOTKEY_MODULES:
            raise RuntimeError(
                f"Unknown hotkey module '{forced}'. "
                f"Available: {', '.join(HOTKEY_MODULES)}"
            )
        instance = HOTKEY_MODULES[forced]()
        if not instance.is_available():
            raise RuntimeError(
                f"Hotkey module '{forced}' is not available. "
                f"Check its dependencies."
            )
        logging.info(f"Using {instance.__class__.__name__} for push-to-talk (forced).")
        instance.init(key)
        return instance

    hotkey_classes = [
        HotkeyPortal,
        HotkeyPynput,
    ]

    for cls in hotkey_classes:
        instance = cls()
        if not instance.is_available():
            continue
        try:
            instance.init(key)
        except Exception as e:
            logging.warning(f"{cls.__name__} failed to start: {e}")
            instance.close()
            continue
        logging.info(f"Using {cls.__name__} for push-to-talk.")
        return instance
    return None
