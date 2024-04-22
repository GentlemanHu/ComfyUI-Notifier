import os
import asyncio
import threading
import logging
from typing import List, Dict
from dotenv import load_dotenv

from .base import Notifier
from .discord_bot import DiscordNotifier
from .telegram_bot import TelegramNotifier
from .yike import YikeNotifier
# ... (Other notifier classes like TelegramNotifier and DiscordNotifier) ...

class NotificationManager:
    __instance = None

    def __init__(self):
        if NotificationManager.__instance is not None:
            raise Exception("This class is a singleton!")
        else:
            NotificationManager.__instance = self
            self.notifiers: Dict[str, Notifier] = {}
            self._auto_register_notifiers()

    @staticmethod
    def get_instance():
        if NotificationManager.__instance is None:
            NotificationManager()
        return NotificationManager.__instance

    def _auto_register_notifiers(self):
        load_dotenv()  # Load environment variables from .env file

        self.register_notifier(TelegramNotifier(os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")))
        self.register_notifier(DiscordNotifier(os.getenv("DISCORD_WEBHOOK_URL")))
        self.register_notifier(YikeNotifier(os.getenv("YIKE_BASE_URL"), os.getenv("YIKE_TOKEN")))
        # ... Add more notifiers here ...

    def register_notifier(self, notifier: Notifier):
        self.notifiers[notifier.__class__.__name__] = notifier

    def get_notifier_info(self) -> List[dict]:
        notifier_info = []
        for name, notifier in self.notifiers.items():
            notifier_info.append({
                "name": name,
                "enabled": False  # Initially disabled
            })
        return notifier_info

    def notify_all(self, file, msg, enabled_notifiers: List[str] = None):
        if enabled_notifiers is None:
            enabled_notifiers = list(self.notifiers.keys())  # Use all notifiers
        
        for name, notifier in self.notifiers.items():
            if name in enabled_notifiers:
                if isinstance(notifier, YikeNotifier):
                    notifier.notify(file, "ai_default")
                else:
                    notifier.notify(file, msg)

