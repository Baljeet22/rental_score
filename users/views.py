from rest_framework import generics
from rest_framework.permissions import AllowAny

from .serializers import UserSignupSerializer


class UserSignupAPIView(generics.CreateAPIView):
    """
    API endpoint for creating a new user.
    """

    serializer_class = UserSignupSerializer
    permission_classes = [AllowAny]
