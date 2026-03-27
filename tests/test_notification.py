import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from notification import Notification, NotificationNotifySend, NotificationNoop, use_notification

class TestNotification(unittest.TestCase):

    @patch('notification.subprocess.run')
    def test_notification_notify_send(self, mock_run):
        notify = NotificationNotifySend()
        notify.notify("Hi", "Hello World")
        mock_run.assert_called_with(['notify-send', '-a', 'Tyrant', "Hi", "Hello World"])

    @patch('notification.shutil.which')
    def test_notification_notify_send_available(self, mock_which):
        mock_which.return_value = '/usr/bin/notify-send'
        notify = NotificationNotifySend()
        self.assertTrue(notify.is_available())
        mock_which.assert_called_with('notify-send')

    @patch('notification.shutil.which')
    def test_notification_notify_send_not_available(self, mock_which):
        mock_which.return_value = None
        notify = NotificationNotifySend()
        self.assertFalse(notify.is_available())

    def test_notification_noop(self):
        notify = NotificationNoop()
        self.assertTrue(notify.is_available())
        # Should not raise any error
        notify.notify("Title", "Message")

    def test_use_notification(self):
        with patch('notification.NotificationNotifySend.is_available') as mock_available:
            # Test when NotificationNotifySend is available
            mock_available.return_value = True
            notify = use_notification()
            self.assertIsInstance(notify, NotificationNotifySend)

            # Test when NotificationNotifySend is not available, should fall back to NotificationNoop
            mock_available.return_value = False
            notify = use_notification()
            self.assertIsInstance(notify, NotificationNoop)

if __name__ == '__main__':
    unittest.main()
