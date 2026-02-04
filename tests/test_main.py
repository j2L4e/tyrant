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
from output import Output, OutputXdotool, first_available_output
from transcription import Transcription, TranscriptionMistral, first_available_transcription

class TestDictate(unittest.TestCase):

    @patch('main.sd.InputStream')
    @patch('main.keyboard.Listener')
    def test_record_audio_ptt_short(self, mock_listener, mock_input_stream):
        # Simulate a short press (1 second)
        mock_listener_instance = MagicMock()
        mock_listener.return_value.__enter__.return_value = mock_listener_instance
        
        def mock_listener_side_effect(on_press, on_release):
            class FakeKey:
                name = 'ctrl'
            
            # Start a thread to simulate the key press after some time
            def simulate_key():
                time.sleep(0.1)
                on_press(FakeKey())
                time.sleep(1) # Short duration
                on_release(FakeKey())
                mock_listener_instance.running = False

            threading.Thread(target=simulate_key).start()
            return mock_listener_instance

        mock_listener.side_effect = mock_listener_side_effect

        audio_data, fs = main.record_audio(ptt_key='ctrl')
        
        self.assertIsNone(audio_data)

    @patch('main.sd.InputStream')
    @patch('main.keyboard.Listener')
    def test_record_audio_ptt_long(self, mock_listener, mock_input_stream):
        # Simulate a long press (2.5 seconds)
        mock_listener_instance = MagicMock()
        mock_listener.return_value.__enter__.return_value = mock_listener_instance
        
        # We need to capture the callback passed to InputStream
        callback_container = [None]
        def mock_input_stream_side_effect(**kwargs):
            callback_container[0] = kwargs.get('callback')
            return MagicMock()
        mock_input_stream.side_effect = mock_input_stream_side_effect

        def mock_listener_side_effect(on_press, on_release):
            class FakeKey:
                name = 'ctrl'
            
            def simulate_key():
                time.sleep(0.1)
                on_press(FakeKey())
                # While recording is active, simulate some audio callbacks
                for _ in range(5):
                    if callback_container[0]:
                        callback_container[0](np.zeros((100, 1)), 100, None, None)
                    time.sleep(0.1)
                
                time.sleep(2.0) # Total > 2 seconds
                on_release(FakeKey())
                mock_listener_instance.running = False

            threading.Thread(target=simulate_key).start()
            return mock_listener_instance

        mock_listener.side_effect = mock_listener_side_effect

        audio_data, fs = main.record_audio(ptt_key='ctrl')
        
        self.assertIsNotNone(audio_data)
        self.assertTrue(len(audio_data) > 0)

    @patch('transcription.Mistral')
    def test_transcribe_audio(self, mock_mistral):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = 'hello world'
        
        mock_client.audio.transcriptions.complete.return_value = mock_response
        mock_mistral.return_value = mock_client
        
        trans = TranscriptionMistral(api_key='fake_key')
        # Create a dummy file
        with open('test.wav', 'w') as f:
            f.write('dummy content')
        
        text = trans.transcribe('test.wav')
        self.assertEqual(text, 'hello world')
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

    def test_first_available_output(self):
        from output import OutputNoop
        with patch('output.OutputXdotool.is_available') as mock_available:
            # Test when OutputXdotool is available
            mock_available.return_value = True
            output = first_available_output()
            self.assertIsInstance(output, OutputXdotool)

            # Test when OutputXdotool is not available, should fall back to OutputNoop
            mock_available.return_value = False
            output = first_available_output()
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

    def test_first_available_transcription(self):
        from transcription import TranscriptionNoop
        with patch('transcription.TranscriptionMistral.is_available') as mock_available:
            # Test when TranscriptionMistral is available
            mock_available.return_value = True
            trans = first_available_transcription()
            self.assertIsInstance(trans, TranscriptionMistral)

            # Test when TranscriptionMistral is not available, should fall back to TranscriptionNoop
            mock_available.return_value = False
            trans = first_available_transcription()
            self.assertIsInstance(trans, TranscriptionNoop)

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
