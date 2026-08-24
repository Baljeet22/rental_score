import boto3

from botocore.client import Config
from botocore.exceptions import ClientError

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create the configured MinIO bucket if it does not exist."

    def handle(self, *args, **options):
        client = boto3.client(
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

        bucket_name = settings.MINIO_BUCKET_NAME

        try:
            client.head_bucket(
                Bucket=bucket_name,
            )

            self.stdout.write(
                self.style.SUCCESS(f"Bucket '{bucket_name}' already exists.")
            )

        except ClientError:
            client.create_bucket(
                Bucket=bucket_name,
            )

            self.stdout.write(self.style.SUCCESS(f"Bucket '{bucket_name}' created."))
