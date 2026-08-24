MAX_FILE_SIZE = 25 * 1024 * 1024


DOCUMENT_STATUS_PENDING = "pending"
DOCUMENT_STATUS_UPLOADED = "uploaded"
DOCUMENT_STATUS_FAILED = "failed"


DOCUMENT_STATUS_CHOICES = (
    (DOCUMENT_STATUS_PENDING, "Pending"),
    (DOCUMENT_STATUS_UPLOADED, "Uploaded"),
    (DOCUMENT_STATUS_FAILED, "Failed"),
)


ALLOWED_FILE_TYPES = {
    "pdf": {
        "application/pdf",
    },
    "doc": {
        "application/msword",
    },
    "docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    },
    "xls": {
        "application/vnd.ms-excel",
    },
    "xlsx": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    },
    "ppt": {
        "application/vnd.ms-powerpoint",
    },
    "pptx": {
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    },
    "txt": {
        "text/plain",
    },
    "csv": {
        "text/csv",
        "application/csv",
    },
    "jpg": {
        "image/jpeg",
    },
    "jpeg": {
        "image/jpeg",
    },
    "png": {
        "image/png",
    },
    "gif": {
        "image/gif",
    },
    "webp": {
        "image/webp",
    },
    "bmp": {
        "image/bmp",
    },
    "tif": {
        "image/tiff",
    },
    "tiff": {
        "image/tiff",
    },
}
