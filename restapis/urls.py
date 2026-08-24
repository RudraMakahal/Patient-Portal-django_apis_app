from django.urls import path
from .views import (
    LoginAPIView,
    RegisterAPIView,
    ProfileAPIView,
    PatientDashboardAPIView,
    ProviderDashboardAPIView,
    AppointmentListCreateAPIView,
    AppointmentCancelAPIView,
    AppointmentProviderActionAPIView,
    ProviderRequestCreateAPIView,
    ApprovedProviderListAPIView,
    ProviderAppointmentListAPIView,
)

urlpatterns = [
    path("login", LoginAPIView.as_view(), name="login"),
    path("register", RegisterAPIView.as_view(), name="register"),
    path("profile", ProfileAPIView.as_view(), name="profile"),
    path("patient-dashboard", PatientDashboardAPIView.as_view(), name="patient-dashboard"),
    path("provider-dashboard", ProviderDashboardAPIView.as_view(), name="provider-dashboard"),
    path("appointments", AppointmentListCreateAPIView.as_view(), name="appointments"),
    path("appointments/<int:pk>/cancel/", AppointmentCancelAPIView.as_view(), name="appointment-cancel"),
    path("appointments/<int:pk>/provider-action/", AppointmentProviderActionAPIView.as_view(), name="appointment-provider-action"),
    path("provider-requests", ProviderRequestCreateAPIView.as_view(), name="provider-requests"),
    path("providers/approved", ApprovedProviderListAPIView.as_view(), name="approved-providers"),
    path("providers/appointments", ProviderAppointmentListAPIView.as_view(), name="provider-appointments"),
]