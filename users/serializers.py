from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class UserSignupSerializer(serializers.ModelSerializer):
    """
    Serializer used to create a new user.
    """

    password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={"input_type": "password"},
    )

    class Meta:
        model = User
        fields = (
            "email",
            "password",
            "first_name",
            "middle_name",
            "last_name",
            "dob",
            "is_owner",
            "is_tenant",
            "address",
        )

    def validate_email(self, value):
        return value.strip().lower()

    def create(self, validated_data):
        password = validated_data.pop("password")

        return User.objects.create_user(
            email=validated_data.pop("email"),
            password=password,
            **validated_data,
        )
