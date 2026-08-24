from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import AppointmentRequest, ProviderProfile, ProviderRequest

User = get_user_model()


class AppointmentCancellationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="patient1",
            email="patient1@example.com",
            password="StrongPass123!",
        )
        self.other_user = User.objects.create_user(
            username="patient2",
            email="patient2@example.com",
            password="StrongPass123!",
        )

    def test_patient_can_cancel_confirmed_appointment(self):
        self.client.force_authenticate(user=self.user)
        appointment = AppointmentRequest.objects.create(
            patient=self.user,
            preferred_date="2026-09-01",
            preferred_time="10:00:00",
            appointment_type="Follow-up",
            reason="Need review.",
            status=AppointmentRequest.STATUS_CONFIRMED,
        )

        response = self.client.patch(f"/apis/appointments/{appointment.id}/cancel/")

        self.assertEqual(response.status_code, 200)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, AppointmentRequest.STATUS_CANCELLED)

    def test_pending_appointment_cannot_be_cancelled(self):
        self.client.force_authenticate(user=self.user)
        appointment = AppointmentRequest.objects.create(
            patient=self.user,
            preferred_date="2026-09-02",
            preferred_time="11:00:00",
            appointment_type="Primary Care",
            reason="Need checkup.",
            status=AppointmentRequest.STATUS_PENDING,
        )

        response = self.client.patch(f"/apis/appointments/{appointment.id}/cancel/")

        self.assertEqual(response.status_code, 400)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, AppointmentRequest.STATUS_PENDING)

    def test_stale_patient_cancel_is_rejected(self):
        self.client.force_authenticate(user=self.user)
        appointment = AppointmentRequest.objects.create(
            patient=self.user,
            preferred_date="2026-09-03",
            preferred_time="10:00:00",
            appointment_type="Follow-up",
            reason="Need see doctor.",
            status=AppointmentRequest.STATUS_CONFIRMED,
        )

        stale_version = (timezone.now() - timedelta(minutes=5)).isoformat()
        response = self.client.patch(
            f"/apis/appointments/{appointment.id}/cancel/",
            {"base_updated_at": stale_version},
            format="json",
        )

        self.assertEqual(response.status_code, 409)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, AppointmentRequest.STATUS_CONFIRMED)

    def test_provider_can_confirm_pending_appointment(self):
        provider = User.objects.create_user(
            username="provider1",
            email="provider1@example.com",
            password="StrongPass123!",
        )
        ProviderRequest.objects.create(
            patient=provider,
            first_name="Dr.",
            last_name="Smith",
            email="provider1@example.com",
            specialty="Cardiology",
            license_number="LIC-1001",
            message="Cardiology provider application",
            status=ProviderRequest.STATUS_APPROVED,
        )
        self.client.force_authenticate(user=provider)
        appointment = AppointmentRequest.objects.create(
            patient=self.user,
            preferred_date="2026-09-03",
            preferred_time="12:30:00",
            provider_name="Dr. Smith",
            appointment_type="Consultation",
            reason="Cardiology consult.",
            status=AppointmentRequest.STATUS_PENDING,
        )

        response = self.client.patch(
            f"/apis/appointments/{appointment.id}/provider-action/",
            {"action": "confirm"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, AppointmentRequest.STATUS_CONFIRMED)

    def test_confirmed_provider_slot_is_unique(self):
        self.client.force_authenticate(user=self.user)
        appointment = AppointmentRequest.objects.create(
            patient=self.user,
            preferred_date="2026-09-10",
            preferred_time="09:00:00",
            provider_name="Dr. Smith",
            appointment_type="Follow-up",
            reason="Initial visit.",
            status=AppointmentRequest.STATUS_CONFIRMED,
        )

        with self.assertRaises(IntegrityError):
            AppointmentRequest.objects.create(
                patient=self.user,
                preferred_date=appointment.preferred_date,
                preferred_time=appointment.preferred_time,
                provider_name=appointment.provider_name,
                appointment_type="Consultation",
                reason="Duplicate slot.",
                status=AppointmentRequest.STATUS_CONFIRMED,
            )

    @patch("restapis.views.send_appointment_notification")
    def test_provider_confirm_does_not_fail_when_notification_stub_raises(self, mock_notify):
        provider = User.objects.create_user(
            username="provider3",
            email="provider3@example.com",
            password="StrongPass123!",
        )
        ProviderRequest.objects.create(
            patient=provider,
            first_name="Dr.",
            last_name="Brown",
            email="provider3@example.com",
            specialty="Neurology",
            license_number="LIC-3003",
            message="Neurology provider application",
            status=ProviderRequest.STATUS_APPROVED,
        )
        self.client.force_authenticate(user=provider)
        appointment = AppointmentRequest.objects.create(
            patient=self.user,
            preferred_date="2026-09-08",
            preferred_time="08:15:00",
            provider_name="Dr. Brown",
            appointment_type="Consultation",
            reason="Neurology consult.",
            status=AppointmentRequest.STATUS_PENDING,
        )

        mock_notify.side_effect = RuntimeError("notification failed")

        response = self.client.patch(
            f"/apis/appointments/{appointment.id}/provider-action/",
            {"action": "confirm"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, AppointmentRequest.STATUS_CONFIRMED)

    def test_provider_can_reschedule_pending_appointment(self):
        provider = User.objects.create_user(
            username="provider2",
            email="provider2@example.com",
            password="StrongPass123!",
        )
        ProviderRequest.objects.create(
            patient=provider,
            first_name="Dr.",
            last_name="Jones",
            email="provider2@example.com",
            specialty="Dermatology",
            license_number="LIC-2002",
            message="Dermatology provider application",
            status=ProviderRequest.STATUS_APPROVED,
        )
        self.client.force_authenticate(user=provider)
        appointment = AppointmentRequest.objects.create(
            patient=self.user,
            preferred_date="2026-09-04",
            preferred_time="15:00:00",
            provider_name="Dr. Jones",
            appointment_type="Follow-up",
            reason="Skin issue review.",
            status=AppointmentRequest.STATUS_PENDING,
        )

        response = self.client.patch(
            f"/apis/appointments/{appointment.id}/provider-action/",
            {
                "action": "reschedule",
                "preferred_date": "2026-09-06",
                "preferred_time": "09:45:00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        appointment.refresh_from_db()
        self.assertEqual(appointment.preferred_date.isoformat(), "2026-09-06")
        self.assertEqual(appointment.preferred_time.strftime("%H:%M:%S"), "09:45:00")
        self.assertEqual(appointment.status, AppointmentRequest.STATUS_PENDING)
