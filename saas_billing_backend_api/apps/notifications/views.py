from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenants.permissions import IsOrganizationMember

from .models import Notification
from .serializers import NotificationSerializer
from apps.core.pagination import bounded_limit


class NotificationListView(APIView):
    """
    List notifications for the authenticated user
    within the selected organization.
    """

    permission_classes = [
        IsAuthenticated,
        IsOrganizationMember,
    ]

    def get(self, request, organization_id):
        notifications = Notification.objects.filter(
            organization_id=organization_id,
            user=request.user,
        ).order_by("-created_at")[: bounded_limit(request)]

        serializer = NotificationSerializer(
            notifications,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


class UnreadNotificationCountView(APIView):
    """
    Return the number of unread notifications
    for the authenticated user.
    """

    permission_classes = [
        IsAuthenticated,
        IsOrganizationMember,
    ]

    def get(self, request, organization_id):
        unread_count = Notification.objects.filter(
            organization_id=organization_id,
            user=request.user,
            is_read=False,
        ).count()

        return Response(
            {
                "unread_count": unread_count,
            },
            status=status.HTTP_200_OK,
        )


class MarkNotificationReadView(APIView):
    """
    Mark one notification as read.
    """

    permission_classes = [
        IsAuthenticated,
        IsOrganizationMember,
    ]

    def post(self, request, organization_id, notification_id):
        notification = get_object_or_404(
            Notification,
            id=notification_id,
            organization_id=organization_id,
            user=request.user,
        )

        if notification.is_read:
            return Response(
                {
                    "detail": "Notification is already marked as read.",
                    "notification_id": str(notification.id),
                    "is_read": True,
                    "read_at": notification.read_at,
                },
                status=status.HTTP_200_OK,
            )

        notification.is_read = True
        notification.read_at = timezone.now()

        notification.save(
            update_fields=[
                "is_read",
                "read_at",
            ]
        )

        return Response(
            {
                "detail": "Notification marked as read.",
                "notification_id": str(notification.id),
                "is_read": True,
                "read_at": notification.read_at,
            },
            status=status.HTTP_200_OK,
        )


class MarkAllNotificationsReadView(APIView):
    """
    Mark all unread notifications for the authenticated
    user in the organization as read.
    """

    permission_classes = [
        IsAuthenticated,
        IsOrganizationMember,
    ]

    def post(self, request, organization_id):
        now = timezone.now()

        updated_count = Notification.objects.filter(
            organization_id=organization_id,
            user=request.user,
            is_read=False,
        ).update(
            is_read=True,
            read_at=now,
        )

        return Response(
            {
                "detail": "All notifications marked as read.",
                "updated_count": updated_count,
            },
            status=status.HTTP_200_OK,
        )