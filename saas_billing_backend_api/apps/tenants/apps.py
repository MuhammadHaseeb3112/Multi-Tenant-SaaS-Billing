from django.apps import AppConfig

class TenantsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.tenants'  # Points Django to the correct physical directory
    label = 'tenants'      # Forces the short unique namespace inside the registry
