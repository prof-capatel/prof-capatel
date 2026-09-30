"""
Tests for Super Admin SEO Analytics & Management Hub.
Verifies GET/POST /api/v1/super-admin/seo, /sitemap-regenerate,
dynamic /robots.txt, dynamic /sitemap.xml, and UI rendering.
"""
import os
import sys
from pathlib import Path
import unittest
from fastapi.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Ensure Anaconda DLL path if needed
anaconda_bin = r"C:\ProgramData\Anaconda3\Library\bin"
if os.path.exists(anaconda_bin):
    try:
        os.add_dll_directory(anaconda_bin)
    except Exception:
        pass
    if anaconda_bin not in os.environ.get("PATH", ""):
        os.environ["PATH"] = anaconda_bin + os.pathsep + os.environ.get("PATH", "")

from src.database.session import init_db
from src.server.app import app
from src.server.services import seo_service


class TestSuperAdminSeo(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.client = TestClient(app, cookies={})

    def _login_super_admin(self):
        res = self.client.post("/api/v1/auth/super-admin/login", json={
            "username": "superadmin",
            "password": "admin123",
        })
        self.assertEqual(res.status_code, 200)
        return self.client

    def test_01_unauthenticated_seo_endpoint_rejected(self):
        """Verify unauthenticated requests to /api/v1/super-admin/seo are rejected."""
        client_no_auth = TestClient(app, cookies={})
        res = client_no_auth.post("/api/v1/super-admin/seo", json={
            "site_title": "Test Title",
            "meta_description": "Test Desc",
            "canonical_url": "https://curiosityhub.co.in/",
        })
        self.assertIn(res.status_code, [401, 403])

    def test_02_get_seo_overview(self):
        """Verify GET /api/v1/super-admin/seo returns comprehensive audit metrics."""
        self._login_super_admin()
        res = self.client.get("/api/v1/super-admin/seo")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("score", data)
        self.assertGreaterEqual(data["score"], 50)
        self.assertIn("settings", data)
        self.assertIn("audit_items", data)
        self.assertIn("serp_preview", data)
        self.assertIn("social_preview", data)
        self.assertEqual(data["sitemap_url"], "https://curiosityhub.co.in/sitemap.xml")

    def test_03_update_seo_configuration(self):
        """Verify POST /api/v1/super-admin/seo updates and persists settings."""
        self._login_super_admin()
        payload = {
            "site_title": "Curiosity HUB — Face Recognition Attendance & Payroll SaaS",
            "meta_description": "Enterprise AI facial recognition attendance & automated payroll SaaS for modern companies. Centralize multi-location offices with mobile GPS geofencing and bank-grade security.",
            "meta_keywords": "facial recognition attendance, multi location attendance, automated payroll saas, ahmedabad hr software",
            "canonical_url": "https://curiosityhub.co.in/",
            "og_title": "Curiosity HUB — Enterprise AI Attendance & Payroll SaaS",
            "og_description": "Enterprise AI facial recognition attendance & automated payroll SaaS for companies. Multi-location offices and bank-grade security.",
            "og_image": "https://curiosityhub.co.in/screenshots/walkthrough/02_dashboard_live.png",
            "robots_directives": "User-agent: *\nAllow: /$\nAllow: /screenshots/\nAllow: /static/\nDisallow: /saas\nDisallow: /super-admin\nDisallow: /dashboard\nDisallow: /api/\n\nSitemap: https://curiosityhub.co.in/sitemap.xml\n",
        }
        res = self.client.post("/api/v1/super-admin/seo", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("seo", data)
        self.assertEqual(data["seo"]["settings"]["site_title"], payload["site_title"])

    def test_04_regenerate_sitemap(self):
        """Verify POST /api/v1/super-admin/seo/sitemap-regenerate generates XML sitemap."""
        self._login_super_admin()
        res = self.client.post("/api/v1/super-admin/seo/sitemap-regenerate")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("sitemap_url", data)

    def test_05_dynamic_robots_and_sitemap_endpoints(self):
        """Verify /robots.txt and /sitemap.xml serve live content from seo_service."""
        # robots.txt
        res_robots = self.client.get("/robots.txt")
        self.assertEqual(res_robots.status_code, 200)
        self.assertIn("User-agent: *", res_robots.text)
        self.assertIn("Sitemap: https://curiosityhub.co.in/sitemap.xml", res_robots.text)

        # sitemap.xml
        res_sitemap = self.client.get("/sitemap.xml")
        self.assertEqual(res_sitemap.status_code, 200)
        self.assertIn('<?xml version="1.0" encoding="UTF-8"?>', res_sitemap.text)
        self.assertIn("<loc>https://curiosityhub.co.in/</loc>", res_sitemap.text)

    def test_06_super_admin_ui_contains_seo_hub(self):
        """Verify /super-admin UI renders the SEO Hub card, SERP preview, and form."""
        self._login_super_admin()
        res = self.client.get("/super-admin")
        self.assertEqual(res.status_code, 200)
        html = res.text
        self.assertIn("seoManagementCard", html)
        self.assertIn("SEO Reporting & Search Engine Optimization Hub", html)
        self.assertIn("Live Google SERP Simulator", html)
        self.assertIn("OpenGraph Social Card Preview", html)
        self.assertIn("seoConfigForm", html)
        self.assertIn("seoChecklistTable", html)


if __name__ == "__main__":
    unittest.main()
