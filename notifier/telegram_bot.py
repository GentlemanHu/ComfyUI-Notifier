import logging
import asyncio
from time import sleep
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, Updater
from telegram.ext._utils.types import BT
import json
import os
import threading


from .base import Notifier

class TelegramNotifier(Notifier):
    def __init__(self, token, chat_id):
        super().__init__()
            # Create the Updater and pass it your bot's token.
        self.application = ApplicationBuilder().token(token).build()
        self.bot: BT = self.application.bot
        self.chat_id = chat_id
        

    async def send_notification(self, file, msg):
        file_size = os.path.getsize(file)
        file_name = os.path.basename(file)
        extension = os.path.splitext(file)[1].lstrip(".")
        image_extensions = ['png', 'jpg', 'jpeg', 'bmp', 'webp']

        try:
            if file_size <= 10 * 1024 * 1024 and extension in image_extensions:
                with open(file, 'rb') as f:
                    sent_message = await self.bot.send_photo(self.chat_id, photo=f, caption=file_name, write_timeout=3000)
            else:
                with open(file, 'rb') as f:
                    sent_message = await self.bot.send_document(self.chat_id, document=f, caption=file_name, write_timeout=3000)

            await self.reply_msg(sent_message.message_id, msg)
            self.log_info(f"Telegram notification sent for file: {file}")
        except Exception as e:
            self.log_error(f"Failed to send Telegram notification: {e}")

    async def reply_msg(self, message_id, message):
        msgs = [message[i:i + 4096] for i in range(0, len(message), 4096)]
        for text in msgs:
            await self.bot.send_message(self.chat_id, text=text, reply_to_message_id=message_id)