from datetime import datetime

from rest_framework import serializers

from .models import User, indian_phone_validator


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    phone = serializers.CharField(
        required=True,
        validators=[indian_phone_validator],
        help_text="Indian mobile number: 10 digits starting with 6-9, optional +91 or 0 prefix.",
    )

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "phone",
            "role",
            "password",
        ]

    def validate_phone(self, value):
        """Strip +91 or 0 prefix, store only the 10-digit number."""
        # Remove +91 or 0 prefix
        if value.startswith("+91"):
            value = value[3:]
        elif value.startswith("0"):
            value = value[1:]
        # Check uniqueness manually (since model allows NULL)
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError("This phone number is already registered.")
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            phone=validated_data.get("phone"),
            role=validated_data.get("role", "PATIENT"),
            password=validated_data["password"],
        )
        return user


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """
    Updates the fields the current user is allowed to edit.

    `full_name` is a convenience input: it is split into the User model's
    first_name/last_name fields before saving, matching how the profile
    GET endpoint reports a combined "full_name".
    """

    full_name = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Optional combined full name; split into first/last name on save.",
    )
    email = serializers.EmailField()
    phone = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        validators=[indian_phone_validator],
        help_text="Indian mobile number: 10 digits starting with 6-9, optional +91 or 0 prefix.",
    )
    gender = serializers.ChoiceField(
        choices=User.GENDER_CHOICES,
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Gender code (MALE/FEMALE/OTHER/PREFER_NOT_TO_SAY).",
    )
    # Kept as a CharField (DateField has no allow_blank in this DRF version)
    # so an empty string clears the value; validate_date_of_birth parses it.
    date_of_birth = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Date of birth as YYYY-MM-DD.",
    )

    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "full_name",
            "email",
            "phone",
            "gender",
            "date_of_birth",
        ]

    def validate_phone(self, value):
        """Strip +91 or 0 prefix and reject duplicates (matching registration)."""
        value = (value or "").strip()
        if not value:
            return None
        if value.startswith("+91"):
            value = value[3:]
        elif value.startswith("0"):
            value = value[1:]
        qs = User.objects.filter(phone=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "This phone number is already registered."
            )
        return value

    def validate_date_of_birth(self, value):
        """Parse YYYY-MM-DD into a date; blank/null stays None."""
        if value in (None, ""):
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            raise serializers.ValidationError(
                "Date has wrong format. Use one of these formats instead: YYYY-MM-DD."
            )

    def validate(self, attrs):
        full_name = attrs.get("full_name")
        if full_name is not None:
            parts = full_name.strip().split(None, 1)
            attrs["first_name"] = parts[0] if parts else ""
            attrs["last_name"] = parts[1] if len(parts) > 1 else ""
        attrs.pop("full_name", None)

        # Normalize blank strings to None so the optional fields are stored as
        # NULL (and reported as null) rather than an empty string.
        if attrs.get("gender") == "":
            attrs["gender"] = None
        if attrs.get("date_of_birth") == "":
            attrs["date_of_birth"] = None

        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    """Validates a password change for the currently authenticated user."""

    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = self.context["request"].user

        if not user.check_password(attrs.get("current_password", "")):
            raise serializers.ValidationError(
                {"current_password": "Current password is incorrect."}
            )

        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {
                    "confirm_password": (
                        "New password and confirm password do not match."
                    )
                }
            )

        # Apply Django's configured password validators (length, common,
        # numeric, similarity) so the new password meets the same rules as
        # registration.
        from django.contrib.auth.password_validation import validate_password

        try:
            validate_password(attrs["new_password"], user)
        except Exception as exc:
            messages = getattr(exc, "messages", None) or [str(exc)]
            raise serializers.ValidationError(
                {"new_password": " ".join(messages)}
            )

        return attrs