import logging
import logging
from datetime import datetime
from urllib import request

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken

from .models import AppointmentRequest, ProviderProfile, ProviderRequest
from .serializers import (
    LoginSerializer,
    RegisterSerializer,
    ProfileSerializer,
    AppointmentRequestSerializer,
    ProviderProfileSerializer,
    ProviderRequestSerializer,
)

User = get_user_model()
logger = logging.getLogger(__name__)


def has_confirmed_slot_conflict(provider_name, preferred_date, preferred_time, exclude_id=None):
    queryset = AppointmentRequest.objects.filter(
        provider_name__iexact=provider_name,
        preferred_date=preferred_date,
        preferred_time=preferred_time,
        status=AppointmentRequest.STATUS_CONFIRMED,
    )
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)
    return queryset.exists()


def send_appointment_notification(appointment):
    patient_name = " ".join(
        part for part in [appointment.patient.first_name, appointment.patient.last_name] if part
    ).strip() or appointment.patient.username
    recipient = appointment.patient.email or appointment.patient.username
    message = (
        f"Would send appointment confirmation email to {recipient} "
        f"for {patient_name}: appointment is confirmed for {appointment.preferred_date} "
        f"at {appointment.preferred_time}."
    )
    logger.info(message)
    return message


class ProviderRequestCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        provider_request = ProviderRequest.objects.filter(patient=request.user).order_by("-created_at").first()
        if not provider_request:
            return Response({"status": "not_submitted"}, status=status.HTTP_200_OK)
        return Response({
            "status": provider_request.status,
            "first_name": provider_request.first_name,
            "last_name": provider_request.last_name,
            "email": provider_request.email,
            "specialty": provider_request.specialty,
            "license_number": provider_request.license_number,
        }, status=status.HTTP_200_OK)

    def post(self, request):
        if ProviderRequest.objects.filter(patient=request.user).exists():
            return Response(
                {"detail": "Your provider application is already tracked."},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = ProviderRequestSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        provider_request = serializer.save()
        provider_request.status = ProviderRequest.STATUS_APPROVED
        provider_request.save(update_fields=["status", "updated_at"])

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ApprovedProviderListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        providers = ProviderRequest.objects.all().filter(status=ProviderRequest.STATUS_APPROVED)

        serializer = ProviderRequestSerializer(providers, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ProviderAppointmentListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        provider_request = ProviderRequest.objects.filter(
            patient=request.user,
            status=ProviderRequest.STATUS_APPROVED,
        ).first()
        provider_name = ""

        if provider_request:
            provider_name = " ".join(
                part for part in [provider_request.first_name, provider_request.last_name] if part
            ).strip() or request.user.username
        else:
            full_name = " ".join(
                part for part in [request.user.first_name, request.user.last_name] if part
            ).strip()
            provider_name = full_name or request.user.username

        appointments = AppointmentRequest.objects.filter(provider_name__icontains=provider_name)
        serializer = AppointmentRequestSerializer(appointments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AppointmentListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        appointments = AppointmentRequest.objects.filter(patient=request.user)
        serializer = AppointmentRequestSerializer(appointments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = AppointmentRequestSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


def parse_version(value):
    if not value:
        return None

    if isinstance(value, str):
        value = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return value


class AppointmentCancelAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            appointment = AppointmentRequest.objects.get(pk=pk, patient=request.user)
        except AppointmentRequest.DoesNotExist:
            return Response({"detail": "Appointment not found."}, status=status.HTTP_404_NOT_FOUND)

        base_updated_at = parse_version(request.data.get("base_updated_at"))
        if base_updated_at and appointment.updated_at and appointment.updated_at > base_updated_at:
            return Response(
                {
                    "detail": "This appointment changed while you were viewing it. Please refresh and try again.",
                    "stale": True,
                },
                status=status.HTTP_409_CONFLICT,
            )

        if appointment.status != AppointmentRequest.STATUS_CONFIRMED:
            return Response(
                {"detail": "Only confirmed appointments can be cancelled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        appointment.status = AppointmentRequest.STATUS_CANCELLED
        appointment.save(update_fields=["status", "updated_at"])
        serializer = AppointmentRequestSerializer(appointment)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AppointmentProviderActionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            appointment = AppointmentRequest.objects.get(pk=pk)
        except AppointmentRequest.DoesNotExist:
            return Response({"detail": "Appointment not found."}, status=status.HTTP_404_NOT_FOUND)

        base_updated_at = parse_version(request.data.get("base_updated_at"))
        if base_updated_at and appointment.updated_at and appointment.updated_at > base_updated_at:
            return Response(
                {
                    "detail": "This appointment changed while you were viewing it. Please refresh and try again.",
                    "stale": True,
                },
                status=status.HTTP_409_CONFLICT,
            )
        provider_request = ProviderRequest.objects.filter(
            patient=request.user,
            status=ProviderRequest.STATUS_APPROVED,
        ).first()
        if not provider_request:
            return Response(
                {"detail": "Only approved providers can manage appointments."},
                status=status.HTTP_403_FORBIDDEN,
            )
        provider_name = " ".join(
            part for part in [provider_request.first_name, provider_request.last_name] if part
        ).strip() or request.user.username

        if appointment.provider_name and appointment.provider_name.strip() and appointment.provider_name.strip().lower() != provider_name.lower():
            return Response(
                {"detail": "This appointment is not assigned to your provider profile."},
                status=status.HTTP_403_FORBIDDEN,
            )

        action = request.data.get("action")
        if action == "confirm":
            if appointment.status == AppointmentRequest.STATUS_CANCELLED:
                return Response(
                    {"detail": "Cancelled appointments cannot be confirmed."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            with transaction.atomic():
                AppointmentRequest.objects.select_for_update().filter(pk=appointment.pk).exists()
                if has_confirmed_slot_conflict(
                    provider_name,
                    appointment.preferred_date,
                    appointment.preferred_time,
                    exclude_id=appointment.pk,
                ):
                    return Response(
                        {
                            "detail": "This provider already has a confirmed appointment at that date and time.",
                            "conflict": True,
                        },
                        status=status.HTTP_409_CONFLICT,
                    )

                appointment.status = AppointmentRequest.STATUS_CONFIRMED
                appointment.save(update_fields=["status", "updated_at"])

            try:
                send_appointment_notification(appointment)
            except Exception:
                logger.exception("Appointment confirmation notification failed for appointment %s", appointment.id)
            serializer = AppointmentRequestSerializer(appointment)
            return Response(serializer.data, status=status.HTTP_200_OK)

        if action == "reschedule":
            if appointment.status == AppointmentRequest.STATUS_CANCELLED:
                return Response(
                    {"detail": "Cancelled appointments cannot be rescheduled."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            preferred_date = request.data.get("preferred_date")
            preferred_time = request.data.get("preferred_time")
            if not preferred_date or not preferred_time:
                return Response(
                    {"detail": "preferred_date and preferred_time are required for rescheduling."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            with transaction.atomic():
                AppointmentRequest.objects.select_for_update().filter(pk=appointment.pk).exists()
                if has_confirmed_slot_conflict(
                    provider_name,
                    preferred_date,
                    preferred_time,
                    exclude_id=appointment.pk,
                ):
                    return Response(
                        {
                            "detail": "This provider already has a confirmed appointment at that date and time.",
                            "conflict": True,
                        },
                        status=status.HTTP_409_CONFLICT,
                    )

                appointment.preferred_date = preferred_date
                appointment.preferred_time = preferred_time
                appointment.save(update_fields=["preferred_date", "preferred_time", "updated_at"])
            serializer = AppointmentRequestSerializer(appointment)
            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(
            {"detail": "Unsupported action. Use 'confirm' or 'reschedule'."},
            status=status.HTTP_400_BAD_REQUEST,
        )


class PatientDashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = ProfileSerializer(request.user).data
        appointments = AppointmentRequest.objects.filter(patient=request.user)
        approved_providers = ProviderRequest.objects.filter(status=ProviderRequest.STATUS_APPROVED)

        return Response(
            {
                "profile": profile,
                "appointments": AppointmentRequestSerializer(appointments, many=True).data,
                "approved_providers": ProviderRequestSerializer(approved_providers, many=True).data,
            },
            status=status.HTTP_200_OK,
        )


class ProviderDashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        provider_request = ProviderRequest.objects.filter(
            patient=request.user,
            status=ProviderRequest.STATUS_APPROVED,
        ).first()
        if not provider_request:
            return Response(
                {"detail": "Provider profile not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        provider_name = " ".join(
            part for part in [provider_request.first_name, provider_request.last_name] if part
        ).strip() or request.user.username
        appointments = AppointmentRequest.objects.filter(provider_name__icontains=provider_name)

        return Response(
            {
                "provider": ProviderRequestSerializer(provider_request).data,
                "appointments": AppointmentRequestSerializer(appointments, many=True).data,
            },
            status=status.HTTP_200_OK,
        )


class ProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = ProfileSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request):
        serializer = ProfileSerializer(
            request.user,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class LoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(
            data=request.data,
            context={"request": request},
        )

        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "message": "Login successful",
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                },
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_200_OK,
        )


class RegisterAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.save()
        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "message": "Registration successful",
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                },
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )