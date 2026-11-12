from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .security import (
    AuthRateThrottle,
    LoginLockout,
    RegisterRateThrottle,
    clear_refresh_cookie,
    get_refresh_cookie,
    origin_is_trusted,
    set_refresh_cookie,
)
from .serializers import (
    LoginSerializer,
    MeSerializer,
    RegisterSerializer,
)


def user_payload(user):
    return {
        "id": str(user.id),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
    }


def auth_response(user, message, status_code):
    """
    Body: user + short-lived access token (kept in memory by the SPA).
    Cookie: long-lived refresh token, httpOnly (never readable by JS).
    """

    refresh = RefreshToken.for_user(user)

    response = Response(
        {
            "message": message,
            "user": user_payload(user),
            "tokens": {
                "access": str(refresh.access_token),
            },
        },
        status=status_code,
    )

    return set_refresh_cookie(response, refresh)


class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [RegisterRateThrottle]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.save()

        return auth_response(
            user,
            "Registration successful.",
            status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        lockout = LoginLockout(request, request.data.get("email"))

        if lockout.is_locked():
            return Response(
                {
                    "detail": (
                        "Too many failed login attempts. "
                        "Please try again later."
                    ),
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(lockout.window)},
            )

        serializer = LoginSerializer(
            data=request.data,
            context={"request": request},
        )

        try:
            serializer.is_valid(raise_exception=True)
        except AuthenticationFailed:
            lockout.register_failure()
            raise

        lockout.reset()

        return auth_response(
            serializer.validated_data["user"],
            "Login successful.",
            status.HTTP_200_OK,
        )


class CookieTokenRefreshView(APIView):
    """
    Issues a new access token from the httpOnly refresh cookie.
    With ROTATE_REFRESH_TOKENS the cookie is replaced and the old refresh
    token is blacklisted.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        if not origin_is_trusted(request):
            return Response(
                {"detail": "Untrusted origin."},
                status=status.HTTP_403_FORBIDDEN,
            )

        raw_refresh = get_refresh_cookie(request)

        if not raw_refresh:
            return Response(
                {"detail": "No refresh token."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = TokenRefreshSerializer(
            data={"refresh": raw_refresh}
        )

        try:
            serializer.is_valid(raise_exception=True)
        except (InvalidToken, TokenError):
            response = Response(
                {"detail": "Session expired. Please log in again."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            return clear_refresh_cookie(response)

        data = serializer.validated_data
        response = Response(
            {"access": data["access"]},
            status=status.HTTP_200_OK,
        )

        if "refresh" in data:
            set_refresh_cookie(response, data["refresh"])

        return response


class MeView(APIView):
    def get(self, request):
        serializer = MeSerializer(request.user)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    def patch(self, request):
        """Update the signed-in user's own name."""

        from .account import ProfileUpdateSerializer, audit_for_user

        user = request.user
        before = (user.first_name, user.last_name)

        serializer = ProfileUpdateSerializer(
            user,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        if (user.first_name, user.last_name) != before:
            audit_for_user(
                user,
                "PROFILE_UPDATED",
                f"{user.email} updated their profile name.",
            )

        return Response(
            MeSerializer(user).data,
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    """
    Blacklists the refresh token (from the cookie, or from the body for
    non-browser clients) and deletes the cookie.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not origin_is_trusted(request):
            return Response(
                {"detail": "Untrusted origin."},
                status=status.HTTP_403_FORBIDDEN,
            )

        raw_refresh = (
            get_refresh_cookie(request)
            or request.data.get("refresh")
        )

        if raw_refresh:
            try:
                RefreshToken(raw_refresh).blacklist()
            except TokenError:
                # Already expired / blacklisted: nothing left to revoke.
                pass

        response = Response(
            {"message": "Logout successful."},
            status=status.HTTP_200_OK,
        )

        return clear_refresh_cookie(response)
