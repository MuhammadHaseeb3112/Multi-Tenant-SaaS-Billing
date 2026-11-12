from django.utils.text import slugify

from .models import Organization


def unique_organization_slug(name):
    """A URL-safe slug for ``name`` that no organization uses yet."""

    base_slug = slugify(name) or "organization"
    slug = base_slug
    counter = 1

    while Organization.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug
