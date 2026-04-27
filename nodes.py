from .notifier.notify import NotificationManager


class GeneralNotifier:
    @classmethod
    def INPUT_TYPES(cls):
        manager = NotificationManager.get_instance()
        notifier_info = manager.get_notifier_info()

        input_types = {
            "required": {
                "file_path": ("STRING", {"default": ""}),
                "message": ("STRING", {"default": ""}),
            },
            "optional": {
                "image": ("IMAGE",),
                "audio": ("AUDIO",),
                "video": ("STRING", {"default": ""}),
                "filename": ("STRING", {"default": "", "multiline": False}),
                "media_type": (["auto", "path", "image", "audio", "video", "binary"], {"default": "auto"}),
                "delivery_mode": (["auto", "media", "file", "zip"], {"default": "auto"}),
                "execution_mode": (["async", "sync"], {"default": "async"}),
                "parallel_dispatch": ("BOOLEAN", {"default": True}),
                "retry_attempts": ("INT", {"default": 0, "min": 0, "max": 10, "step": 1}),
                "retry_delay_seconds": ("FLOAT", {"default": 1.5, "min": 0.0, "max": 30.0, "step": 0.1}),
                "retry_backoff_factor": ("FLOAT", {"default": 2.0, "min": 1.0, "max": 10.0, "step": 0.1}),
                "discord_max_attachment_mb": ("FLOAT", {"default": 20.0, "min": 0.0, "max": 500.0, "step": 1.0}),
                "send_as_file": ("BOOLEAN", {"default": False}),
                "send_as_zip": ("BOOLEAN", {"default": False}),
                "audio_format": (["auto", "flac", "mp3", "wav", "opus"], {"default": "auto"}),
                "audio_quality": (["auto", "128k", "192k", "256k", "320k"], {"default": "auto"}),
                "video_format": (["auto", "h264", "h265", "vp9"], {"default": "auto"}),
            },
        }

        for info in notifier_info:
            notifier_name = info["name"]
            input_types["optional"][notifier_name] = ("BOOLEAN", {"default": True})

        return input_types

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("Result URL",)
    FUNCTION = "try_notify"
    OUTPUT_NODE = True

    CATEGORY = "GentlemanHu_Notifier"

    def try_notify(self, file_path, message, image=None, audio=None, video="", filename="", media_type="auto", delivery_mode="auto", execution_mode="async", parallel_dispatch=True, retry_attempts=0, retry_delay_seconds=1.5, retry_backoff_factor=2.0, discord_max_attachment_mb=20.0, send_as_file=False, send_as_zip=False, audio_format="auto", audio_quality="auto", video_format="auto", **kwargs):
        enabled_notifiers = [
            name for name, enabled in kwargs.items()
            if enabled is True and name not in {"send_as_file", "send_as_zip", "delivery_mode", "execution_mode", "parallel_dispatch", "retry_attempts", "retry_delay_seconds", "retry_backoff_factor", "discord_max_attachment_mb", "audio_format", "audio_quality", "video_format"}
        ]

        resolved_delivery_mode = delivery_mode
        if send_as_zip:
            resolved_delivery_mode = "zip"
        elif send_as_file:
            resolved_delivery_mode = "file"

        manager = NotificationManager.get_instance()
        result = manager.notify_all(
            file_path=file_path,
            msg=message,
            enabled_notifiers=enabled_notifiers,
            image=image,
            audio=audio,
            video=video,
            filename=filename,
            media_type=media_type,
            delivery_mode=resolved_delivery_mode,
            execution_mode=execution_mode,
            parallel_dispatch=parallel_dispatch,
            retry_attempts=retry_attempts,
            retry_delay_seconds=retry_delay_seconds,
            retry_backoff_factor=retry_backoff_factor,
            discord_max_attachment_mb=discord_max_attachment_mb,
            audio_format=audio_format,
            audio_quality=audio_quality,
            video_format=video_format,
        )

        print(f"Triggered notifications for input: {file_path or filename or media_type}")
        return (result.summary_text(),)


NODE_CLASS_MAPPINGS = {
    "GentlemanHu_Notifier": GeneralNotifier
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "GentlemanHu_Notifier": "GeneralNotifier"
}
