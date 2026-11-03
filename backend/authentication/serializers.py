"""Serializers for registration, login (JWT), logout and the current user."""

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User


class UserSerializer(serializers.ModelSerializer):
    """Public profile of a user. Email and role can't be changed through the API."""

    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "phone_number",
            "role",
            "receive_email_alerts",
            "receive_sms_alerts",
            "date_joined",
        )
        read_only_fields = ("id", "email", "role", "date_joined")


class RegisterSerializer(serializers.ModelSerializer):
    """Self-registration. Always creates a `customer`; the role can't be chosen."""

    password = serializers.CharField(
        write_only=True,
        validators=[validate_password],  # Django's strength rules (length, common passwords...)
        style={"input_type": "password"},
    )
    password_confirm = serializers.CharField(write_only=True, style={"input_type": "password"})

    class Meta:
        model = User
        fields = (
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "password",
            "password_confirm",
        )
        extra_kwargs = {
            "first_name": {"required": True, "allow_blank": False},
            "last_name": {"required": True, "allow_blank": False},
        }

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(role=User.Role.CUSTOMER, **validated_data)


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Login serializer. Because User.USERNAME_FIELD is "email", clients send
    {"email": ..., "password": ...}. We also:
      - put the user's email and role inside the token (handy for the React app), and
      - return the user's profile next to the tokens so no second request is needed.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["email"] = user.email
        token["role"] = user.role
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data


class LogoutSerializer(serializers.Serializer):
    """Validates a refresh token and blacklists it so it can never be used again."""

    refresh = serializers.CharField()

    def validate(self, attrs):
        try:
            self._token = RefreshToken(attrs["refresh"])
        except TokenError:
            raise serializers.ValidationError({"refresh": "Token is invalid or expired."})
        return attrs

    def save(self, **kwargs):
        self._token.blacklist()
