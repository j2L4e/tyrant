import subprocess
import shutil
import logging


class Notification:
    """
    Interface for notification classes.
    Any implementation must provide 'is_available' and 'notify' methods.
    """

    def is_available(self) -> bool:
        """Check if the notification method is available on the current system."""
        raise NotImplementedError

    def notify(self, title: str, message: str):
        """Show a notification."""
        raise NotImplementedError


class NotificationNotifySend(Notification):
    """
    Notification implementation using notify-send.
    """

    def is_available(self) -> bool:
        return shutil.which('notify-send') is not None

    def notify(self, title: str, message: str):
        logging.info(f"Showing notification: {title} - {message}")
        subprocess.run(['notify-send', '-a', 'Tyrant', title, message])


class NotificationNoop(Notification):
    """
    Dummy Notification implementation.
    """

    def is_available(self) -> bool:
        return True

    def notify(self, title: str, message: str):
        logging.info(f"Notification noop: {title} - {message}")


NOTIFICATION_MODULES = {
    "notify-send": NotificationNotifySend,
    "noop": NotificationNoop,
}


def use_notification(forced=None):
    """
    Check for available notification methods and return the first one found.
    If forced is set, use that module or raise an error.
    """
    if forced:
        forced = forced.lower()
        if forced not in NOTIFICATION_MODULES:
            raise RuntimeError(
                f"Unknown notification module '{forced}'. "
                f"Available: {', '.join(NOTIFICATION_MODULES)}"
            )
        instance = NOTIFICATION_MODULES[forced]()
        if not instance.is_available():
            raise RuntimeError(
                f"Notification module '{forced}' is not available. "
                f"Check its dependencies."
            )
        logging.info(f"Using {instance.__class__.__name__} for notifications (forced).")
        return instance

    notification_classes = [
        NotificationNotifySend,
        NotificationNoop
    ]

    for cls in notification_classes:
        instance = cls()
        if instance.is_available():
            logging.info(f"Using {cls.__name__} for notifications.")
            return instance
    return None
