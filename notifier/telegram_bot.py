import os

from telegram.ext import ApplicationBuilder
from telegram.ext._utils.types import BT

from .base import ChannelCapabilities, DeliveryMode, DeliveryPlan, DeliveryResult, Notifier, RetryPolicy, SupportLevel


class TelegramNotifier(Notifier):
    def __init__(self, token, chat_id):
        super().__init__()
        self.application = ApplicationBuilder().token(token).build()
        self.bot: BT = self.application.bot
        self.chat_id = chat_id
        self._request_timeouts = {
            "connect_timeout": 30,
            "read_timeout": 120,
            "write_timeout": 120,
            "pool_timeout": 30,
        }

    def capabilities(self) -> ChannelCapabilities:
        return ChannelCapabilities(
            media=SupportLevel.NATIVE,
            file=SupportLevel.NATIVE,
            zip=SupportLevel.NATIVE,
            image=True,
            audio=True,
            video=True,
            binary=True,
        )

    async def send_with_plan(self, payload, msg, plan: DeliveryPlan, retry_policy: RetryPolicy | None = None) -> DeliveryResult:
        async def _execute():
            if plan.resolved_mode == DeliveryMode.ZIP:
                sent_message = await self._send_zip_document(payload)
            elif plan.resolved_mode == DeliveryMode.FILE:
                sent_message = await self._send_document(payload)
            else:
                sent_message = await self._send_media(payload)

            await self.reply_msg(sent_message.message_id, msg)
        return await self.timed_send(payload, msg, plan, _execute, retry_policy=retry_policy)

    async def _send_media(self, payload):
        if payload.media_category == "image" and payload.file_size <= 10 * 1024 * 1024:
            with payload.open_binary() as file_obj:
                return await self.bot.send_photo(self.chat_id, photo=file_obj, caption=payload.file_name, **self._request_timeouts)

        if payload.media_category == "audio":
            with payload.open_binary() as file_obj:
                return await self.bot.send_audio(self.chat_id, audio=file_obj, caption=payload.file_name, title=payload.file_name, **self._request_timeouts)

        if payload.media_category == "video":
            with payload.open_binary() as file_obj:
                return await self.bot.send_video(self.chat_id, video=file_obj, caption=payload.file_name, **self._request_timeouts)

        return await self._send_document(payload)

    async def _send_document(self, payload):
        with payload.open_binary() as file_obj:
            return await self.bot.send_document(self.chat_id, document=file_obj, caption=payload.file_name, **self._request_timeouts)

    async def _send_zip_document(self, payload):
        import io
        import zipfile

        memory_zip = io.BytesIO()
        with zipfile.ZipFile(memory_zip, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.write(payload.file_path, payload.file_name)
        memory_zip.seek(0)
        memory_zip.name = f"{os.path.splitext(payload.file_name)[0]}.zip"
        return await self.bot.send_document(self.chat_id, document=memory_zip, caption=memory_zip.name, **self._request_timeouts)

    async def reply_msg(self, message_id, message):
        if not message or not message.strip():
            return

        msgs = [message[i:i + 4096] for i in range(0, len(message), 4096)] or [""]
        for text in msgs:
            if not text.strip():
                continue
            await self.bot.send_message(self.chat_id, text=text, reply_to_message_id=message_id)
