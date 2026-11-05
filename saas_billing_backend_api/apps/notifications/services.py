from django.contrib.auth import get_user_model

from .models import Notification


User = get_user_model()


def create_notification(
    *,
    organization,
    user,
    notification_type,
    title,
    message,
):
    """
    Create an in-app notification for a user
    within an organization.
    """

    return Notification.objects.create(
        organization=organization,
        user=user,
        notification_type=notification_type,
        title=title,
        message=message,
    )


def create_notification_for_organization_members(
    *,
    organization,
    notification_type,
    title,
    message,
):
    """
    Create the same notification for all active
    members of an organization.
    """

    users = User.objects.filter(
        memberships__organization=organization,
        memberships__is_active=True,
        is_active=True,
    ).distinct()

    notifications = []

    for user in users:
        notifications.append(
            Notification(
                organization=organization,
                user=user,
                notification_type=notification_type,
                title=title,
                message=message,
            )
        )

    return Notification.objects.bulk_create(notifications)