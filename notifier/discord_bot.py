import io
import os
import zipfile

from discord_webhook import DiscordEmbed, DiscordWebhook

from .base import ChannelCapabilities, DeliveryMode, DeliveryPlan, DeliveryResult, Notifier, RetryPolicy, SupportLevel


class DiscordNotifier(Notifier):
    def __init__(self, webhook_url):
        super().__init__()
        self.webhook_url = webhook_url
        self._max_attachment_bytes = self._resolve_max_attachment_bytes()

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
                await self._send_zip_fallback(payload, msg)
            elif plan.resolved_mode == DeliveryMode.FILE:
                await self._send_file(payload, msg)
            else:
                await self._send_media(payload, msg)
        return await self.timed_send(payload, msg, plan, _execute, retry_policy=retry_policy)

    async def _send_media(self, payload, msg):
        self._validate_attachment_size(payload)
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
            response = webhook.execute()
            self._ensure_discord_response_ok(response, payload)

    async def _send_file(self, payload, msg):
        self._validate_attachment_size(payload)
        await self.run_blocking(self._execute_file, payload, msg)

    def _execute_file(self, payload, msg):
        with payload.open_binary() as file_obj:
            webhook = DiscordWebhook(url=self.webhook_url, content=msg[:2000] if msg else None)
            webhook.add_file(file=file_obj.read(), filename=payload.file_name)
            response = webhook.execute()
            self._ensure_discord_response_ok(response, payload)

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
        response = webhook.execute()
        self._ensure_discord_response_ok(response, payload)

    def _resolve_max_attachment_bytes(self) -> int:
        raw = os.getenv("DISCORD_WEBHOOK_MAX_ATTACHMENT_MB", "8")
        try:
            size_mb = float(raw)
        except ValueError:
            size_mb = 8.0
        if size_mb <= 0:
            return 0
        return int(size_mb * 1024 * 1024)

    def _validate_attachment_size(self, payload):
        if self._max_attachment_bytes <= 0:
            return
        file_size = payload.file_size
        if file_size <= self._max_attachment_bytes:
            return
        max_mb = self._max_attachment_bytes / (1024 * 1024)
        current_mb = file_size / (1024 * 1024)
        raise RuntimeError(
            f"Discord attachment too large before upload | file={payload.file_name} | size_mb={current_mb:.2f} | limit_mb={max_mb:.2f}"
        )

    def _ensure_discord_response_ok(self, response, payload):
        if response is None:
            return

        status_code = getattr(response, "status_code", None)
        ok = getattr(response, "ok", None)
        if status_code is None and isinstance(response, (bool, int)):
            if response:
                return
            raise RuntimeError(f"Discord webhook returned falsy result | file={payload.file_name}")

        if status_code is None:
            return

        if ok is True or (isinstance(status_code, int) and 200 <= status_code < 300):
            return

        response_text = getattr(response, "text", "") or ""
        if len(response_text) > 300:
            response_text = response_text[:300] + "..."
        raise RuntimeError(
            f"Discord webhook failed | status_code={status_code} | file={payload.file_name} | response={response_text}"
        )
