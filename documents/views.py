from django.conf import settings
from django.db.models import Q

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .constants import DOCUMENT_STATUS_UPLOADED
from .models import Document
from .permissions import CanAccessDocument
from .serializers import (
    DocumentInitializeSerializer,
    DocumentResponseSerializer,
    DownloadResponseSerializer,
)
from .services import DocumentService
from .storage import MinIOStorageError


class DocumentInitializeUploadAPIView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request):
        serializer = DocumentInitializeSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        service = DocumentService()

        try:
            document = service.create_pending_document(
                user=request.user,
                **serializer.validated_data,
            )

            upload_url = service.generate_upload_url(document)

        except ValueError as exc:
            return Response(
                {
                    "detail": str(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        except MinIOStorageError:
            return Response(
                {
                    "detail": ("Unable to create upload URL."),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        response_data = DocumentResponseSerializer(document).data

        response_data["upload"] = {
            "method": "PUT",
            "url": upload_url,
            "headers": {
                "Content-Type": document.content_type,
            },
            "expires_in": (settings.MINIO_PRESIGNED_UPLOAD_EXPIRATION),
        }

        return Response(
            response_data,
            status=status.HTTP_201_CREATED,
        )


class DocumentFinalizeUploadAPIView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(
        self,
        request,
        pk,
    ):
        service = DocumentService()

        try:
            document = service.finalize_document(
                document_id=pk,
                user=request.user,
            )

        except ValueError as exc:
            return Response(
                {
                    "detail": str(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        except MinIOStorageError:
            return Response(
                {
                    "detail": ("Unable to verify uploaded file."),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            DocumentResponseSerializer(document).data,
            status=status.HTTP_200_OK,
        )


class DocumentListAPIView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request):
        documents = (
            Document.objects.filter(
                deleted_at__isnull=True,
            )
            .filter(
                Q(user=request.user)
                | Q(belongs_to=request.user)
                | Q(user__is_staff=True)
            )
            .order_by("-created_at")
            .distinct()
        )

        serializer = DocumentResponseSerializer(
            documents,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


class DocumentDetailAPIView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get_object(
        self,
        request,
        pk,
    ):
        document = Document.objects.filter(
            id=pk,
            deleted_at__isnull=True,
        ).first()

        if document is None:
            return None

        permission = CanAccessDocument()

        if not permission.has_object_permission(
            request,
            self,
            document,
        ):
            return None

        return document

    def get(
        self,
        request,
        pk,
    ):
        document = self.get_object(
            request,
            pk,
        )

        if document is None:
            return Response(
                {
                    "detail": "Document not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(DocumentResponseSerializer(document).data)

    def delete(
        self,
        request,
        pk,
    ):
        document = Document.objects.filter(
            id=pk,
            deleted_at__isnull=True,
        ).first()

        if document is None:
            return Response(
                {
                    "detail": "Document not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if document.user_id != request.user.id and not request.user.is_staff:
            return Response(
                {
                    "detail": ("You cannot delete this document."),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        service = DocumentService()

        try:
            service.soft_delete(
                document_id=document.id,
                user=document.user,
            )

        except ValueError as exc:
            return Response(
                {
                    "detail": str(exc),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            status=status.HTTP_204_NO_CONTENT,
        )


class DocumentDownloadAPIView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(
        self,
        request,
        pk,
    ):
        document = Document.objects.filter(
            id=pk,
            deleted_at__isnull=True,
            status=DOCUMENT_STATUS_UPLOADED,
        ).first()

        if document is None:
            return Response(
                {
                    "detail": "Document not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        permission = CanAccessDocument()

        if not permission.has_object_permission(
            request,
            self,
            document,
        ):
            return Response(
                {
                    "detail": "Document not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        service = DocumentService()

        filename = service.build_download_filename(
            uf_name=document.uf_name,
            original_filename=document.original_filename,
        )

        try:
            download_url = service.storage.generate_download_url(
                key=document.s3_key,
                filename=filename,
                content_type=document.content_type,
            )

        except MinIOStorageError:
            return Response(
                {
                    "detail": ("Unable to generate download URL."),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        serializer = DownloadResponseSerializer(
            {
                "download_url": download_url,
                "filename": filename,
                "expires_in": (settings.MINIO_PRESIGNED_DOWNLOAD_EXPIRATION),
            }
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )
