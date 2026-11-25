"""
Shared access to XDG desktop portals over D-Bus (used for Wayland support).

All portal signals are dispatched on a private GLib main loop running in a
daemon thread, so callers can block on results from any thread without
interfering with the tray icon's own event loop.
"""
import os
import sys
import uuid
import logging
import threading

APP_ID = "tyrant"
BUS_NAME = "org.freedesktop.portal.Desktop"
OBJECT_PATH = "/org/freedesktop/portal/desktop"
REQUEST_IFACE = "org.freedesktop.portal.Request"
SESSION_IFACE = "org.freedesktop.portal.Session"
REGISTRY_IFACE = "org.freedesktop.host.portal.Registry"

try:
    from gi.repository import Gio, GLib
except ImportError:  # PyGObject missing: portals are simply unavailable
    Gio = GLib = None


class PortalError(RuntimeError):
    pass


def desktop_file_path():
    data_home = os.getenv("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    return os.path.join(data_home, "applications", f"{APP_ID}.desktop")


def ensure_desktop_file():
    """
    Host (non-Flatpak) apps need a desktop file matching their app id,
    otherwise the portal refuses to register it.
    """
    path = desktop_file_path()
    if os.path.exists(path):
        return path
    main_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=Tyrant\n"
            "Comment=Speech-to-text dictation\n"
            f"Exec={sys.executable} {main_py}\n"
            "Icon=audio-input-microphone\n"
            "Terminal=false\n"
            "NoDisplay=true\n"
        )
    logging.info(f"Created desktop file {path}")
    return path


class Portal:
    """A private session bus connection to the desktop portal."""

    def __init__(self):
        if Gio is None:
            raise PortalError("PyGObject is not installed")
        address = Gio.dbus_address_get_for_bus_sync(Gio.BusType.SESSION, None)
        self.conn = Gio.DBusConnection.new_for_address_sync(
            address,
            Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
            | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
            None, None,
        )
        self._sender = self.conn.get_unique_name()[1:].replace(".", "_")
        self._context = GLib.MainContext()
        self._loop = GLib.MainLoop(self._context)
        self._thread = threading.Thread(target=self._run, name="portal", daemon=True)
        self._thread.start()
        self._register_app_id()

    def _run(self):
        self._context.push_thread_default()
        self._loop.run()

    def _invoke(self, fn):
        """Run fn on the portal loop thread and return its result."""
        done = threading.Event()
        result = {}

        def wrapper(*_user_data):
            try:
                result["value"] = fn()
            except Exception as e:
                result["error"] = e
            finally:
                done.set()
            return False

        source = GLib.idle_source_new()
        source.set_callback(wrapper)
        source.attach(self._context)
        done.wait()
        if "error" in result:
            raise result["error"]
        return result.get("value")

    def _register_app_id(self):
        if self.version(REGISTRY_IFACE) is None:
            return
        try:
            ensure_desktop_file()
            self.call(REGISTRY_IFACE, "Register", GLib.Variant("(sa{sv})", (APP_ID, {})))
            logging.debug(f"Registered portal app id '{APP_ID}'")
        except (GLib.Error, OSError) as e:
            # e.g. the app id was already derived from the systemd unit
            logging.warning(f"Could not register portal app id: {e}")

    def version(self, iface):
        """Return the portal interface version, or None if it is not offered."""
        try:
            reply = self.conn.call_sync(
                BUS_NAME, OBJECT_PATH, "org.freedesktop.DBus.Properties", "Get",
                GLib.Variant("(ss)", (iface, "version")),
                GLib.VariantType("(v)"), Gio.DBusCallFlags.NONE, 5000, None,
            )
            return reply.unpack()[0]
        except GLib.Error:
            return None

    def call(self, iface, method, params, timeout_ms=5000):
        return self.conn.call_sync(
            BUS_NAME, OBJECT_PATH, iface, method, params,
            None, Gio.DBusCallFlags.NONE, timeout_ms, None,
        )

    def subscribe(self, iface, signal, callback):
        """Call callback(*args) on the portal thread whenever signal fires."""
        def on_signal(_conn, _sender, _path, _iface, _signal, params):
            try:
                callback(*params.unpack())
            except Exception:
                logging.exception(f"Error handling portal signal {signal}")

        return self._invoke(lambda: self.conn.signal_subscribe(
            BUS_NAME, iface, signal, OBJECT_PATH, None,
            Gio.DBusSignalFlags.NONE, on_signal,
        ))

    def request(self, iface, method, build_params, timeout=300):
        """
        Call a portal method that answers via a Request object and wait for
        its Response. build_params receives the handle token to put into the
        method's options. Returns the results dict.
        """
        token = "tyrant_" + uuid.uuid4().hex[:12]
        handle = f"{OBJECT_PATH}/request/{self._sender}/{token}"
        done = threading.Event()
        response = {}

        def on_response(_conn, _sender, _path, _iface, _signal, params):
            response["code"], response["results"] = params.unpack()
            done.set()

        sub = self._invoke(lambda: self.conn.signal_subscribe(
            BUS_NAME, REQUEST_IFACE, "Response", handle, None,
            Gio.DBusSignalFlags.NO_MATCH_RULE, on_response,
        ))
        try:
            self.call(iface, method, build_params(token))
            if not done.wait(timeout):
                raise PortalError(f"{method}: no response from portal within {timeout}s")
        finally:
            self._invoke(lambda: self.conn.signal_unsubscribe(sub))
        if response["code"] == 1:
            raise PortalError(f"{method}: cancelled by user")
        if response["code"] != 0:
            raise PortalError(f"{method}: failed (response code {response['code']})")
        return response["results"]

    def create_session(self, iface):
        results = self.request(iface, "CreateSession", lambda t: GLib.Variant("(a{sv})", ({
            "handle_token": GLib.Variant("s", t),
            "session_handle_token": GLib.Variant("s", "tyrant_" + uuid.uuid4().hex[:12]),
        },)))
        return results["session_handle"]

    def close_session(self, session_handle):
        try:
            self.conn.call_sync(
                BUS_NAME, session_handle, SESSION_IFACE, "Close", None,
                None, Gio.DBusCallFlags.NONE, 5000, None,
            )
        except GLib.Error as e:
            logging.debug(f"Closing portal session failed: {e}")


_portal = None
_portal_lock = threading.Lock()


def get_portal():
    """Return the shared Portal connection, or None if D-Bus is unavailable."""
    global _portal
    with _portal_lock:
        if _portal is None:
            try:
                _portal = Portal()
            except Exception as e:
                logging.debug(f"Desktop portal unavailable: {e}")
                return None
        return _portal


def portal_supports(iface):
    """True if the desktop portal offers the given interface."""
    portal = get_portal()
    return portal is not None and portal.version(iface) is not None
