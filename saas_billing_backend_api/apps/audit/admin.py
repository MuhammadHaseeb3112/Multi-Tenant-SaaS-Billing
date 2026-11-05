from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = [
        "created_at",
        "organization",
        "user",
        "action",
        "resource_type",
        "resource_id",
    ]

    list_filter = [
        "action",
        "resource_type",
        "created_at",
    ]

    search_fields = [
        "organization__name",
        "user__email",
        "action",
        "resource_type",
        "resource_id",
        "description",
    ]

    readonly_fields = [
        "id",
        "organization",
        "user",
        "action",
        "resource_type",
        "resource_id",
        "description",
        "metadata",
        "created_at",
    ]

    ordering = ["-created_at"]