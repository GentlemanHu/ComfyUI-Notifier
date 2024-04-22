# Example usage
from time import sleep
from notifier.notify import NotificationManager




manager = NotificationManager.get_instance()
manager.notify_all("/Users/gentlemanhu/Documents/288211713772136_.pic.jpg","test-notifier",enabled_notifiers=["TelegramNotifier"])

# 注意 后台 - tg容易出现 Unknown error in HTTP implementation: RuntimeError('cannot schedule new futures after interpreter shutdown')
sleep(10)