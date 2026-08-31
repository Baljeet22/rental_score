import base64
import json
from urllib.parse import urlencode

from django.db.models import Q
from django.utils.dateparse import parse_datetime

from rest_framework.exceptions import NotFound
from rest_framework.pagination import BasePagination
from rest_framework.response import Response


class DocumentGroupPagination(BasePagination):
    """
    Cursor pagination for document groups.

    Pagination rules:

    1. Groups are ordered by:
           -created_at
           -group_ref_id

    2. A page contains at least `min_files` documents.

    3. A group is never split between pages.

    4. If a single group contains more than `min_files`,
       the complete group is returned.

    5. Pagination is cursor-based rather than offset-based.
    """

    default_min_files = 10
    max_min_files = 100

    def paginate_queryset(
        self,
        queryset,
        request,
        view=None,
    ):
        self.request = request

        self.min_files = self._get_min_files(
            request,
        )

        cursor = request.query_params.get(
            "cursor",
        )

        direction = request.query_params.get(
            "direction",
            "next",
        )

        if direction not in {"next", "previous"}:
            raise NotFound("Invalid pagination direction.")

        self.direction = direction

        # Keep the complete group queryset.
        self.base_queryset = queryset

        # Apply cursor.
        working_queryset = queryset

        if cursor:
            cursor_data = self._decode_cursor(
                cursor,
            )

            working_queryset = self._apply_cursor(
                queryset=working_queryset,
                cursor_data=cursor_data,
                direction=direction,
            )

        # Reverse ordering when going backwards.
        if direction == "previous":
            working_queryset = working_queryset.order_by(
                "created_at",
                "group_ref_id",
            )

        selected_groups = []
        file_count = 0

        for group in working_queryset.iterator():
            selected_groups.append(group)

            file_count += group["file_count"]

            if file_count >= self.min_files:
                break

        if direction == "previous":
            selected_groups.reverse()

        self.page = selected_groups
        self.file_count = file_count

        self.next_cursor = None
        self.previous_cursor = None

        if not selected_groups:
            return selected_groups

        first_group = selected_groups[0]
        last_group = selected_groups[-1]

        # ---------------------------------------------------------
        # NEXT
        # ---------------------------------------------------------

        if self._has_groups_after(
            queryset=self.base_queryset,
            group=last_group,
        ):
            self.next_cursor = self._encode_cursor(
                created_at=last_group["created_at"],
                group_ref_id=last_group["group_ref_id"],
            )

        # ---------------------------------------------------------
        # PREVIOUS
        # ---------------------------------------------------------

        if self._has_groups_before(
            queryset=self.base_queryset,
            group=first_group,
        ):
            self.previous_cursor = self._encode_cursor(
                created_at=first_group["created_at"],
                group_ref_id=first_group["group_ref_id"],
            )

        return selected_groups

    def get_paginated_response(
        self,
        data,
    ):
        return Response(
            {
                "min_files": self.min_files,
                "file_count": self.file_count,
                "group_count": len(self.page),
                "next": self._build_url(
                    cursor=self.next_cursor,
                    direction="next",
                ),
                "previous": self._build_url(
                    cursor=self.previous_cursor,
                    direction="previous",
                ),
                "results": data,
            }
        )

    # =============================================================
    # min_files
    # =============================================================

    def _get_min_files(
        self,
        request,
    ):
        value = request.query_params.get(
            "min_files",
            self.default_min_files,
        )

        try:
            value = int(value)
        except (TypeError, ValueError):
            raise NotFound("min_files must be a valid integer.")

        if value <= 0:
            raise NotFound("min_files must be greater than 0.")

        if value > self.max_min_files:
            raise NotFound(
                f"min_files cannot be greater than " f"{self.max_min_files}."
            )

        return value

    # =============================================================
    # Cursor encoding / decoding
    # =============================================================

    @staticmethod
    def _encode_cursor(
        *,
        created_at,
        group_ref_id,
    ):
        payload = {
            "created_at": created_at.isoformat(),
            "group_ref_id": group_ref_id,
        }

        encoded = base64.urlsafe_b64encode(
            json.dumps(
                payload,
                separators=(",", ":"),
            ).encode(),
        ).decode()

        return encoded

    @staticmethod
    def _decode_cursor(
        cursor,
    ):
        try:
            decoded = base64.urlsafe_b64decode(
                cursor.encode(),
            )

            data = json.loads(
                decoded.decode(),
            )

            created_at = parse_datetime(
                data["created_at"],
            )

            if created_at is None:
                raise ValueError

            group_ref_id = int(
                data["group_ref_id"],
            )

            return {
                "created_at": created_at,
                "group_ref_id": group_ref_id,
            }

        except (
            ValueError,
            TypeError,
            KeyError,
            json.JSONDecodeError,
        ):
            raise NotFound("Invalid pagination cursor.")

    # =============================================================
    # Cursor filtering
    # =============================================================

    @staticmethod
    def _apply_cursor(
        *,
        queryset,
        cursor_data,
        direction,
    ):
        created_at = cursor_data["created_at"]
        group_ref_id = cursor_data["group_ref_id"]

        if direction == "next":
            return queryset.filter(
                Q(
                    created_at__lt=created_at,
                )
                | Q(
                    created_at=created_at,
                    group_ref_id__lt=group_ref_id,
                )
            )

        return queryset.filter(
            Q(
                created_at__gt=created_at,
            )
            | Q(
                created_at=created_at,
                group_ref_id__gt=group_ref_id,
            )
        )

    # =============================================================
    # Check whether groups exist before / after
    # =============================================================

    @staticmethod
    def _has_groups_after(
        *,
        queryset,
        group,
    ):
        return queryset.filter(
            Q(
                created_at__lt=group["created_at"],
            )
            | Q(
                created_at=group["created_at"],
                group_ref_id__lt=group["group_ref_id"],
            )
        ).exists()

    @staticmethod
    def _has_groups_before(
        *,
        queryset,
        group,
    ):
        return queryset.filter(
            Q(
                created_at__gt=group["created_at"],
            )
            | Q(
                created_at=group["created_at"],
                group_ref_id__gt=group["group_ref_id"],
            )
        ).exists()

    # =============================================================
    # URL generation
    # =============================================================

    def _build_url(
        self,
        *,
        cursor,
        direction,
    ):
        if not cursor:
            return None

        query_params = self.request.query_params.copy()

        query_params["cursor"] = cursor
        query_params["direction"] = direction

        return (
            self.request.build_absolute_uri(
                self.request.path,
            )
            + "?"
            + urlencode(query_params)
        )
