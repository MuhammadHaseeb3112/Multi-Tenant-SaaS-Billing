from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.pagination import bounded_limit
from apps.tenants.permissions import IsOrganizationMember

from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogListView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsOrganizationMember,
    ]

    def get(self, request, organization_id):
        logs = (
            AuditLog.objects
            .filter(
                organization_id=organization_id,
            )
            .select_related("user", "organization")
            .order_by("-created_at")[: bounded_limit(request)]
        )

        serializer = AuditLogSerializer(
            logs,
            many=True,
        )

        return Response(serializer.data)