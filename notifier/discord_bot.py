import os
from discord_webhook import DiscordEmbed, DiscordWebhook
import logging
import zipfile
import asyncio
import threading

from .base import Notifier


class DiscordNotifier(Notifier):
    def __init__(self, webhook_url):
        super().__init__()
        self.webhook_url = webhook_url

    async def send_notification(self, file, msg):
        try:
            await self.send_image(file, msg)
            await self.send_file(file, msg)
            self.log_info(f"Discord notification sent for file: {file}")
        except Exception as e:
            self.log_error(f"Failed to send Discord notification: {e}")

    async def send_image(self, file, msg):
        with open(file, "rb") as f:
            webhook = DiscordWebhook(url=self.webhook_url)
            webhook.add_file(file=f.read(), filename=f"{os.path.basename(f.name)}")

            if len(msg) <= 2000:
                embed = DiscordEmbed(title=f"{os.path.basename(f.name)}", description=f"{msg}", color="03b2f8")
                embed.set_thumbnail(url=f"attachment://{f.name}")
                webhook.add_embed(embed)
                webhook.execute()
            else:
                msg_parts = [msg[i:i+2000] for i in range(0, len(msg), 2000)]
                for i, part in enumerate(msg_parts):
                    embed = DiscordEmbed(title=f"{os.path.basename(f.name)} - Part {i+1}", description=part, color="03b2f8")
                    if i == 0:
                        embed.set_thumbnail(url=f"attachment://{f.name}")
                    webhook.add_embed(embed)
                    webhook.execute()

    async def send_file(self, file, msg):
        zip_file_path = f"{file}.zip"
        with zipfile.ZipFile(zip_file_path, "w") as zip_file:
            zip_file.write(file, os.path.basename(file))

        with open(zip_file_path, "rb") as f:
            webhook = DiscordWebhook(url=self.webhook_url)
            webhook.add_file(file=f.read(), filename=f"{os.path.basename(f.name)}.zip")

            if len(msg) <= 2000:
                embed = DiscordEmbed(title=f"{os.path.basename(f.name)}.zip", description=f"{msg}", color="03b2f8")
                embed.set_thumbnail(url=f"attachment://{f.name}.zip")
                webhook.add_embed(embed)
                webhook.execute()
            else:
                msg_parts = [msg[i:i+2000] for i in range(0, len(msg), 2000)]
                for i, part in enumerate(msg_parts):
                    embed = DiscordEmbed(title=f"{os.path.basename(f.name)}.zip - Part {i+1}", description=part, color="03b2f8")
                    if i == 0:
                        embed.set_thumbnail(url=f"attachment://{f.name}.zip")
                    webhook.add_embed(embed)
                    webhook.execute()

        os.remove(zip_file_path)