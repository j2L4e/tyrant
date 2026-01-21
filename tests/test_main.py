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

    @patch('main.Mistral')
    def test_transcribe_audio(self, mock_mistral):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = 'hello world'
        
        mock_client.audio.transcriptions.complete.return_value = mock_response
        mock_mistral.return_value = mock_client
        
        with patch('main.MISTRAL_API_KEY', 'fake_key'):
            # Create a dummy file
            with open('test.wav', 'w') as f:
                f.write('dummy content')
            
            text = main.transcribe_audio('test.wav')
            self.assertEqual(text, 'hello world')
            os.remove('test.wav')

    @patch('main.subprocess.run')
    def test_type_text(self, mock_run):
        main.type_text("hello")
        mock_run.assert_called_with(['xdotool', 'type', '--clearmodifiers', 'hello'])

if __name__ == '__main__':
    unittest.main()
