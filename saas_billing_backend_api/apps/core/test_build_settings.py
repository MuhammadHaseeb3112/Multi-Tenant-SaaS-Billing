"""
The Docker image collects static files at build time with
scripts/collectstatic_settings.py (the real settings are not available
then). These tests fail if that file drifts from the real settings,
which would leave static files missing in the image.
"""

import importlib.util
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

ROOT = Path(settings.BASE_DIR)


def build_settings():
    spec = importlib.util.spec_from_file_location(
        "collectstatic_settings",
        ROOT / "scripts" / "collectstatic_settings.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BuildTimeStaticSettingsTests(SimpleTestCase):

    def test_every_third_party_app_is_collected_at_build_time(self):
        third_party = {
            app for app in settings.INSTALLED_APPS
            if not app.startswith("apps.")
        }

        self.assertLessEqual(
            third_party,
            set(build_settings().INSTALLED_APPS),
            "Add the new app to scripts/collectstatic_settings.py",
        )

    def test_project_has_no_static_files_of_its_own(self):
        # Build-time collection only sees installed packages. If the
        # project gains its own static files, collect them in the
        # Dockerfile after the code is copied.
        self.assertFalse(getattr(settings, "STATICFILES_DIRS", []))
        self.assertEqual(list((ROOT / "apps").glob("*/static")), [])

    def test_same_storage_and_location_as_production(self):
        build = build_settings()
        production = (
            ROOT / "config" / "settings" / "production.py"
        ).read_text()

        self.assertIn(
            build.STORAGES["staticfiles"]["BACKEND"], production,
        )
        self.assertEqual(build.STATIC_URL, settings.STATIC_URL)
        self.assertEqual(Path(build.STATIC_ROOT).name, "staticfiles")

    def test_start_script_does_not_collect_static_on_every_boot(self):
        script = (ROOT / "scripts" / "start-web.sh").read_text()

        self.assertIn("staticfiles/staticfiles.json", script)
        self.assertNotIn("\r", script)  # must stay LF for /bin/sh
