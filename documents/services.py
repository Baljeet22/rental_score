import uuid
from pathlib import Path

from django.db import transaction
from django.utils import timezone

from .constants import (
    ALLOWED_FILE_TYPES,
    DOCUMENT_STATUS_FAILED,
    DOCUMENT_STATUS_PENDING,
    DOCUMENT_STATUS_UPLOADED,
    MAX_FILE_SIZE,
)
from .models import Document
from .storage import MinIOStorage, MinIOStorageError


class DocumentService:
    def __init__(self):
        self.storage = MinIOStorage()

    @staticmethod
    def generate_s3_key(
        user_id: int,
        filename: str,
    ) -> str:
        extension = Path(filename).suffix.lower()

        unique_id = uuid.uuid4()

        return f"documents/" f"{user_id}/" f"{unique_id}" f"{extension}"

    @staticmethod
    def validate_file_metadata(
        filename: str,
        content_type: str,
        file_size: int,
    ) -> str:

        if not filename:
            raise ValueError("Filename is required.")

        if file_size <= 0:
            raise ValueError("File must be greater than 0 bytes.")

        if file_size > MAX_FILE_SIZE:
            raise ValueError("Maximum file size is 25 MB.")

        extension = Path(filename).suffix.lower().lstrip(".")

        if not extension:
            raise ValueError("File must have an extension.")

        allowed_mime_types = ALLOWED_FILE_TYPES.get(extension)

        if not allowed_mime_types:
            raise ValueError("This file type is not supported.")

        if content_type not in allowed_mime_types:
            raise ValueError("File extension and content type do not match.")

        return extension

    @staticmethod
    def clean_user_filename(
        filename: str,
    ) -> str:
        filename = filename.strip()

        filename = filename.replace(
            "/",
            "_",
        ).replace(
            "\\",
            "_",
        )

        filename = "".join(character for character in filename if ord(character) >= 32)

        return filename[:255]

    @staticmethod
    def build_download_filename(
        uf_name: str,
        original_filename: str,
    ) -> str:
        clean_name = DocumentService.clean_user_filename(uf_name)

        original_extension = Path(original_filename).suffix

        if not original_extension:
            return clean_name

        if clean_name.lower().endswith(original_extension.lower()):
            return clean_name

        return f"{clean_name}{original_extension}"

    @transaction.atomic
    def create_pending_document(
        self,
        *,
        user,
        document_type: str,
        original_filename: str,
        uf_name: str,
        content_type: str,
        file_size: int,
        belongs_to_self: bool,
        group_ref_id: int | None = None,
        docdata: dict | None = None,
    ) -> Document:

        self.validate_file_metadata(
            filename=original_filename,
            content_type=content_type,
            file_size=file_size,
        )

        original_filename = self.clean_user_filename(original_filename)

        uf_name = self.clean_user_filename(uf_name)

        if not uf_name:
            raise ValueError("User-facing filename is required.")

        belongs_to = user if belongs_to_self else None

        group_ref = None

        if group_ref_id is not None:

            group_ref = Document.objects.filter(
                id=group_ref_id,
                deleted_at__isnull=True,
                user=user,
            ).first()

            if group_ref is None:
                raise ValueError("Invalid group reference.")

            if group_ref.group_ref_id != group_ref.id:
                raise ValueError("The selected document is not a primary document.")

            if group_ref.status != DOCUMENT_STATUS_UPLOADED:
                raise ValueError("The selected primary document is not ready.")

        s3_key = self.generate_s3_key(
            user_id=user.id,
            filename=original_filename,
        )

        document = Document.objects.create(
            user=user,
            belongs_to=belongs_to,
            group_ref=group_ref,
            document_type=document_type,
            is_verified=False,
            original_filename=original_filename,
            uf_name=uf_name,
            s3_key=s3_key,
            content_type=content_type,
            file_size=file_size,
            status=DOCUMENT_STATUS_PENDING,
            docdata=docdata or {},
        )

        # Primary document:
        #
        # id = 101
        # group_ref_id = 101
        #
        # Related document:
        #
        # id = 102
        # group_ref_id = 101

        if document.group_ref_id is None:
            document.group_ref_id = document.id
            document.save(
                update_fields=[
                    "group_ref",
                    "updated_at",
                ]
            )

        return document

    def generate_upload_url(
        self,
        document: Document,
    ) -> str:

        return self.storage.generate_upload_url(
            key=document.s3_key,
            content_type=document.content_type,
        )

    @transaction.atomic
    def finalize_document(
        self,
        *,
        document_id: int,
        user,
    ) -> Document:

        document = (
            Document.objects.select_for_update()
            .filter(
                id=document_id,
                deleted_at__isnull=True,
                user=user,
            )
            .first()
        )

        if document is None:
            raise ValueError("Document not found.")

        if document.status == DOCUMENT_STATUS_UPLOADED:
            return document

        if document.status != DOCUMENT_STATUS_PENDING:
            raise ValueError("Document cannot be finalized.")

        try:
            object_info = self.storage.head_object(document.s3_key)

            if object_info is None:
                document.status = DOCUMENT_STATUS_FAILED
                document.save(
                    update_fields=[
                        "status",
                        "updated_at",
                    ]
                )

                raise ValueError("File was not found in storage.")

            actual_size = object_info.get("ContentLength")

            if actual_size != document.file_size:
                document.status = DOCUMENT_STATUS_FAILED

                document.save(
                    update_fields=[
                        "status",
                        "updated_at",
                    ]
                )

                raise ValueError("Uploaded file size does not match.")

            actual_content_type = object_info.get("ContentType")

            if actual_content_type and actual_content_type != document.content_type:
                document.status = DOCUMENT_STATUS_FAILED

                document.save(
                    update_fields=[
                        "status",
                        "updated_at",
                    ]
                )

                raise ValueError("Uploaded file content type does not match.")

            checksum = self.storage.calculate_sha256(document.s3_key)

            document.checksum = checksum
            document.status = DOCUMENT_STATUS_UPLOADED

            document.save(
                update_fields=[
                    "checksum",
                    "status",
                    "updated_at",
                ]
            )

            return document

        except MinIOStorageError:

            document.status = DOCUMENT_STATUS_FAILED

            document.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

            raise

    @transaction.atomic
    def soft_delete(
        self,
        *,
        document_id: int,
        user,
    ) -> Document:

        document = (
            Document.objects.select_for_update()
            .filter(
                id=document_id,
                user=user,
                deleted_at__isnull=True,
            )
            .first()
        )

        if document is None:
            raise ValueError("Document not found.")

        document.deleted_at = timezone.now()

        document.save(
            update_fields=[
                "deleted_at",
                "updated_at",
            ]
        )

        return document


import uuid
from pathlib import Path

from django.db import transaction
from django.utils import timezone

from .constants import (
    ALLOWED_FILE_TYPES,
    DOCUMENT_STATUS_FAILED,
    DOCUMENT_STATUS_PENDING,
    DOCUMENT_STATUS_UPLOADED,
    MAX_FILE_SIZE,
)
from .models import Document
from .storage import MinIOStorage, MinIOStorageError


class DocumentService:
    def __init__(self):
        self.storage = MinIOStorage()

    @staticmethod
    def generate_s3_key(
        user_id: int,
        filename: str,
    ) -> str:
        extension = Path(filename).suffix.lower()

        unique_id = uuid.uuid4()

        return f"documents/" f"{user_id}/" f"{unique_id}" f"{extension}"

    @staticmethod
    def validate_file_metadata(
        filename: str,
        content_type: str,
        file_size: int,
    ) -> str:

        if not filename:
            raise ValueError("Filename is required.")

        if file_size <= 0:
            raise ValueError("File must be greater than 0 bytes.")

        if file_size > MAX_FILE_SIZE:
            raise ValueError("Maximum file size is 25 MB.")

        extension = Path(filename).suffix.lower().lstrip(".")

        if not extension:
            raise ValueError("File must have an extension.")

        allowed_mime_types = ALLOWED_FILE_TYPES.get(extension)

        if not allowed_mime_types:
            raise ValueError("This file type is not supported.")

        if content_type not in allowed_mime_types:
            raise ValueError("File extension and content type do not match.")

        return extension

    @staticmethod
    def clean_user_filename(
        filename: str,
    ) -> str:
        filename = filename.strip()

        filename = filename.replace(
            "/",
            "_",
        ).replace(
            "\\",
            "_",
        )

        filename = "".join(character for character in filename if ord(character) >= 32)

        return filename[:255]

    @staticmethod
    def build_download_filename(
        uf_name: str,
        original_filename: str,
    ) -> str:
        clean_name = DocumentService.clean_user_filename(uf_name)

        original_extension = Path(original_filename).suffix

        if not original_extension:
            return clean_name

        if clean_name.lower().endswith(original_extension.lower()):
            return clean_name

        return f"{clean_name}{original_extension}"

    @transaction.atomic
    def create_pending_document(
        self,
        *,
        user,
        document_type: str,
        original_filename: str,
        uf_name: str,
        content_type: str,
        file_size: int,
        belongs_to_self: bool,
        group_ref_id: int | None = None,
        docdata: dict | None = None,
    ) -> Document:

        self.validate_file_metadata(
            filename=original_filename,
            content_type=content_type,
            file_size=file_size,
        )

        original_filename = self.clean_user_filename(original_filename)

        uf_name = self.clean_user_filename(uf_name)

        if not uf_name:
            raise ValueError("User-facing filename is required.")

        belongs_to = user if belongs_to_self else None

        group_ref = None

        if group_ref_id is not None:

            group_ref = Document.objects.filter(
                id=group_ref_id,
                deleted_at__isnull=True,
                user=user,
            ).first()

            if group_ref is None:
                raise ValueError("Invalid group reference.")

            if group_ref.group_ref_id != group_ref.id:
                raise ValueError("The selected document is not a primary document.")

            if group_ref.status != DOCUMENT_STATUS_UPLOADED:
                raise ValueError("The selected primary document is not ready.")

        s3_key = self.generate_s3_key(
            user_id=user.id,
            filename=original_filename,
        )

        document = Document.objects.create(
            user=user,
            belongs_to=belongs_to,
            group_ref=group_ref,
            document_type=document_type,
            is_verified=False,
            original_filename=original_filename,
            uf_name=uf_name,
            s3_key=s3_key,
            content_type=content_type,
            file_size=file_size,
            status=DOCUMENT_STATUS_PENDING,
            docdata=docdata or {},
        )

        # Primary document:
        #
        # id = 101
        # group_ref_id = 101
        #
        # Related document:
        #
        # id = 102
        # group_ref_id = 101

        if document.group_ref_id is None:
            document.group_ref_id = document.id
            document.save(
                update_fields=[
                    "group_ref",
                    "updated_at",
                ]
            )

        return document

    def generate_upload_url(
        self,
        document: Document,
    ) -> str:

        return self.storage.generate_upload_url(
            key=document.s3_key,
            content_type=document.content_type,
        )

    @transaction.atomic
    def finalize_document(
        self,
        *,
        document_id: int,
        user,
    ) -> Document:

        document = (
            Document.objects.select_for_update()
            .filter(
                id=document_id,
                deleted_at__isnull=True,
                user=user,
            )
            .first()
        )

        if document is None:
            raise ValueError("Document not found.")

        if document.status == DOCUMENT_STATUS_UPLOADED:
            return document

        if document.status != DOCUMENT_STATUS_PENDING:
            raise ValueError("Document cannot be finalized.")

        try:
            object_info = self.storage.head_object(document.s3_key)

            if object_info is None:
                document.status = DOCUMENT_STATUS_FAILED
                document.save(
                    update_fields=[
                        "status",
                        "updated_at",
                    ]
                )

                raise ValueError("File was not found in storage.")

            actual_size = object_info.get("ContentLength")

            if actual_size != document.file_size:
                document.status = DOCUMENT_STATUS_FAILED

                document.save(
                    update_fields=[
                        "status",
                        "updated_at",
                    ]
                )

                raise ValueError("Uploaded file size does not match.")

            actual_content_type = object_info.get("ContentType")

            if actual_content_type and actual_content_type != document.content_type:
                document.status = DOCUMENT_STATUS_FAILED

                document.save(
                    update_fields=[
                        "status",
                        "updated_at",
                    ]
                )

                raise ValueError("Uploaded file content type does not match.")

            checksum = self.storage.calculate_sha256(document.s3_key)

            document.checksum = checksum
            document.status = DOCUMENT_STATUS_UPLOADED

            document.save(
                update_fields=[
                    "checksum",
                    "status",
                    "updated_at",
                ]
            )

            return document

        except MinIOStorageError:

            document.status = DOCUMENT_STATUS_FAILED

            document.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

            raise

    @transaction.atomic
    def soft_delete(
        self,
        *,
        document_id: int,
        user,
    ) -> Document:

        document = (
            Document.objects.select_for_update()
            .filter(
                id=document_id,
                user=user,
                deleted_at__isnull=True,
            )
            .first()
        )

        if document is None:
            raise ValueError("Document not found.")

        document.deleted_at = timezone.now()

        document.save(
            update_fields=[
                "deleted_at",
                "updated_at",
            ]
        )

        return document
