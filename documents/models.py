from django.conf import settings
from django.db import models
from django.db.models import Q

from .constants import (
    DOCUMENT_STATUS_CHOICES,
    DOCUMENT_STATUS_PENDING,
    MAX_FILE_SIZE,
)


class Document(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="uploaded_documents",
    )

    belongs_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="documents_belonging_to",
    )

    group_ref = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="grouped_documents",
    )

    document_type = models.CharField(
        max_length=50,
    )

    is_verified = models.BooleanField(
        default=False,
    )

    original_filename = models.CharField(
        max_length=255,
    )

    uf_name = models.CharField(
        max_length=255,
    )

    s3_key = models.CharField(
        max_length=500,
        unique=True,
    )

    content_type = models.CharField(
        max_length=255,
    )

    file_size = models.BigIntegerField()

    status = models.CharField(
        max_length=50,
        choices=DOCUMENT_STATUS_CHOICES,
        default=DOCUMENT_STATUS_PENDING,
        db_index=True,
    )

    checksum = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        db_index=True,
    )

    docdata = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )

    class Meta:
        db_table = "documents"

        indexes = [
            models.Index(
                fields=["user", "status"],
                name="document_user_status_idx",
            ),
            models.Index(
                fields=["belongs_to", "status"],
                name="document_belongs_status_idx",
            ),
            models.Index(
                fields=["group_ref"],
                name="document_group_ref_idx",
            ),
            models.Index(
                fields=["document_type"],
                name="document_type_idx",
            ),
            models.Index(
                fields=["created_at"],
                name="document_created_idx",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(file_size__gt=0),
                name="document_file_size_positive",
            ),
            models.CheckConstraint(
                condition=Q(file_size__lte=MAX_FILE_SIZE),
                name="document_file_size_max_25mb",
            ),
        ]

    def __str__(self):
        return f"{self.id} - {self.uf_name}"
