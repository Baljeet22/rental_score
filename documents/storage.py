import hashlib
from urllib.parse import quote

import boto3

from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from django.conf import settings


class MinIOStorageError(Exception):
    """Raised when a MinIO storage operation fails."""


class MinIOStorage:
    """
    MinIO/S3 storage service.

    Two S3 clients are used intentionally:

    1. self.client
       Used for server-side Django -> MinIO operations.
       Example: http://minio:9000

    2. self.presign_client
       Used only to generate presigned URLs that clients
       (browser/Postman) can access.
       Example: http://127.0.0.1:9000
    """

    def __init__(self):
        s3_config = Config(
            signature_version="s3v4",
            s3={
                "addressing_style": "path",
            },
        )

        # ---------------------------------------------------------
        # Internal client
        # Django container -> MinIO container
        # ---------------------------------------------------------
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.MINIO_ENDPOINT,
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            region_name=settings.MINIO_REGION,
            use_ssl=settings.MINIO_SECURE,
            config=s3_config,
        )

        # ---------------------------------------------------------
        # Presigning client
        # Used to generate URLs accessible by browser/Postman
        # ---------------------------------------------------------
        self.presign_client = boto3.client(
            "s3",
            endpoint_url=settings.MINIO_PUBLIC_ENDPOINT,
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            region_name=settings.MINIO_REGION,
            use_ssl=settings.MINIO_PUBLIC_SECURE,
            config=s3_config,
        )

        self.bucket_name = settings.MINIO_BUCKET_NAME

    # =============================================================
    # Presigned upload URL
    # =============================================================

    def generate_upload_url(
        self,
        key: str,
        content_type: str,
    ) -> str:
        """
        Generate a presigned PUT URL.

        Content-Type is intentionally NOT included in the signed
        parameters. This avoids signature mismatches caused by
        clients modifying or omitting Content-Type.

        The returned URL is signed using MINIO_PUBLIC_ENDPOINT.
        """

        try:
            return self.presign_client.generate_presigned_url(
                ClientMethod="put_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": key,
                },
                ExpiresIn=settings.MINIO_PRESIGNED_UPLOAD_EXPIRATION,
                HttpMethod="PUT",
            )

        except (ClientError, BotoCoreError) as exc:
            raise MinIOStorageError("Unable to generate upload URL.") from exc

    # =============================================================
    # Presigned download URL
    # =============================================================

    def generate_download_url(
        self,
        key: str,
        filename: str,
        content_type: str,
    ) -> str:
        """
        Generate a presigned GET URL for downloading a document.
        """

        try:
            content_disposition = (
                "attachment; " f"filename*=UTF-8''{self._encode_filename(filename)}"
            )

            return self.presign_client.generate_presigned_url(
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

    # =============================================================
    # Check whether an object exists
    # =============================================================

    def head_object(self, key: str) -> dict | None:
        """
        Retrieve metadata for an object.

        Returns:
            dict: MinIO/S3 object metadata if the object exists.
            None: if the object does not exist.
        """

        try:
            return self.client.head_object(
                Bucket=self.bucket_name,
                Key=key,
            )

        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")

            if error_code in {
                "404",
                "NoSuchKey",
                "NotFound",
            }:
                return None

            raise MinIOStorageError("Unable to check uploaded object.") from exc

        except BotoCoreError as exc:
            raise MinIOStorageError("Unable to check uploaded object.") from exc

    # =============================================================
    # Calculate SHA-256
    # =============================================================

    def calculate_sha256(
        self,
        key: str,
    ) -> str:
        """
        Calculate SHA-256 checksum of an object stored in MinIO.

        The object is streamed in chunks rather than loaded
        completely into memory.
        """

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

    # =============================================================
    # Delete object
    # =============================================================

    def delete_object(
        self,
        key: str,
    ) -> None:
        """
        Delete an object from MinIO.
        """

        try:
            self.client.delete_object(
                Bucket=self.bucket_name,
                Key=key,
            )

        except (ClientError, BotoCoreError) as exc:
            raise MinIOStorageError("Unable to delete file.") from exc

    # =============================================================
    # Private helpers
    # =============================================================

    @staticmethod
    def _encode_filename(
        filename: str,
    ) -> str:
        """
        URL-encode a filename for Content-Disposition.
        """

        return quote(
            filename,
            safe="",
        )
