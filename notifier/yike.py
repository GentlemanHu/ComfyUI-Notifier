import os
import requests
import urllib.parse
from requests_toolbelt import MultipartEncoder
import asyncio
import threading

from notifier.base import Notifier


## 对接的是alist程序
class YikeNotifier(Notifier):
    def __init__(self, base_url, token):
        super().__init__()
        self.base_url = base_url
        self.token = token

    async def send_notification(self, file_path, album="ai_default"):
        try:
            # 创建文件夹
            url2 = f"{self.base_url}/api/fs/mkdir"
            headers = {'Authorization': self.token}
            data = {'path': f'/yike_sc/{album}'}
            requests.post(url=url2, data=data, headers=headers)

            target_path = f"{album}/{os.path.basename(file_path)}"
            encoded_target_path = urllib.parse.quote(target_path)

            data = MultipartEncoder(fields={'file': (file_path, open(file_path, 'rb'))})

            headers = {
                "Authorization": self.token,
                'File-Path': "/yike_sc/" + encoded_target_path,
                "Content-Type": data.content_type,
                "Content-Length": f"{os.path.getsize(file_path)}"
            }

            upload_url = f"{self.base_url}/api/fs/form"
            response = requests.put(upload_url, headers=headers, data=data)

            if response.status_code == 200:
                self.log_info(f"File uploaded successfully to Yike: {file_path}")
            else:
                self.log_error(f"Failed to upload file to Yike: {file_path}. Error: {response.text}")
        except Exception as e:
            self.log_error(f"Failed to upload to Yike: {e}")