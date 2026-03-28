import urllib.parse

import requests
from requests_toolbelt import MultipartEncoder

from .base import ChannelCapabilities, DeliveryMode, DeliveryPlan, DeliveryResult, Notifier, RetryPolicy, SupportLevel


class YikeNotifier(Notifier):
    def __init__(self, base_url, token):
        super().__init__()
        self.base_url = base_url
        self.token = token

    def capabilities(self) -> ChannelCapabilities:
        return ChannelCapabilities(
            media=SupportLevel.UNSUPPORTED,
            file=SupportLevel.NATIVE,
            zip=SupportLevel.NATIVE,
            image=True,
            audio=True,
            video=True,
            binary=True,
        )

    async def send_with_plan(self, payload, msg, plan: DeliveryPlan, retry_policy: RetryPolicy | None = None) -> DeliveryResult:
        async def _execute():
            await self.run_blocking(self._upload, payload, plan)
        return await self.timed_send(payload, msg, plan, _execute, retry_policy=retry_policy)

    def _upload(self, payload, plan: DeliveryPlan):
        album = "ai_default"
        url2 = f"{self.base_url}/api/fs/mkdir"
        headers = {"Authorization": self.token}
        data = {"path": f"/yike_sc/{album}"}
        requests.post(url=url2, data=data, headers=headers, timeout=30)

        file_name = payload.file_name
        file_path = payload.file_path

        if plan.resolved_mode == DeliveryMode.ZIP:
            import io
            import zipfile

            memory_zip = io.BytesIO()
            with zipfile.ZipFile(memory_zip, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
                zip_file.write(payload.file_path, payload.file_name)
            memory_zip.seek(0)
            file_name = f"{payload.file_name.rsplit('.', 1)[0]}.zip"
            file_bytes = memory_zip.getvalue()
            data = MultipartEncoder(fields={"file": (file_name, file_bytes, "application/zip")})
            content_length = len(file_bytes)
        else:
            file_handle = open(file_path, "rb")
            data = MultipartEncoder(fields={"file": (file_name, file_handle, payload.mime_type)})
            content_length = payload.file_size

        try:
            encoded_target_path = urllib.parse.quote(f"{album}/{file_name}")
            upload_headers = {
                "Authorization": self.token,
                "File-Path": "/yike_sc/" + encoded_target_path,
                "Content-Type": data.content_type,
                "Content-Length": f"{content_length}",
            }
            upload_url = f"{self.base_url}/api/fs/form"
            response = requests.put(upload_url, headers=upload_headers, data=data, timeout=300)
        finally:
            if hasattr(data, "fields"):
                field_file = data.fields.get("file")
                if isinstance(field_file, tuple) and len(field_file) > 1 and hasattr(field_file[1], "close"):
                    field_file[1].close()

        if response.status_code == 200:
            self.log_info(f"File uploaded successfully to Yike: {payload.file_path}")
        else:
            self.log_error(f"Failed to upload file to Yike: {payload.file_path}. Error: {response.text}")
            raise RuntimeError(response.text)
