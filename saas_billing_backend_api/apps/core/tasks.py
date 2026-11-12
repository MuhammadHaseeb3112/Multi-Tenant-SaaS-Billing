from celery import shared_task
from django.core.management import call_command


@shared_task
def reset_demo_data():
    """Public demo only: restore the demo data every night."""

    call_command("seed_demo", "--reset")
