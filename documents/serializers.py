from pathlib import Path

from rest_framework import serializers

from .constants import ALLOWED_FILE_TYPES, MAX_FILE_SIZE
from .models import Document


class DocumentInitializeSerializer(serializers.Serializer):
    document_type = serializers.CharField(
        max_length=50,
    )

    original_filename = serializers.CharField(
        max_length=255,
    )

    uf_name = serializers.CharField(
        max_length=255,
    )

    content_type = serializers.CharField(
        max_length=255,
    )

    file_size = serializers.IntegerField(
        min_value=1,
        max_value=MAX_FILE_SIZE,
    )

    belongs_to_self = serializers.BooleanField(
        default=False,
    )

    group_ref_id = serializers.IntegerField(
        required=False,
        allow_null=True,
    )

    docdata = serializers.JSONField(
        required=False,
        default=dict,
    )

    def validate(self, attrs):
        filename = attrs["original_filename"]
        content_type = attrs["content_type"]
        file_size = attrs["file_size"]

        extension = Path(filename).suffix.lower().lstrip(".")

        if not extension:
            raise serializers.ValidationError(
                {"original_filename": ("File must have an extension.")}
            )

        allowed_types = ALLOWED_FILE_TYPES.get(extension)

        if not allowed_types:
            raise serializers.ValidationError(
                {"original_filename": ("This file type is not supported.")}
            )

        if content_type not in allowed_types:
            raise serializers.ValidationError(
                {"content_type": ("Content type does not match " "the file extension.")}
            )

        if file_size > MAX_FILE_SIZE:
            raise serializers.ValidationError(
                {"file_size": ("Maximum file size is 25 MB.")}
            )

        docdata = attrs.get(
            "docdata",
            {},
        )

        if not isinstance(docdata, dict):
            raise serializers.ValidationError(
                {"docdata": ("docdata must be a JSON object.")}
            )

        return attrs


class DocumentResponseSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(
        read_only=True,
    )

    belongs_to_id = serializers.IntegerField(
        read_only=True,
    )

    group_ref_id = serializers.IntegerField(
        read_only=True,
    )

    class Meta:
        model = Document

        fields = [
            "id",
            "user_id",
            "belongs_to_id",
            "group_ref_id",
            "document_type",
            "is_verified",
            "original_filename",
            "uf_name",
            "content_type",
            "file_size",
            "status",
            "checksum",
            "docdata",
            "created_at",
            "updated_at",
        ]

        read_only_fields = fields


class DownloadResponseSerializer(serializers.Serializer):
    download_url = serializers.URLField()

    filename = serializers.CharField()

    expires_in = serializers.IntegerField()


class DocumentGroupSerializer(serializers.Serializer):
    group_ref_id = serializers.IntegerField()

    documents = DocumentResponseSerializer(
        many=True,
    )
