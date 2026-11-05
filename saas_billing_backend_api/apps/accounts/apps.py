from django.apps import AppConfig

class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'  # This tells Django where the folder is
    label = 'accounts'      # This enforces the clean app_label used by Django
