import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import numpy as np
import time
import threading

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import main
from output import Output, OutputXdotool, use_output
from transcription import (Transcription, TranscriptionMistral, TranscriptionWhisper,
                           TranscriptionWhisperCpp, use_transcription)

class TestDictate(unittest.TestCase):

    def _fake_hotkey(self, hold_seconds, on_recording=None):
        """A hotkey that is pressed once and released after hold_seconds."""
        from hotkey import Hotkey, PRESS, RELEASE

        hotkey = Hotkey()
        now = time.monotonic()
        hotkey._events.put((PRESS, now))
        original_wait = hotkey.wait

        def wait(kind, stop_event=None, poll=0.01):
            if kind == RELEASE:
                if on_recording:
                    on_recording()
                hotkey._events.put((RELEASE, now + hold_seconds))
            return original_wait(kind, stop_event, poll)

        hotkey.wait = wait
        return hotkey

    @patch('main.sd.InputStream')
    def test_record_audio_ptt_short(self, mock_input_stream):
        audio_data, fs = main.record_audio(hotkey=self._fake_hotkey(1.0))
        self.assertIsNone(audio_data)

    @patch('main.sd.InputStream')
    def test_record_audio_ptt_long(self, mock_input_stream):
        callback_container = [None]

        def mock_input_stream_side_effect(**kwargs):
            callback_container[0] = kwargs.get('callback')
            return MagicMock()
        mock_input_stream.side_effect = mock_input_stream_side_effect

        def feed_audio():
            for _ in range(5):
                callback_container[0](np.zeros((100, 1)), 100, None, None)

        audio_data, fs = main.record_audio(hotkey=self._fake_hotkey(2.5, feed_audio))
        self.assertIsNotNone(audio_data)
        self.assertEqual(len(audio_data), 500)
        mock_input_stream.assert_called_once()

    @patch('main.sd.InputStream')
    def test_record_audio_ptt_muted(self, mock_input_stream):
        muted = threading.Event()
        muted.set()
        audio_data, fs = main.record_audio(hotkey=self._fake_hotkey(3.0), muted=muted)
        self.assertIsNone(audio_data)
        mock_input_stream.assert_not_called()

    @patch('main.sd.InputStream')
    def test_record_audio_ptt_stopped(self, mock_input_stream):
        from hotkey import Hotkey
        stop_event = threading.Event()
        stop_event.set()
        audio_data, fs = main.record_audio(hotkey=Hotkey(), stop_event=stop_event)
        self.assertIsNone(audio_data)
        mock_input_stream.assert_not_called()

    @patch('main.record_audio')
    def test_loop_backs_off_and_notifies_once(self, mock_record):
        stop_event = threading.Event()
        calls = []

        def failing_record(**kwargs):
            calls.append(1)
            if len(calls) >= 3:
                stop_event.set()
            raise RuntimeError("Invalid sample rate")
        mock_record.side_effect = failing_record

        notification = MagicMock()
        args = MagicMock(ptt='scroll_lock')
        with patch.object(stop_event, 'wait') as mock_wait:
            main.run_transcription_loop(args, None, None, stop_event, threading.Event(),
                                        MagicMock(), MagicMock(), notification, hotkey=MagicMock())

        self.assertEqual(notification.notify.call_count, 1)
        self.assertEqual([c.args[0] for c in mock_wait.call_args_list], [1, 2, 4])

    @patch('transcription.Mistral')
    def test_transcribe_audio(self, mock_mistral):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = 'hello world'
        
        mock_client.audio.transcriptions.complete.return_value = mock_response
        mock_mistral.return_value = mock_client
        
        with patch.dict(os.environ, {"MISTRAL_CONTEXT_BIAS": "term1,term2"}):
            trans = TranscriptionMistral(api_key='fake_key')
            self.assertEqual(trans.context_bias, ["term1", "term2"])
            
            # Create a dummy file
            with open('test.wav', 'w') as f:
                f.write('dummy content')
            
            text = trans.transcribe('test.wav')
            self.assertEqual(text, 'hello world')
            
            # Verify context_bias was passed to the API call
            mock_client.audio.transcriptions.complete.assert_called()
            args, kwargs = mock_client.audio.transcriptions.complete.call_args
            self.assertEqual(kwargs.get('context_bias'), ["term1", "term2"])
            
            os.remove('test.wav')

    @patch('output.subprocess.run')
    def test_output_xdotool_type(self, mock_run):
        out = OutputXdotool()
        out.type("hello")
        mock_run.assert_called_with(['xdotool', 'type', '--clearmodifiers', "hello"])

    @patch('output.shutil.which')
    def test_output_xdotool_available(self, mock_which):
        mock_which.return_value = '/usr/bin/xdotool'
        out = OutputXdotool()
        self.assertTrue(out.is_available())
        mock_which.assert_called_with('xdotool')

    @patch('output.shutil.which')
    def test_output_xdotool_not_available(self, mock_which):
        mock_which.return_value = None
        out = OutputXdotool()
        self.assertFalse(out.is_available())

    @patch('output.OutputPortal.is_available', return_value=False)
    def test_use_output(self, _mock_portal):
        from output import OutputNoop
        with patch('output.OutputXdotool.is_available') as mock_available:
            # Test when OutputXdotool is available
            mock_available.return_value = True
            output = use_output()
            self.assertIsInstance(output, OutputXdotool)

            # Test when OutputXdotool is not available, should fall back to OutputNoop
            mock_available.return_value = False
            output = use_output()
            self.assertIsInstance(output, OutputNoop)

    def test_output_selection_logic(self):
        class MockOutputAvailable(Output):
            def is_available(self): return True
            def type(self, text): pass

        class MockOutputUnavailable(Output):
            def is_available(self): return False
            def type(self, text): pass

        # Test selecting the first available
        output_classes = [MockOutputUnavailable, MockOutputAvailable]
        output = None
        for cls in output_classes:
            instance = cls()
            if instance.is_available():
                output = instance
                break
        self.assertIsInstance(output, MockOutputAvailable)

        # Test none available
        output_classes = [MockOutputUnavailable]
        output = None
        for cls in output_classes:
            instance = cls()
            if instance.is_available():
                output = instance
                break
        self.assertIsNone(output)

    @patch('scipy.io.wavfile.read')
    def test_whisper_transcribe(self, mock_wavfile_read):
        mock_wavfile_read.return_value = (16000, np.zeros((16000,), dtype=np.float32))

        mock_segment_1 = MagicMock()
        mock_segment_1.text = " Hello"
        mock_segment_2 = MagicMock()
        mock_segment_2.text = " world."

        mock_info = MagicMock()
        mock_info.language = "en"
        mock_info.language_probability = 0.98

        mock_model = MagicMock()
        mock_model.transcribe.return_value = (iter([mock_segment_1, mock_segment_2]), mock_info)

        whisper = TranscriptionWhisper()
        whisper._model = mock_model

        result = whisper.transcribe("test.wav")
        self.assertEqual(result, "Hello world.")

    def test_whisper_lazy_model_loading(self):
        whisper = TranscriptionWhisper()
        self.assertIsNone(whisper._model)

    def test_whisper_env_config(self):
        with patch.dict(os.environ, {
            "WHISPER_MODEL": "large-v3",
            "WHISPER_DEVICE": "cuda",
            "WHISPER_COMPUTE_TYPE": "float16",
        }):
            whisper = TranscriptionWhisper()
            self.assertEqual(whisper.model_size, "large-v3")
            self.assertEqual(whisper.device, "cuda")
            self.assertEqual(whisper.compute_type, "float16")

    @patch.object(TranscriptionWhisperCpp, 'is_available', return_value=False)
    def test_whisper_priority_over_mistral(self, _):
        with patch.object(TranscriptionWhisper, 'is_available', return_value=True):
            trans = use_transcription()
            self.assertIsInstance(trans, TranscriptionWhisper)

    @patch.object(TranscriptionWhisperCpp, 'is_available', return_value=False)
    def test_use_transcription(self, _):
        from transcription import TranscriptionNoop
        with patch.object(TranscriptionWhisper, 'is_available', return_value=False):
            with patch('transcription.TranscriptionMistral.is_available') as mock_available:
                # Test when TranscriptionMistral is available
                mock_available.return_value = True
                trans = use_transcription()
                self.assertIsInstance(trans, TranscriptionMistral)

                # Test when TranscriptionMistral is not available, should fall back to TranscriptionNoop
                mock_available.return_value = False
                trans = use_transcription()
                self.assertIsInstance(trans, TranscriptionNoop)

    @patch('scipy.io.wavfile.read')
    def test_whispercpp_transcribe(self, mock_wavfile_read):
        mock_wavfile_read.return_value = (16000, np.zeros((16000,), dtype=np.int16))
        mock_segment_1 = MagicMock()
        mock_segment_1.text = " Hello"
        mock_segment_2 = MagicMock()
        mock_segment_2.text = " world."
        mock_model = MagicMock()
        mock_model.transcribe.return_value = [mock_segment_1, mock_segment_2]

        whispercpp = TranscriptionWhisperCpp()
        whispercpp._model = mock_model

        self.assertEqual(whispercpp.transcribe("test.wav"), "Hello world.")
        audio = mock_model.transcribe.call_args[0][0]
        self.assertEqual(audio.dtype, np.float32)

    def test_whispercpp_model_env(self):
        with patch.dict(os.environ, {"WHISPER_MODEL": "medium"}):
            os.environ.pop("WHISPERCPP_MODEL", None)
            self.assertEqual(TranscriptionWhisperCpp().model_name, "medium")
        with patch.dict(os.environ, {"WHISPER_MODEL": "medium", "WHISPERCPP_MODEL": "large-v3-turbo"}):
            self.assertEqual(TranscriptionWhisperCpp().model_name, "large-v3-turbo")

    @patch('transcription.os.listdir')
    @patch('transcription.importlib.util.find_spec')
    def test_whispercpp_requires_gpu_backend(self, mock_find_spec, mock_listdir):
        mock_find_spec.return_value = MagicMock(origin="/site-packages/_pywhispercpp.so")

        mock_listdir.return_value = ["libggml-base.so.0", "libggml-cpu.so.0", "libwhisper.so.1"]
        self.assertFalse(TranscriptionWhisperCpp().is_available())

        mock_listdir.return_value = ["libggml-cpu.so.0", "libggml-vulkan.so.0"]
        whispercpp = TranscriptionWhisperCpp()
        self.assertTrue(whispercpp.is_available())
        self.assertEqual(whispercpp.gpu_backends(), ["vulkan"])

    @patch('transcription.importlib.util.find_spec', return_value=None)
    def test_whispercpp_not_installed(self, _):
        self.assertFalse(TranscriptionWhisperCpp().is_available())

    @patch.object(TranscriptionWhisperCpp, 'init')
    @patch.object(TranscriptionWhisperCpp, 'is_available', return_value=True)
    def test_whispercpp_priority_over_whisper(self, _available, _init):
        with patch.object(TranscriptionWhisper, 'is_available', return_value=True):
            self.assertIsInstance(use_transcription(), TranscriptionWhisperCpp)

    def test_transcription_selection_logic(self):
        class MockTransAvailable(Transcription):
            def is_available(self): return True
            def transcribe(self, file_path): return "ok"

        class MockTransUnavailable(Transcription):
            def is_available(self): return False
            def transcribe(self, file_path): return "no"

        # Test selecting the first available
        trans_classes = [MockTransUnavailable, MockTransAvailable]
        trans = None
        for cls in trans_classes:
            instance = cls()
            if instance.is_available():
                trans = instance
                break
        self.assertIsInstance(trans, MockTransAvailable)

if __name__ == '__main__':
    unittest.main()
