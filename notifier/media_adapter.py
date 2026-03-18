import hashlib
import mimetypes
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import folder_paths
from comfy_api.latest._io import FolderType

try:
    import torch
except ImportError:  # pragma: no cover
    torch = None

from comfy_api.latest._ui import AudioSaveHelper

from .base import DeliveryMode


IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif", ".tiff", ".tif", ".avif"
}
VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".mpeg", ".mpg"
}
AUDIO_EXTENSIONS = {
    ".wav", ".flac", ".mp3", ".ogg", ".opus", ".m4a", ".aac"
}


@dataclass(frozen=True)
class MediaPayload:
    source_kind: str
    file_path: str
    file_name: str
    mime_type: str
    media_category: str
    requested_delivery_mode: DeliveryMode
    is_temporary: bool = False

    @property
    def file_size(self) -> int:
        return os.path.getsize(self.file_path)

    @property
    def extension(self) -> str:
        return Path(self.file_name).suffix.lower()

    def open_binary(self):
        return open(self.file_path, "rb")


class MediaAdapter:
    _instance = None
    _instance_lock = threading.Lock()

    def __init__(self):
        self._cache_lock = threading.Lock()
        self._materialized_cache: dict[str, MediaPayload] = {}
        self._temp_root = os.path.join(folder_paths.get_temp_directory(), "comfyui_notifier")
        os.makedirs(self._temp_root, exist_ok=True)

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def resolve_payload(self, *, file_path: str = "", image: Any = None, audio: Any = None, video: str = "", filename: str = "", media_type: str = "auto", delivery_mode: str = "auto") -> MediaPayload:
        requested_delivery_mode = self._normalize_delivery_mode(delivery_mode)
        if file_path:
            return self._payload_from_path(file_path, filename=filename, media_type=media_type, requested_delivery_mode=requested_delivery_mode)
        if video:
            return self._payload_from_path(video, filename=filename, media_type=("video" if media_type == "auto" else media_type), requested_delivery_mode=requested_delivery_mode)
        if audio is not None:
            return self._payload_from_audio(audio, filename=filename, requested_delivery_mode=requested_delivery_mode)
        if image is not None:
            return self._payload_from_image(image, filename=filename, requested_delivery_mode=requested_delivery_mode)
        raise ValueError("No valid media input provided. Expected file_path, video, audio or image.")

    def _payload_from_path(self, raw_path: str, *, filename: str = "", media_type: str = "auto", requested_delivery_mode: DeliveryMode = DeliveryMode.AUTO) -> MediaPayload:
        normalized_path = folder_paths.get_annotated_filepath(raw_path) if self._looks_like_annotated_path(raw_path) else raw_path
        normalized_path = os.path.abspath(normalized_path)
        if not os.path.exists(normalized_path):
            raise FileNotFoundError(f"Media file does not exist: {raw_path}")

        resolved_name = filename.strip() or os.path.basename(normalized_path)
        category = self._infer_category_from_path(normalized_path, media_type)
        mime_type = mimetypes.guess_type(resolved_name)[0] or "application/octet-stream"
        return MediaPayload(
            source_kind="path",
            file_path=normalized_path,
            file_name=resolved_name,
            mime_type=mime_type,
            media_category=category,
            requested_delivery_mode=requested_delivery_mode,
            is_temporary=False,
        )

    def _payload_from_audio(self, audio: dict, *, filename: str = "", requested_delivery_mode: DeliveryMode = DeliveryMode.AUTO) -> MediaPayload:
        cache_key = self._hash_audio(audio, filename, requested_delivery_mode.value)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        generated_name = self._sanitize_filename(filename or f"notifier_audio_{cache_key[:12]}.flac")
        if not generated_name.lower().endswith((".flac", ".mp3", ".opus", ".wav", ".ogg", ".m4a")):
            generated_name += ".flac"

        result = AudioSaveHelper.save_audio(
            audio,
            filename_prefix=f"comfyui_notifier/{cache_key}",
            folder_type="temp",
            cls=None,
            format=self._audio_format_from_name(generated_name),
            quality="128k",
        )[0]
        output_path = os.path.join(folder_paths.get_temp_directory(), result.subfolder, result.filename)
        payload = MediaPayload(
            source_kind="audio",
            file_path=output_path,
            file_name=generated_name,
            mime_type=mimetypes.guess_type(generated_name)[0] or "audio/flac",
            media_category="audio",
            requested_delivery_mode=requested_delivery_mode,
            is_temporary=True,
        )
        self._store_cached(cache_key, payload)
        return payload

    def _payload_from_image(self, image: Any, *, filename: str = "", requested_delivery_mode: DeliveryMode = DeliveryMode.AUTO) -> MediaPayload:
        if torch is None:
            raise RuntimeError("torch is required to materialize IMAGE input.")

        cache_key = self._hash_tensor_like(image, filename, requested_delivery_mode.value)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        image_tensor = image[0] if getattr(image, "shape", None) is not None and len(image.shape) == 4 else image
        image_tensor = image_tensor.detach().cpu().clamp(0, 1)
        image_array = (image_tensor.numpy() * 255.0).round().astype("uint8")

        from PIL import Image

        generated_name = self._sanitize_filename(filename or f"notifier_image_{cache_key[:12]}.png")
        if not generated_name.lower().endswith(tuple(IMAGE_EXTENSIONS)):
            generated_name += ".png"

        target_path = os.path.join(self._temp_root, generated_name)
        Image.fromarray(image_array).save(target_path)
        payload = MediaPayload(
            source_kind="image",
            file_path=target_path,
            file_name=generated_name,
            mime_type=mimetypes.guess_type(generated_name)[0] or "image/png",
            media_category="image",
            requested_delivery_mode=requested_delivery_mode,
            is_temporary=True,
        )
        self._store_cached(cache_key, payload)
        return payload

    def _get_cached(self, cache_key: str):
        with self._cache_lock:
            payload = self._materialized_cache.get(cache_key)
            if payload and os.path.exists(payload.file_path):
                return payload
            if payload:
                self._materialized_cache.pop(cache_key, None)
        return None

    def _store_cached(self, cache_key: str, payload: MediaPayload):
        with self._cache_lock:
            self._materialized_cache[cache_key] = payload

    def _hash_audio(self, audio: dict, filename: str, delivery_mode: str) -> str:
        waveform = audio["waveform"].detach().cpu().contiguous()
        sample_rate = str(audio.get("sample_rate", ""))
        digest = hashlib.sha256()
        digest.update(sample_rate.encode("utf-8"))
        digest.update(filename.encode("utf-8"))
        digest.update(delivery_mode.encode("utf-8"))
        digest.update(waveform.numpy().tobytes())
        return digest.hexdigest()

    def _hash_tensor_like(self, value: Any, filename: str, delivery_mode: str) -> str:
        tensor = value[0] if getattr(value, "shape", None) is not None and len(value.shape) == 4 else value
        tensor = tensor.detach().cpu().contiguous()
        digest = hashlib.sha256()
        digest.update(filename.encode("utf-8"))
        digest.update(delivery_mode.encode("utf-8"))
        digest.update(str(tuple(tensor.shape)).encode("utf-8"))
        digest.update(tensor.numpy().tobytes())
        return digest.hexdigest()

    def _infer_category_from_path(self, path: str, media_type: str) -> str:
        if media_type and media_type != "auto" and media_type != "path":
            return media_type
        suffix = Path(path).suffix.lower()
        if suffix in IMAGE_EXTENSIONS:
            return "image"
        if suffix in AUDIO_EXTENSIONS:
            return "audio"
        if suffix in VIDEO_EXTENSIONS:
            return "video"
        return "binary"

    def _looks_like_annotated_path(self, value: str) -> bool:
        return value.endswith(" [input]") or value.endswith(" [output]") or value.endswith(" [temp]")

    def _sanitize_filename(self, value: str) -> str:
        safe_name = os.path.basename(value.strip()) or "payload.bin"
        return safe_name.replace("..", "_")

    def _audio_format_from_name(self, file_name: str) -> str:
        suffix = Path(file_name).suffix.lower().lstrip(".")
        return suffix if suffix in {"flac", "mp3", "opus"} else "flac"

    def _normalize_delivery_mode(self, delivery_mode: str) -> DeliveryMode:
        try:
            return DeliveryMode(delivery_mode or DeliveryMode.AUTO.value)
        except ValueError as exc:
            raise ValueError(f"Unsupported delivery mode: {delivery_mode}") from exc


_original_save_audio = AudioSaveHelper.save_audio


def _save_audio_with_string_folder_type(audio, filename_prefix, folder_type, cls, format="flac", quality="128k"):
    resolved_folder_type = folder_type
    if isinstance(folder_type, str):
        resolved_folder_type = getattr(FolderType, folder_type, FolderType.output)
    return _original_save_audio(audio, filename_prefix, resolved_folder_type, cls, format=format, quality=quality)


AudioSaveHelper.save_audio = _save_audio_with_string_folder_type
