from .models import AuditLog


def create_audit_log(
    *,
    organization,
    user=None,
    action,
    resource_type="",
    resource_id="",
    description="",
    metadata=None,
):
    return AuditLog.objects.create(
        organization=organization,
        user=user,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id else "",
        description=description,
        metadata=metadata or {},
    )