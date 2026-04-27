import asyncio
import concurrent.futures
import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum


class DeliveryMode(str, Enum):
    AUTO = "auto"
    MEDIA = "media"
    FILE = "file"
    ZIP = "zip"


class SupportLevel(str, Enum):
    NATIVE = "native"
    FALLBACK = "fallback"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class ChannelCapabilities:
    media: SupportLevel = SupportLevel.UNSUPPORTED
    file: SupportLevel = SupportLevel.NATIVE
    zip: SupportLevel = SupportLevel.FALLBACK
    image: bool = True
    audio: bool = True
    video: bool = True
    binary: bool = True


@dataclass(frozen=True)
class DeliveryPlan:
    requested_mode: DeliveryMode
    resolved_mode: DeliveryMode
    fallback_reason: str | None = None


@dataclass
class DeliveryResult:
    notifier_name: str
    requested_mode: str
    resolved_mode: str
    status: str
    fallback_reason: str | None = None
    detail: str = ""
    duration_ms: int = 0


@dataclass(frozen=True)
class RetryPolicy:
    attempts: int = 0
    initial_delay_seconds: float = 1.5
    backoff_factor: float = 2.0


class Notifier:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.run_asyncio_loop, args=(self.loop,), daemon=True)
        self.thread.start()
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix=self.__class__.__name__)

        logging.basicConfig(
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            level=logging.INFO,
        )
        self.logger = logging.getLogger(self.__class__.__name__)

    def _sanitize_retry_policy(self, retry_policy: RetryPolicy | None) -> RetryPolicy:
        if retry_policy is None:
            return RetryPolicy()

        attempts = max(0, int(retry_policy.attempts))
        initial_delay = float(retry_policy.initial_delay_seconds)
        backoff = float(retry_policy.backoff_factor)

        if initial_delay < 0:
            initial_delay = 0.0
        if backoff < 1.0:
            backoff = 1.0

        return RetryPolicy(
            attempts=attempts,
            initial_delay_seconds=initial_delay,
            backoff_factor=backoff,
        )

    def _is_retryable_exception(self, exc: Exception) -> bool:
        if isinstance(exc, (TimeoutError, ConnectionError, ConnectionResetError)):
            return True

        exc_type_name = type(exc).__name__.lower()
        retryable_markers = (
            "connecterror",
            "connectionerror",
            "timeout",
            "ssl",
            "remoteprotocolerror",
            "chunkedencodingerror",
            "protocolerror",
            "networkerror",
            "pooltimeout",
            "eoferror",
        )
        return any(marker in exc_type_name for marker in retryable_markers)

    def run_asyncio_loop(self, loop):
        asyncio.set_event_loop(loop)
        loop.run_forever()

    def capabilities(self) -> ChannelCapabilities:
        return ChannelCapabilities()

    def supports_category(self, media_category: str) -> bool:
        capabilities = self.capabilities()
        return getattr(capabilities, media_category, True)

    def resolve_delivery_plan(self, payload) -> DeliveryPlan:
        requested_mode = payload.requested_delivery_mode
        capabilities = self.capabilities()

        if requested_mode == DeliveryMode.AUTO:
            if capabilities.media != SupportLevel.UNSUPPORTED and self.supports_category(payload.media_category):
                return DeliveryPlan(requested_mode, DeliveryMode.MEDIA)
            if capabilities.file != SupportLevel.UNSUPPORTED:
                return DeliveryPlan(requested_mode, DeliveryMode.FILE, "channel_media_not_supported")
            if capabilities.zip != SupportLevel.UNSUPPORTED:
                return DeliveryPlan(requested_mode, DeliveryMode.ZIP, "channel_file_not_supported")
            raise ValueError(f"{self.__class__.__name__} does not support payload category: {payload.media_category}")

        requested_support = getattr(capabilities, requested_mode.value)
        if requested_mode == DeliveryMode.MEDIA and not self.supports_category(payload.media_category):
            requested_support = SupportLevel.UNSUPPORTED

        if requested_support != SupportLevel.UNSUPPORTED:
            return DeliveryPlan(requested_mode, requested_mode)

        if requested_mode != DeliveryMode.FILE and capabilities.file != SupportLevel.UNSUPPORTED:
            return DeliveryPlan(requested_mode, DeliveryMode.FILE, f"{requested_mode.value}_unsupported_fallback_to_file")
        if requested_mode != DeliveryMode.ZIP and capabilities.zip != SupportLevel.UNSUPPORTED:
            return DeliveryPlan(requested_mode, DeliveryMode.ZIP, f"{requested_mode.value}_unsupported_fallback_to_zip")
        raise ValueError(f"{self.__class__.__name__} cannot satisfy requested mode: {requested_mode.value}")

    async def send_with_plan(self, payload, msg, plan: DeliveryPlan, retry_policy: RetryPolicy | None = None, notifier_options: dict | None = None) -> DeliveryResult:
        raise NotImplementedError("Subclasses must implement send_with_plan method")

    def notify(self, payload, msg, retry_policy: RetryPolicy | None = None, notifier_options: dict | None = None):
        retry_policy = self._sanitize_retry_policy(retry_policy)
        plan = self.resolve_delivery_plan(payload)
        self.log_info(
            f"Queue notification | notifier={self.__class__.__name__} | category={payload.media_category} | requested={plan.requested_mode.value} | resolved={plan.resolved_mode.value} | fallback={plan.fallback_reason or 'none'} | retry_attempts={retry_policy.attempts}"
        )
        return asyncio.run_coroutine_threadsafe(
            self.send_with_plan(payload, msg, plan, retry_policy=retry_policy, notifier_options=notifier_options),
            self.loop,
        )

    async def run_blocking(self, func, *args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.executor, lambda: func(*args, **kwargs))

    def build_result(self, plan: DeliveryPlan, status: str, detail: str = "", duration_ms: int = 0) -> DeliveryResult:
        return DeliveryResult(
            notifier_name=self.__class__.__name__,
            requested_mode=plan.requested_mode.value,
            resolved_mode=plan.resolved_mode.value,
            status=status,
            fallback_reason=plan.fallback_reason,
            detail=detail,
            duration_ms=duration_ms,
        )

    async def timed_send(self, payload, msg, plan: DeliveryPlan, send_callable, retry_policy: RetryPolicy | None = None):
        retry_policy = self._sanitize_retry_policy(retry_policy)
        start_time = time.perf_counter()
        total_attempts = retry_policy.attempts + 1
        delay_seconds = retry_policy.initial_delay_seconds

        for attempt in range(1, total_attempts + 1):
            try:
                await send_callable()
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                self.log_info(
                    f"Send success | notifier={self.__class__.__name__} | category={payload.media_category} | requested={plan.requested_mode.value} | resolved={plan.resolved_mode.value} | duration_ms={duration_ms} | attempt={attempt}/{total_attempts}"
                )
                return self.build_result(plan, "sent", duration_ms=duration_ms)
            except Exception as exc:
                is_retryable = self._is_retryable_exception(exc)
                can_retry = attempt < total_attempts and is_retryable

                if can_retry:
                    self.log_error(
                        f"Send attempt failed, will retry | notifier={self.__class__.__name__} | category={payload.media_category} | requested={plan.requested_mode.value} | resolved={plan.resolved_mode.value} | attempt={attempt}/{total_attempts} | delay_seconds={delay_seconds:.2f} | error={exc}"
                    )
                    if delay_seconds > 0:
                        await asyncio.sleep(delay_seconds)
                    delay_seconds = min(delay_seconds * retry_policy.backoff_factor, 30.0)
                    continue

                duration_ms = int((time.perf_counter() - start_time) * 1000)
                retry_hint = "retryable" if is_retryable else "non-retryable"
                self.log_error(
                    f"Send failed | notifier={self.__class__.__name__} | category={payload.media_category} | requested={plan.requested_mode.value} | resolved={plan.resolved_mode.value} | duration_ms={duration_ms} | attempt={attempt}/{total_attempts} | {retry_hint} | error={exc}"
                )
                return self.build_result(plan, "error", str(exc), duration_ms=duration_ms)

    def log_info(self, message):
        self.logger.info(message)

    def log_error(self, message):
        self.logger.error(message)
