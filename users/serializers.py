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

    def validate(self, attrs):
        """
        Checking if Data coming is valid.
        """
        is_owner = attrs.get("is_owner")
        is_tenant = attrs.get("is_tenant")

        if not is_owner and not is_tenant:
            raise serializers.ValidationError(
                {
                    "is_owner": "Select either Owner or Tenant.",
                    "is_tenant": "Select either Owner or Tenant.",
                }
            )

        if is_owner and is_tenant:
            raise serializers.ValidationError(
                {
                    "is_owner": "Owner and Tenant cannot both be selected at this moment.",
                    "is_tenant": "Owner and Tenant cannot both be selected at this moment.",
                }
            )

        return attrs

    def validate_email(self, value):
        return value.strip().lower()

    def create(self, validated_data):
        password = validated_data.pop("password")

        user = User.objects.create_user(
            password=password,
            **validated_data,
        )

        user.is_active = False
        user.save(update_fields=["is_active"])

        return user


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={"input_type": "password"},
    )
    confirm_password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )

        return attrs


class LoginSerializer(serializers.Serializer):
    """
    Serializer used to login    .
    """

    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        style={"input_type": "password"},
    )


class RoleSelectionSerializer(serializers.Serializer):
    challenge_token = serializers.CharField(
        write_only=True,
    )
    role = serializers.ChoiceField(
        choices=[
            ("owner", "Owner"),
            ("tenant", "Tenant"),
        ]
    )


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(
        write_only=True,
        trim_whitespace=True,
        style={"input_type": "password"},
    )
