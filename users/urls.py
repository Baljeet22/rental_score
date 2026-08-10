from django.urls import path

from .views import UserSignupAPIView

urlpatterns = [
    path(
        "signup/",
        UserSignupAPIView.as_view(),
        name="user-signup",
    ),
]
