import asyncio
import threading
import logging

class Notifier:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.run_asyncio_loop, args=(self.loop,))
        self.thread.start()

        # Configure logging
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=logging.INFO
        )
        self.logger = logging.getLogger(__name__)

    def run_asyncio_loop(self, loop):
        loop.run_forever()

    async def send_notification(self, file, msg):
        raise NotImplementedError("Subclasses must implement send_notification method")

    def notify(self, file, msg):
        asyncio.run_coroutine_threadsafe(self.send_notification(file, msg), self.loop)

    def log_info(self, message):
        self.logger.info(message)

    def log_error(self, message):
        self.logger.error(message)

        