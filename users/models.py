from django.contrib.auth.models import AbstractUser
from django.db import models

from .managers import UserManager


class User(AbstractUser):
    """
    Custom user model.

    Uses email address as the unique authentication identifier
    instead of Django's default username field.
    """

    username = None

    email = models.EmailField(
        unique=True,
        db_index=True,
    )

    middle_name = models.CharField(
        max_length=150,
        blank=True,
    )

    dob = models.DateField(
        null=True,
        blank=True,
    )

    is_owner = models.BooleanField(
        default=False,
    )

    is_tenant = models.BooleanField(
        default=False,
    )

    address = models.JSONField(
        null=True,
        blank=True,
    )

    is_verified = models.BooleanField(
        default=False,
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email
