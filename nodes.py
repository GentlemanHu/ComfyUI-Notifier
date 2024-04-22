# ... (Notifier classes and NotificationManager remain the same) ...

from notifier.notify import NotificationManager


class Trigger:
    # ... (Other methods remain the same) ...

    @classmethod
    def INPUT_TYPES(cls):
        manager = NotificationManager.get_instance()
        notifier_info = manager.get_notifier_info()

        input_types = {
            "required": {
                "file_path": ("STRING", {"default": ""}),
                "message": ("STRING", {"default": ""}),
            },
            "optional": {}
        }

        for info in notifier_info:
            notifier_name = info["name"]
            input_types["optional"][notifier_name] = ("BOOLEAN", {"default": True})

        return input_types
    
    #TODO - 返回各个渠道的结果url
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("Result URL",)
    FUNCTION = "try_notify"
    OUTPUT_NODE = True

    CATEGORY = "GentlemanHu_Notifier"
    
    def try_notify(self, file_path, message, **kwargs):
        enabled_notifiers = [name for name, enabled in kwargs.items() if enabled]
        manager = NotificationManager.get_instance()
        manager.notify_all(file_path, message, enabled_notifiers)

        ret = True  # Assuming success
        print(f"Triggered notifications for: {file_path}")
        #TODO - 返回各个渠道的结果url
        return ("",)

# ... (Rest of the code remains the same) ...