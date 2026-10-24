from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    RegisterSerializer,
    ProfileUpdateSerializer,
    ChangePasswordSerializer,
)
from rest_framework.permissions import IsAuthenticated


class RegisterView(APIView):
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "User registered successfully"},
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProfileView(APIView):
    """
    GET    -> the currently logged-in user's profile.
    PATCH  -> update editable profile fields (first/last name, email, phone,
              gender, date of birth).

    `is_verified` is read-only here (managed via staff/admin); everything
    else reflects the logged-in user's actual stored values.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(self._profile_data(request.user))

    def patch(self, request):
        serializer = ProfileUpdateSerializer(
            request.user, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(self._profile_data(request.user))
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request):
        return self.patch(request)

    @staticmethod
    def _profile_data(user):
        return {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            # Raw combined name (may be empty). The frontend falls back to
            # the username for the header and shows "Not Available" for the
            # field when no name has been set.
            "full_name": (f"{user.first_name} {user.last_name}").strip(),
            "email": user.email,
            "phone": user.phone,
            "role": user.get_role_display(),
            "role_code": user.role,
            "gender": user.get_gender_display() if user.gender else None,
            "gender_code": user.gender or None,
            "date_of_birth": (
                user.date_of_birth.isoformat() if user.date_of_birth else None
            ),
            "date_joined": user.date_joined,
            "last_login": user.last_login,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
        }


class ChangePasswordView(APIView):
    """Changes the authenticated user's password via the existing User model."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            request.user.set_password(serializer.validated_data["new_password"])
            request.user.save(update_fields=["password"])
            return Response({"message": "Password changed successfully."})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
