from django.contrib import admin

from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "belongs_to",
        "document_type",
        "uf_name",
        "status",
        "is_verified",
        "file_size",
        "created_at",
        "deleted_at",
        "checksum",
    )

    list_filter = (
        "status",
        "is_verified",
        "document_type",
        "created_at",
    )

    search_fields = (
        "original_filename",
        "uf_name",
        "s3_key",
        "checksum",
        "user__email",
    )

    readonly_fields = (
        "s3_key",
        "checksum",
        "created_at",
        "updated_at",
    )
