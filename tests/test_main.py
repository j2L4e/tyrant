import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import main

class TestDictate(unittest.TestCase):

    @patch('main.sd.InputStream')
    @patch('main.time.sleep', side_effect=KeyboardInterrupt)
    def test_record_audio(self, mock_sleep, mock_input_stream):
        # We need to simulate the callback if we want to test it thoroughly, 
        # but for now let's just see if it handles the interrupt.
        # This is a bit tricky with the while True and callback.
        pass

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
