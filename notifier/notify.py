import concurrent.futures
import logging
import os
import threading
from dataclasses import dataclass, field
from typing import Dict, List

from dotenv import load_dotenv

from .base import DeliveryResult, Notifier, RetryPolicy
from .discord_bot import DiscordNotifier
from .media_adapter import MediaAdapter
from .telegram_bot import TelegramNotifier
from .yike import YikeNotifier


@dataclass
class NotificationResult:
    payload_path: str
    payload_category: str
    notifier_results: dict[str, DeliveryResult] = field(default_factory=dict)

    def summary_text(self) -> str:
        if not self.notifier_results:
            return f"payload={self.payload_path}; category={self.payload_category}; no-notifier-selected"

        parts = []
        for name, result in self.notifier_results.items():
            detail = f"{name}:{result.status}[{result.requested_mode}->{result.resolved_mode}]"
            if result.fallback_reason:
                detail += f"<{result.fallback_reason}>"
            parts.append(detail)
        return f"payload={self.payload_path}; category={self.payload_category}; " + ", ".join(parts)


class NotificationManager:
    __instance = None

    def __init__(self):
        if NotificationManager.__instance is not None:
            raise Exception("This class is a singleton!")
        NotificationManager.__instance = self
        self.notifiers: Dict[str, Notifier] = {}
        self.media_adapter = MediaAdapter.get_instance()
        self.logger = logging.getLogger(self.__class__.__name__)
        self._auto_register_notifiers()

    def _dispatch_single_sync(self, name, notifier, payload, msg, retry_policy: RetryPolicy):
        self.logger.info(
            f"Dispatch sync | notifier={name} | category={payload.media_category} | requested={payload.requested_delivery_mode.value} | retry_attempts={retry_policy.attempts}"
        )
        future = notifier.notify(payload, msg, retry_policy=retry_policy)
        return future.result()

    def _run_sync(self, payload, msg, enabled_notifiers: List[str], result: NotificationResult, parallel: bool, retry_policy: RetryPolicy):
        selected_items = [(name, notifier) for name, notifier in self.notifiers.items() if name in enabled_notifiers]
        if parallel:
            worker_count = max(1, len(selected_items))
            with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="NotifierDispatch") as executor:
                future_map = {
                    executor.submit(self._dispatch_single_sync, name, notifier, payload, msg, retry_policy): name
                    for name, notifier in selected_items
                }
                for future in concurrent.futures.as_completed(future_map):
                    delivery_result = future.result()
                    result.notifier_results[delivery_result.notifier_name] = delivery_result
        else:
            for name, notifier in selected_items:
                delivery_result = self._dispatch_single_sync(name, notifier, payload, msg, retry_policy)
                result.notifier_results[delivery_result.notifier_name] = delivery_result

    def _background_dispatch(self, payload, msg, enabled_notifiers: List[str], parallel: bool, retry_policy: RetryPolicy):
        self.logger.info(
            f"Background dispatch start | category={payload.media_category} | requested={payload.requested_delivery_mode.value} | parallel={parallel} | retry_attempts={retry_policy.attempts}"
        )
        background_result = NotificationResult(payload_path=payload.file_path, payload_category=payload.media_category)
        try:
            self._run_sync(payload, msg, enabled_notifiers, background_result, parallel, retry_policy)
            self.logger.info(
                f"Background dispatch finished | category={payload.media_category} | summary={background_result.summary_text()}"
            )
        except Exception as exc:
            self.logger.error(f"Background dispatch failed | error={exc}")

    def _run_async_background(self, payload, msg, enabled_notifiers: List[str], parallel: bool, retry_policy: RetryPolicy):
        thread = threading.Thread(
            target=self._background_dispatch,
            args=(payload, msg, enabled_notifiers, parallel, retry_policy),
            daemon=True,
            name="ComfyUI-Notifier-BackgroundDispatch",
        )
        thread.start()

    @staticmethod
    def get_instance():
        if NotificationManager.__instance is None:
            NotificationManager()
        return NotificationManager.__instance

    def _auto_register_notifiers(self):
        load_dotenv()

        telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        discord_webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
        yike_base_url = os.getenv("YIKE_BASE_URL")
        yike_token = os.getenv("YIKE_TOKEN")

        if telegram_token and telegram_chat_id:
            self.register_notifier(TelegramNotifier(telegram_token, telegram_chat_id))
        if discord_webhook_url:
            self.register_notifier(DiscordNotifier(discord_webhook_url))
        if yike_base_url and yike_token:
            self.register_notifier(YikeNotifier(yike_base_url, yike_token))

    def register_notifier(self, notifier: Notifier):
        self.notifiers[notifier.__class__.__name__] = notifier

    def get_notifier_info(self) -> List[dict]:
        notifier_info = []
        for name, notifier in self.notifiers.items():
            capabilities = notifier.capabilities()
            notifier_info.append({
                "name": name,
                "enabled": False,
                "capabilities": {
                    "media": capabilities.media.value,
                    "file": capabilities.file.value,
                    "zip": capabilities.zip.value,
                },
            })
        return notifier_info

    def notify_all(self, file_path, msg, enabled_notifiers: List[str] = None, **media_inputs):
        if enabled_notifiers is None:
            enabled_notifiers = list(self.notifiers.keys())

        execution_mode = media_inputs.pop("execution_mode", "async")
        parallel = bool(media_inputs.pop("parallel_dispatch", True))
        retry_attempts = max(0, int(media_inputs.pop("retry_attempts", 0)))
        retry_delay_seconds = float(media_inputs.pop("retry_delay_seconds", 1.5))
        retry_backoff_factor = float(media_inputs.pop("retry_backoff_factor", 2.0))

        retry_policy = RetryPolicy(
            attempts=retry_attempts,
            initial_delay_seconds=retry_delay_seconds,
            backoff_factor=retry_backoff_factor,
        )

        payload = self.media_adapter.resolve_payload(file_path=file_path, **media_inputs)
        result = NotificationResult(payload_path=payload.file_path, payload_category=payload.media_category)

        self.logger.info(
            f"Notify request received | payload={payload.file_path} | category={payload.media_category} | execution_mode={execution_mode} | parallel={parallel} | retry_attempts={retry_policy.attempts} | retry_delay_seconds={retry_policy.initial_delay_seconds} | retry_backoff_factor={retry_policy.backoff_factor} | enabled_notifiers={enabled_notifiers}"
        )

        if execution_mode == "async":
            self._run_async_background(payload, msg, enabled_notifiers, parallel, retry_policy)
            for name in enabled_notifiers:
                result.notifier_results[name] = DeliveryResult(
                    notifier_name=name,
                    requested_mode=payload.requested_delivery_mode.value,
                    resolved_mode="background",
                    status="queued",
                    fallback_reason=None,
                    detail=f"queued for background dispatch; parallel={parallel}; retry_attempts={retry_policy.attempts}",
                    duration_ms=0,
                )
            return result

        self._run_sync(payload, msg, enabled_notifiers, result, parallel, retry_policy)

        return result
