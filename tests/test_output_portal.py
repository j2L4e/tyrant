import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import tempfile

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from output import OutputPortal, OutputXdotool, keysym_for, use_output


class TestKeysym(unittest.TestCase):

    def test_ascii_and_latin1(self):
        self.assertEqual(keysym_for("a"), 0x61)
        self.assertEqual(keysym_for("Z"), 0x5A)
        self.assertEqual(keysym_for("ä"), 0xE4)
        self.assertEqual(keysym_for("ß"), 0xDF)

    def test_unicode(self):
        self.assertEqual(keysym_for("€"), 0x010020AC)

    def test_control_characters(self):
        self.assertEqual(keysym_for("\n"), 0xFF0D)
        self.assertEqual(keysym_for("\t"), 0xFF09)


class TestOutputPortal(unittest.TestCase):

    def setUp(self):
        self.state_dir = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"XDG_STATE_HOME": self.state_dir.name})
        self.env.start()
        self.portal = MagicMock()
        self.portal.create_session.return_value = "/session/rd"
        self.portal.request.side_effect = self._request
        self.start_results = {"devices": 1, "restore_token": "token-1"}
        self.get_portal = patch('output.get_portal', return_value=self.portal)
        self.get_portal.start()

    def tearDown(self):
        self.get_portal.stop()
        self.env.stop()
        self.state_dir.cleanup()

    def _request(self, iface, method, build_params):
        params = build_params("tok").unpack()
        if method == "SelectDevices":
            self.select_options = params[1]
            return {}
        return self.start_results

    def test_init_saves_restore_token_and_reuses_it(self):
        OutputPortal().init()
        self.assertNotIn("restore_token", self.select_options)
        self.assertEqual(self.select_options["types"], 1)
        self.assertEqual(self.select_options["persist_mode"], 2)

        OutputPortal().init()
        self.assertEqual(self.select_options["restore_token"], "token-1")

    def test_init_fails_without_keyboard(self):
        self.start_results = {"devices": 0}
        with self.assertRaises(RuntimeError):
            OutputPortal().init()
        self.portal.close_session.assert_called_once_with("/session/rd")

    def test_type_sends_keysym_press_and_release(self):
        out = OutputPortal()
        out.init()
        out.type("ä\n")
        sent = [c.args[2].unpack() for c in self.portal.call.call_args_list
                if c.args[1] == "NotifyKeyboardKeysym"]
        self.assertEqual(sent, [
            ("/session/rd", {}, 0xE4, 1), ("/session/rd", {}, 0xE4, 0),
            ("/session/rd", {}, 0xFF0D, 1), ("/session/rd", {}, 0xFF0D, 0),
        ])

    def test_type_reconnects_once_on_failure(self):
        out = OutputPortal()
        out.init()
        self.portal.call.side_effect = [RuntimeError("session closed"), None, None]
        out.type("a")
        self.assertEqual(self.portal.create_session.call_count, 2)

    def test_not_available_without_wayland(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(OutputPortal().is_available())


class TestUseOutputPortal(unittest.TestCase):

    @patch.object(OutputPortal, 'init')
    @patch.object(OutputPortal, 'is_available', return_value=True)
    def test_prefers_portal(self, *_mocks):
        self.assertIsInstance(use_output(), OutputPortal)

    @patch.object(OutputXdotool, 'is_available', return_value=True)
    @patch.object(OutputPortal, 'init', side_effect=RuntimeError("cancelled"))
    @patch.object(OutputPortal, 'is_available', return_value=True)
    def test_falls_back_to_xdotool(self, *_mocks):
        self.assertIsInstance(use_output(), OutputXdotool)


if __name__ == '__main__':
    unittest.main()
