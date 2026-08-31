from django.urls import path

from .views import (
    DocumentDetailAPIView,
    DocumentDownloadAPIView,
    DocumentFinalizeUploadAPIView,
    DocumentInitializeUploadAPIView,
    DocumentListAPIView,
    DocumentSoftDeleteAPIView,
)

urlpatterns = [
    path(
        "",
        DocumentInitializeUploadAPIView.as_view(),
        name="document-upload-init",
    ),
    path(
        "list/",
        DocumentListAPIView.as_view(),
        name="document-list",
    ),
    path(
        "<int:pk>/",
        DocumentDetailAPIView.as_view(),
        name="document-detail",
    ),
    path(
        "<int:pk>/finalize/",
        DocumentFinalizeUploadAPIView.as_view(),
        name="document-finalize",
    ),
    path(
        "<int:pk>/download/",
        DocumentDownloadAPIView.as_view(),
        name="document-download",
    ),
    path(
        "<int:pk>/delete/",
        DocumentSoftDeleteAPIView.as_view(),
        name="document-delete",
    ),
]
