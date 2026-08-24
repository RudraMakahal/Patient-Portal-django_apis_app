from django.conf import settings
from django.db import models
from django.db.models import Q


class ProviderProfile(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="provider_profile",
        null=True,
        blank=True,
    )
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    email = models.EmailField()
    specialty = models.CharField(max_length=120)
    license_number = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["first_name", "last_name"]

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self):
        return f"{self.full_name} - {self.specialty}"


class ProviderRequest(models.Model):
    STATUS_PENDING = "Pending"
    STATUS_REVIEWED = "Reviewed"
    STATUS_APPROVED = "Approved"
    STATUS_REJECTED = "Rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_REVIEWED, "Reviewed"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="provider_requests",
        null=True,
        blank=True,
    )
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    email = models.EmailField()
    specialty = models.CharField(max_length=120)
    license_number = models.CharField(max_length=120)
    message = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.specialty}"


class AppointmentRequest(models.Model):
    APPOINTMENT_TYPES = [
        ("Follow-up", "Follow-up"),
        ("Primary Care", "Primary Care"),
        ("Telehealth", "Telehealth"),
        ("Consultation", "Consultation"),
    ]

    STATUS_PENDING = "Pending"
    STATUS_CONFIRMED = "Confirmed"
    STATUS_CANCELLED = "Cancelled"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="appointment_requests",
    )
    preferred_date = models.DateField()
    preferred_time = models.TimeField()
    provider_name = models.CharField(max_length=120, blank=True, default="")
    appointment_type = models.CharField(
        max_length=30,
        choices=APPOINTMENT_TYPES,
        default="Follow-up",
    )
    reason = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["preferred_date", "preferred_time"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider_name", "preferred_date", "preferred_time"],
                condition=Q(status="Confirmed"),
                name="unique_confirmed_provider_slot",
            )
        ]

    def __str__(self):
        return f"{self.patient.username} - {self.appointment_type} ({self.status})"
