import io
import os
import zipfile

from discord_webhook import DiscordEmbed, DiscordWebhook

from .base import ChannelCapabilities, DeliveryMode, DeliveryPlan, DeliveryResult, Notifier, SupportLevel


class DiscordNotifier(Notifier):
    def __init__(self, webhook_url):
        super().__init__()
        self.webhook_url = webhook_url

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

    async def send_with_plan(self, payload, msg, plan: DeliveryPlan) -> DeliveryResult:
        async def _execute():
            if plan.resolved_mode == DeliveryMode.ZIP:
                await self._send_zip_fallback(payload, msg)
            elif plan.resolved_mode == DeliveryMode.FILE:
                await self._send_file(payload, msg)
            else:
                await self._send_media(payload, msg)
        return await self.timed_send(payload, msg, plan, _execute)

    async def _send_media(self, payload, msg):
        await self.run_blocking(self._execute_media, payload, msg)

    def _execute_media(self, payload, msg):
        with payload.open_binary() as file_obj:
            webhook = DiscordWebhook(url=self.webhook_url)
            webhook.add_file(file=file_obj.read(), filename=payload.file_name)

            msg_parts = [msg[i:i + 2000] for i in range(0, len(msg), 2000)] or [""]
            for index, part in enumerate(msg_parts):
                embed = DiscordEmbed(
                    title=payload.file_name if len(msg_parts) == 1 else f"{payload.file_name} - Part {index + 1}",
                    description=part,
                    color="03b2f8",
                )
                if index == 0 and payload.media_category == "image":
                    embed.set_thumbnail(url=f"attachment://{payload.file_name}")
                webhook.add_embed(embed)
            webhook.execute()

    async def _send_file(self, payload, msg):
        await self.run_blocking(self._execute_file, payload, msg)

    def _execute_file(self, payload, msg):
        with payload.open_binary() as file_obj:
            webhook = DiscordWebhook(url=self.webhook_url, content=msg[:2000] if msg else None)
            webhook.add_file(file=file_obj.read(), filename=payload.file_name)
            webhook.execute()

    async def _send_zip_fallback(self, payload, msg):
        await self.run_blocking(self._execute_zip_fallback, payload, msg)

    def _execute_zip_fallback(self, payload, msg):
        memory_zip = io.BytesIO()
        with zipfile.ZipFile(memory_zip, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.write(payload.file_path, payload.file_name)
        memory_zip.seek(0)

        webhook = DiscordWebhook(url=self.webhook_url, content=msg[:2000] if msg else None)
        archive_name = f"{os.path.splitext(payload.file_name)[0]}.zip"
        webhook.add_file(file=memory_zip.getvalue(), filename=archive_name)
        webhook.execute()
