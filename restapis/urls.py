from django.urls import path
from .views import LoginAPIView, RegisterAPIView, ProfileAPIView

urlpatterns = [
    path("login", LoginAPIView.as_view(), name="login"),
    path("register", RegisterAPIView.as_view(), name="register"),
    path("profile", ProfileAPIView.as_view(), name="profile"),
]