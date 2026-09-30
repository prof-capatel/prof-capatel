"""
Fast Smoke Test Suite for Curiosity HUB SaaS Platform.
Tests top 5 critical paths in < 2 seconds with minimal output.
"""
import os
import sys
from pathlib import Path
import unittest
from fastapi.testclient import TestClient

# Setup path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Ensure DLL path for Anaconda OpenSSL if needed
anaconda_bin = r"C:\ProgramData\Anaconda3\Library\bin"
if os.path.exists(anaconda_bin):
    try:
        os.add_dll_directory(anaconda_bin)
    except Exception:
        pass
    if anaconda_bin not in os.environ.get("PATH", ""):
        os.environ["PATH"] = anaconda_bin + os.pathsep + os.environ.get("PATH", "")

from src.database.session import init_db, get_db_context
from src.database.models import Tenant
from src.server.app import app


class FastSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

    def test_01_landing_page_renders_ok(self):
        """Verify landing page loads 200 OK with modular components."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Curiosity HUB", res.text)
        self.assertIn("freeDemoModal", res.text)
        self.assertIn("onboardingGuideModal", res.text)

    def test_02_login_page_renders_ok(self):
        """Verify SaaS login page loads 200 OK."""
        res = self.client.get("/login")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Face Recognition Employee Management System", res.text)

    def test_03_dashboard_auth_protection(self):
        """Verify protected /dashboard redirects unauthenticated users."""
        res = self.client.get("/dashboard", follow_redirects=False)
        self.assertIn(res.status_code, [302, 303, 307])
        loc = res.headers.get("location", "")
        self.assertTrue("/login" in loc or "/saas" in loc)

    def test_04_core_tenants_integrity(self):
        """Verify all 6 core SaaS tenants exist and are active in database."""
        core_slugs = ["default", "pulin1", "ssec", "gecm", "raymond-store-1", "the-retail-store"]
        with get_db_context() as db:
            active_tenants = db.query(Tenant).filter(Tenant.slug.in_(core_slugs)).all()
            found_slugs = [t.slug for t in active_tenants if t.is_active]
            for slug in core_slugs:
                self.assertIn(slug, found_slugs, f"Core tenant '{slug}' missing or inactive!")

    def test_05_tenant_portal_route(self):
        """Verify tenant-specific portal route (/login/ssec)."""
        res = self.client.get("/login/ssec")
        self.assertEqual(res.status_code, 200)
        self.assertIn("SSEC", res.text)


if __name__ == "__main__":
    unittest.main()
