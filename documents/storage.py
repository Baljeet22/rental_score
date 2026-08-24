import hashlib

import boto3

from botocore.client import Config
from botocore.exceptions import ClientError, BotoCoreError

from django.conf import settings


class MinIOStorageError(Exception):
    """Raised when a MinIO operation fails."""


class MinIOStorage:
    def __init__(self):
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.MINIO_ENDPOINT,
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            region_name=settings.MINIO_REGION,
            use_ssl=settings.MINIO_SECURE,
            config=Config(
                signature_version="s3v4",
                s3={
                    "addressing_style": "path",
                },
            ),
        )

        self.bucket_name = settings.MINIO_BUCKET_NAME

    def generate_upload_url(
        self,
        key: str,
        content_type: str,
    ) -> str:
        try:
            return self.client.generate_presigned_url(
                ClientMethod="put_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": key,
                    "ContentType": content_type,
                },
                ExpiresIn=settings.MINIO_PRESIGNED_UPLOAD_EXPIRATION,
                HttpMethod="PUT",
            )
        except (ClientError, BotoCoreError) as exc:
            raise MinIOStorageError("Unable to generate upload URL.") from exc

    def generate_download_url(
        self,
        key: str,
        filename: str,
        content_type: str,
    ) -> str:
        try:
            content_disposition = (
                f"attachment; filename*=UTF-8''" f"{self._encode_filename(filename)}"
            )

            return self.client.generate_presigned_url(
                ClientMethod="get_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": key,
                    "ResponseContentType": content_type,
                    "ResponseContentDisposition": content_disposition,
                },
                ExpiresIn=settings.MINIO_PRESIGNED_DOWNLOAD_EXPIRATION,
                HttpMethod="GET",
            )
        except (ClientError, BotoCoreError) as exc:
            raise MinIOStorageError("Unable to generate download URL.") from exc

    def head_object(self, key: str) -> dict:
        try:
            return self.client.head_object(
                Bucket=self.bucket_name,
                Key=key,
            )
        except ClientError as exc:
            error_code = exc.response.get(
                "Error",
                {},
            ).get(
                "Code",
            )

            if error_code in {"404", "NoSuchKey", "NotFound"}:
                return None

            raise MinIOStorageError("Unable to check uploaded object.") from exc

    def calculate_sha256(self, key: str) -> str:
        try:
            response = self.client.get_object(
                Bucket=self.bucket_name,
                Key=key,
            )

            sha256 = hashlib.sha256()
            body = response["Body"]

            try:
                while True:
                    chunk = body.read(1024 * 1024)

                    if not chunk:
                        break

                    sha256.update(chunk)

            finally:
                body.close()

            return sha256.hexdigest()

        except (ClientError, BotoCoreError) as exc:
            raise MinIOStorageError("Unable to calculate file checksum.") from exc

    @staticmethod
    def _encode_filename(filename: str) -> str:
        from urllib.parse import quote

        return quote(
            filename,
            safe="",
        )
