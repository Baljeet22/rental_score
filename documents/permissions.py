from rest_framework.permissions import BasePermission


class CanAccessDocument(BasePermission):
    """
    Allows:
    - document uploader
    - user the document belongs to
    - Django staff/admin
    """

    def has_object_permission(
        self,
        request,
        view,
        obj,
    ):
        if request.user.is_staff:
            return True

        if obj.user_id == request.user.id:
            return True

        if obj.belongs_to_id and obj.belongs_to_id == request.user.id:
            return True

        return False
