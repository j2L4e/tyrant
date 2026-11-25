import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import threading

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from hotkey import (Hotkey, HotkeyPortal, HotkeyPynput, use_hotkey, to_keysym_name,
                    PRESS, RELEASE)


class TestHotkeyBase(unittest.TestCase):

    def test_wait_returns_timestamp_of_matching_event(self):
        hotkey = Hotkey()
        hotkey._events.put((RELEASE, 1.0))  # stray release is skipped
        hotkey._events.put((PRESS, 2.0))
        self.assertEqual(hotkey.wait(PRESS, poll=0.01), 2.0)

    def test_wait_returns_none_when_stopped(self):
        stop_event = threading.Event()
        stop_event.set()
        self.assertIsNone(Hotkey().wait(PRESS, stop_event, poll=0.01))

    def test_to_keysym_name(self):
        self.assertEqual(to_keysym_name("scroll_lock"), "Scroll_Lock")
        self.assertEqual(to_keysym_name("caps_lock"), "Caps_Lock")
        self.assertEqual(to_keysym_name("f13"), "F13")
        self.assertEqual(to_keysym_name("pause"), "Pause")
        self.assertEqual(to_keysym_name("print_screen"), "Print")
        self.assertEqual(to_keysym_name("a"), "a")


class TestHotkeyPortal(unittest.TestCase):

    def _bound_hotkey(self):
        portal = MagicMock()
        portal.create_session.return_value = "/session/1"
        portal.request.return_value = {
            "shortcuts": [("ptt", {"trigger_description": "Scroll Lock"})]
        }
        with patch('hotkey.get_portal', return_value=portal):
            hotkey = HotkeyPortal()
            hotkey.init("scroll_lock")
        return hotkey, portal

    def test_init_binds_shortcut_with_preferred_trigger(self):
        hotkey, portal = self._bound_hotkey()
        iface, method, build_params = portal.request.call_args.args
        self.assertEqual(method, "BindShortcuts")
        session, shortcuts, _parent, options = build_params("tok").unpack()
        self.assertEqual(session, "/session/1")
        self.assertEqual(shortcuts[0][0], "ptt")
        self.assertEqual(shortcuts[0][1]["preferred_trigger"], "Scroll_Lock")
        self.assertEqual(options["handle_token"], "tok")

    def test_signals_become_press_and_release(self):
        hotkey, portal = self._bound_hotkey()
        handlers = {c.args[1]: c.args[2] for c in portal.subscribe.call_args_list}
        handlers["Activated"]("/session/other", "ptt", 0, {})  # other session: ignored
        handlers["Activated"]("/session/1", "ptt", 0, {})
        handlers["Deactivated"]("/session/1", "ptt", 0, {})
        self.assertEqual(hotkey._events.get_nowait()[0], PRESS)
        self.assertEqual(hotkey._events.get_nowait()[0], RELEASE)
        self.assertTrue(hotkey._events.empty())

    def test_init_fails_if_not_bound(self):
        portal = MagicMock()
        portal.request.return_value = {"shortcuts": []}
        with patch('hotkey.get_portal', return_value=portal):
            with self.assertRaises(RuntimeError):
                HotkeyPortal().init("scroll_lock")

    def test_close_closes_session(self):
        hotkey, portal = self._bound_hotkey()
        hotkey.close()
        portal.close_session.assert_called_once_with("/session/1")

    def test_not_available_without_wayland(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(HotkeyPortal().is_available())


class TestHotkeyPynput(unittest.TestCase):

    def test_matching_key_emits_events(self):
        hotkey = HotkeyPynput()
        hotkey._key = "scroll_lock"
        key = MagicMock(spec=["name"])
        key.name = "scroll_lock"
        other = MagicMock(spec=["name"])
        other.name = "ctrl"
        hotkey._on_press(other)
        hotkey._on_press(key)
        hotkey._on_release(key)
        self.assertEqual(hotkey._events.get_nowait()[0], PRESS)
        self.assertEqual(hotkey._events.get_nowait()[0], RELEASE)
        self.assertTrue(hotkey._events.empty())

    def test_not_available_on_linux_without_display(self):
        with patch.dict(os.environ, {}, clear=True), patch('hotkey.sys.platform', 'linux'):
            self.assertFalse(HotkeyPynput().is_available())


class TestUseHotkey(unittest.TestCase):

    @patch.object(HotkeyPynput, 'init')
    @patch.object(HotkeyPynput, 'is_available', return_value=True)
    @patch.object(HotkeyPortal, 'init')
    @patch.object(HotkeyPortal, 'is_available', return_value=True)
    def test_prefers_portal(self, *_mocks):
        self.assertIsInstance(use_hotkey("scroll_lock"), HotkeyPortal)

    @patch.object(HotkeyPynput, 'init')
    @patch.object(HotkeyPynput, 'is_available', return_value=True)
    @patch.object(HotkeyPortal, 'init', side_effect=RuntimeError("cancelled"))
    @patch.object(HotkeyPortal, 'is_available', return_value=True)
    def test_falls_back_when_portal_fails(self, *_mocks):
        self.assertIsInstance(use_hotkey("scroll_lock"), HotkeyPynput)

    @patch.object(HotkeyPynput, 'init')
    @patch.object(HotkeyPynput, 'is_available', return_value=True)
    @patch.object(HotkeyPortal, 'is_available', return_value=False)
    def test_uses_pynput_on_x11(self, *_mocks):
        self.assertIsInstance(use_hotkey("scroll_lock"), HotkeyPynput)

    @patch.object(HotkeyPortal, 'init', side_effect=RuntimeError("cancelled"))
    @patch.object(HotkeyPortal, 'is_available', return_value=True)
    def test_forced_does_not_fall_back(self, *_mocks):
        with self.assertRaises(RuntimeError):
            use_hotkey("scroll_lock", forced="portal")

    def test_forced_unknown(self):
        with self.assertRaises(RuntimeError):
            use_hotkey("scroll_lock", forced="nope")


if __name__ == '__main__':
    unittest.main()
