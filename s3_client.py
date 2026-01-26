import os
import boto3
from botocore.config import Config

# Настройки для Yandex Object Storage
AWS_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY")
AWS_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_KEY")
BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
ENDPOINT_URL = "https://storage.yandexcloud.net"

class S3Client:
    def __init__(self):
        if not all([AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, BUCKET_NAME]):
            self.client = None
            print("⚠️ S3 credentials not set, S3 uploads disabled.")
            return

        self.client = boto3.client(
            service_name="s3",
            endpoint_url=ENDPOINT_URL,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            config=Config(region_name="ru-central1")
        )

    def upload_file(self, local_path, object_name=None):
        """Загрузить файл в S3"""
        if not self.client:
            return None

        if object_name is None:
            object_name = os.path.basename(local_path)

        try:
            self.client.upload_file(local_path, BUCKET_NAME, object_name)
            file_url = f"{ENDPOINT_URL}/{BUCKET_NAME}/{object_name}"
            return file_url
        except Exception as e:
            print(f"❌ Error uploading to S3: {e}")
            return None

s3 = S3Client()
