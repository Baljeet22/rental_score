from datetime import timedelta
from django.contrib.auth import authenticate, tokens
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework.generics import GenericAPIView


from .serializers import (
    UserSignupSerializer,
    LoginSerializer,
    RoleSelectionSerializer,
    LogoutSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer,
)


from django.core.mail import send_mail
from .utils import generate_email_verification_token
from django.utils.http import urlencode, urlsafe_base64_decode
from django.core import signing
from django.contrib.auth import get_user_model
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode

from django.conf import settings


class UserSignupAPIView(generics.CreateAPIView):
    """
    API endpoint for creating a new user.
    """

    serializer_class = UserSignupSerializer
    permission_classes = [AllowAny]

    def perform_create(self, serializer):
        user = serializer.save()

        token = generate_email_verification_token(
            user
        )  # This depends on utils.py helper file

        verification_url = (
            f"{settings.FRONTEND_URL}" f"/api/users/verify-email/" f"?token={token}"
        )

        send_mail(
            subject="Verify your email address",
            message=(
                f"Hello {user.first_name},\n\n"
                f"Please verify your email by clicking the link below:\n\n"
                f"{verification_url}\n\n"
                f"This link is valid for 24 hours."
            ),
            from_email=None,
            recipient_list=[user.email],
            fail_silently=False,
        )


class UserEmailVerificationAPIView(generics.GenericAPIView):
    """
    API endpoint to verify a User email by email link.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        token = request.query_params.get("token")

        if not token:
            return Response(
                {"detail": "Verification token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            data = signing.loads(
                token,
                salt="email-verification",
                max_age=60 * 60 * 24,  # 24 hours
            )
        except signing.SignatureExpired:
            return Response(
                {"detail": "Verification link has expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except signing.BadSignature:
            return Response(
                {"detail": "Invalid verification link."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        User = get_user_model()

        try:
            user = User.objects.get(id=data["user_id"])
        except User.DoesNotExist:
            return Response(
                {"detail": "Invalid verification link."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if user.is_active:
            return Response(
                {"detail": "Email is already verified."},
                status=status.HTTP_200_OK,
            )

        user.is_active = True
        user.save(update_fields=["is_active"])

        return Response(
            {"detail": "Email verified successfully."},
            status=status.HTTP_200_OK,
        )


class UserForgotPasswordAPIView(generics.GenericAPIView):
    """
    API endpoint to create forget password links.
    """

    permission_classes = [AllowAny]
    serializer_class = ForgotPasswordSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]

        User = get_user_model()

        user = User.objects.filter(
            email=email,
            is_active=True,
        ).first()

        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))

            token = tokens.default_token_generator.make_token(user)

            reset_url = (
                f"{settings.FRONTEND_URL}"
                f"/api/users/reset-password/"
                f"?uid={uid}&token={token}"
            )

            send_mail(
                subject="Reset your password",
                message=(
                    f"Hello {user.first_name},\n\n"
                    f"We received a request to reset your password.\n\n"
                    f"Click the link below to reset it:\n\n"
                    f"{reset_url}\n\n"
                    f"If you did not request this, you can ignore this email."
                ),
                from_email=None,
                recipient_list=[user.email],
                fail_silently=False,
            )

        # Always return the same response.
        return Response(
            {
                "detail": (
                    "If an account exists with this email, "
                    "a password reset link has been sent."
                )
            },
            status=status.HTTP_200_OK,
        )


class UserResetPasswordAPIView(generics.GenericAPIView):
    """
    API to reset password by validating link from email.
    """

    permission_classes = [AllowAny]
    serializer_class = ResetPasswordSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uid = serializer.validated_data["uid"]
        token = serializer.validated_data["token"]
        new_password = serializer.validated_data["new_password"]

        User = get_user_model()

        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(
                pk=user_id,
                is_active=True,
            )
        except (
            User.DoesNotExist,
            ValueError,
            TypeError,
            OverflowError,
        ):
            return Response(
                {"detail": "Invalid or expired reset link."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not tokens.default_token_generator.check_token(user, token):
            return Response(
                {"detail": "Invalid or expired reset link."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save(update_fields=["password"])
        # Notify user
        self.send_password_changed_email(user)

        return Response(
            {"detail": "Password has been reset successfully."},
            status=status.HTTP_200_OK,
        )

    def send_password_changed_email(self, user):
        send_mail(
            subject="Your password has been changed",
            message=(
                f"Hello {user.first_name},\n\n"
                "Your password has been successfully changed.\n\n"
                "If you did not make this change, "
                "please contact support immediately.\n\n"
                "Thank you."
            ),
            from_email=None,
            recipient_list=[user.email],
            fail_silently=False,
        )


########GLOBAL FUNCTION#######
def generate_tokens(user, role):
    refresh = RefreshToken.for_user(user)
    refresh["role"] = role

    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
        "role": role,
    }


class UserLoginAPIView(APIView):
    """
    API endpoint for user login.
    """

    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    def get_serializer(self, *args, **kwargs):
        return self.serializer_class(*args, **kwargs)

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            request=request,
            username=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )

        if user is None:
            return Response(
                {
                    "detail": "Invalid email or password or account is still inactive, please check your email.."
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_owner and not user.is_tenant:
            return Response(
                {"detail": "User has no valid role."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if user.is_owner and user.is_tenant:
            challenge = AccessToken()
            challenge["user_id"] = user.id
            challenge["purpose"] = "role_selection"
            challenge.set_exp(lifetime=timedelta(minutes=2))

            return Response(
                {
                    "requires_role_selection": True,
                    "available_roles": ["owner", "tenant"],
                    "challenge_token": str(challenge),
                }
            )

        role = "owner" if user.is_owner else "tenant"

        return Response(generate_tokens(user, role))


class UserRoleSelectionAPIView(GenericAPIView):
    """
    API endpoint to select user role.
    """

    permission_classes = [AllowAny]
    serializer_class = RoleSelectionSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        challenge_token = serializer.validated_data["challenge_token"]

        try:
            challenge = AccessToken(challenge_token)

            if challenge.get("purpose") != "role_selection":
                raise TokenError("Invalid challenge.")

            user_id = challenge["user_id"]

        except TokenError:
            return Response(
                {"detail": "Invalid or expired challenge token."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        role = serializer.validated_data["role"]

        from .models import User

        try:
            user = User.objects.get(
                id=user_id,
                is_active=True,
            )
        except User.DoesNotExist:
            return Response(
                {"detail": "Invalid user."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if role == "owner" and not user.is_owner:
            return Response(
                {"detail": "User is not an owner."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if role == "tenant" and not user.is_tenant:
            return Response(
                {"detail": "User is not a tenant."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(
            generate_tokens(user, role),
            status=status.HTTP_200_OK,
        )


class UserLogoutAPIView(GenericAPIView):
    """
    API endpoint to Logout a User.
    """

    permission_classes = [AllowAny]
    serializer_class = LogoutSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            refresh_token = RefreshToken(serializer.validated_data["refresh"])
            refresh_token.blacklist()

        except TokenError:
            return Response(
                {"detail": "Invalid or expired refresh token."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        return Response(
            {"detail": "Logout successful."},
            status=status.HTTP_200_OK,
        )
