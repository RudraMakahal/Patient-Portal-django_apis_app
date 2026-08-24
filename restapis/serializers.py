from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import AppointmentRequest, ProviderProfile, ProviderRequest

User = get_user_model()


class ProviderProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = ProviderProfile
        fields = ["id", "full_name", "email", "specialty", "license_number"]

    def get_full_name(self, obj):
        return obj.full_name


class ProviderRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProviderRequest
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "specialty",
            "license_number",
            "message",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "status", "created_at", "updated_at"]

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["patient"] = request.user
        return super().create(validated_data)


class AppointmentRequestSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField(required=True, allow_blank=False)

    class Meta:
        model = AppointmentRequest
        fields = [
            "id",
            "preferred_date",
            "preferred_time",
            "provider_name",
            "appointment_type",
            "reason",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "status", "created_at", "updated_at"]

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["patient"] = request.user
        return super().create(validated_data)


class ProfileSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]

    def validate_email(self, value):
        if User.objects.filter(email=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        username = attrs["username"]
        password = attrs["password"]

        user = authenticate(
            request=self.context.get("request"),
            username=username,
            password=password,
        )

        if not user:
            raise serializers.ValidationError("Invalid username or password.")

        if not user.is_active:
            raise serializers.ValidationError("User account is inactive.")

        attrs["user"] = user
        return attrs


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["username", "email", "password", "confirm_password"]

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value

    def validate(self, attrs):
        password = attrs.get("password")
        confirm_password = attrs.get("confirm_password")

        validate_password(password)

        if password != confirm_password:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

        return attrs

    def create(self, validated_data):
        validated_data.pop("confirm_password")
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data.get("email", ""),
            password=validated_data["password"],
        )
        return user