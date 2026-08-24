from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import AppointmentRequest, ProviderProfile

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

    def test_provider_can_confirm_pending_appointment(self):
        provider = User.objects.create_user(
            username="provider1",
            email="provider1@example.com",
            password="StrongPass123!",
        )
        ProviderProfile.objects.create(
            user=provider,
            first_name="Dr.",
            last_name="Smith",
            email="provider1@example.com",
            specialty="Cardiology",
            license_number="LIC-1001",
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

    def test_provider_can_reschedule_pending_appointment(self):
        provider = User.objects.create_user(
            username="provider2",
            email="provider2@example.com",
            password="StrongPass123!",
        )
        ProviderProfile.objects.create(
            user=provider,
            first_name="Dr.",
            last_name="Jones",
            email="provider2@example.com",
            specialty="Dermatology",
            license_number="LIC-2002",
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
