"""
Unit & Integration Tests for Universal Login Redesign, Tenant-Specific Unique Login URLs,
Dynamic Role Selection API, and Super Admin Demo Sandbox Portal.
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
from src.database.models import Tenant, User, SystemBranding
from src.server.app import app


class TestTenantLoginRoutingAndDemoPortal(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

    def test_global_login_page_renders_universal_title(self):
        """Test that default /login displays 'Face Recognition - Attendance System'."""
        res = self.client.get("/login")
        self.assertEqual(res.status_code, 200)
        html = res.text
        self.assertIn("Face Recognition - Attendance System", html)
        self.assertTrue("Enterprise Platform Gateway" in html or "Biometric Attendance" in html)
        self.assertIn("loginRole", html)
        self.assertIn("Super Administrator", html)
        self.assertIn("Tenant Administrator", html)

    def test_tenant_specific_login_urls(self):
        """Test tenant-specific unique login URLs (/login/{slug})."""
        # 1. SSEC Corporate Portal
        res_ssec = self.client.get("/login/ssec")
        self.assertEqual(res_ssec.status_code, 200)
        html_ssec = res_ssec.text
        self.assertIn("SSEC", html_ssec)
        self.assertIn("Corporate Enterprise Portal", html_ssec)
        self.assertIn("Employee", html_ssec)

        # 2. pulin1 Corporate Portal
        res_pulin = self.client.get("/login/pulin1")
        self.assertEqual(res_pulin.status_code, 200)
        html_pulin = res_pulin.text
        self.assertIn("pulin1", html_pulin)
        self.assertIn("Corporate Enterprise Portal", html_pulin)

        # 3. GECM Corporate Portal
        res_gecm = self.client.get("/login/gecm")
        self.assertEqual(res_gecm.status_code, 200)
        html_gecm = res_gecm.text
        self.assertIn("GECM", html_gecm)
        self.assertIn("Corporate Enterprise Portal", html_gecm)

        # 4. Default Educational Portal
        res_default = self.client.get("/login/default")
        self.assertEqual(res_default.status_code, 200)
        html_default = res_default.text
        self.assertIn("Academic Campus Portal", html_default)
        self.assertIn("Teacher / Faculty", html_default)
        self.assertIn("Student", html_default)

    def test_invalid_tenant_slug_returns_404(self):
        """Test that a nonexistent tenant slug returns 404 with helpful alert."""
        res = self.client.get("/login/non_existent_tenant_99999")
        self.assertEqual(res.status_code, 404)
        self.assertTrue("not found" in res.text or "deactivated" in res.text)

    def test_tenant_roles_api_endpoint(self):
        """Test /api/v1/auth/tenant-roles/{slug} API returns correct roles and metadata."""
        # SSEC (Corporate)
        res_ssec = self.client.get("/api/v1/auth/tenant-roles/ssec")
        self.assertEqual(res_ssec.status_code, 200)
        data_ssec = res_ssec.json()
        self.assertEqual(data_ssec["status"], "success")
        self.assertTrue(data_ssec["is_corporate"])
        role_keys_ssec = [r["key"] for r in data_ssec["roles"]]
        self.assertIn("TENANT_ADMIN", role_keys_ssec)
        self.assertIn("EMPLOYEE", role_keys_ssec)
        self.assertNotIn("STUDENT", role_keys_ssec)

        # Default (Educational)
        res_def = self.client.get("/api/v1/auth/tenant-roles/default")
        self.assertEqual(res_def.status_code, 200)
        data_def = res_def.json()
        self.assertEqual(data_def["status"], "success")
        self.assertFalse(data_def["is_corporate"])
        role_keys_def = [r["key"] for r in data_def["roles"]]
        self.assertIn("TENANT_ADMIN", role_keys_def)
        self.assertIn("TEACHER", role_keys_def)
        self.assertIn("STUDENT", role_keys_def)

    def test_super_admin_demo_login_portal(self):
        """Test /demo-login and /demo endpoints render the sandbox portal."""
        res = self.client.get("/demo-login")
        self.assertEqual(res.status_code, 200)
        html = res.text
        self.assertIn("Super Admin Sandbox", html)
        self.assertIn("Face Recognition - Attendance System", html)
        self.assertIn("Global Platform Super Administrator", html)
        self.assertIn("SaaS Tenant Organizations", html)
        self.assertIn("ssec", html)
        self.assertIn("pulin1", html)
        self.assertIn("GECM", html)

        # Alias /demo
        res_alias = self.client.get("/demo")
        self.assertEqual(res_alias.status_code, 200)

    def test_multi_role_authentication(self):
        """Test authentication across different system roles and tenants."""
        # 1. Super Admin login
        res_sa = self.client.post("/api/v1/auth/login", json={
            "username": "superadmin",
            "password": "admin123",
            "role": "SUPER_ADMIN",
        })
        self.assertEqual(res_sa.status_code, 200)
        self.assertEqual(res_sa.json()["user"]["role"], "SUPER_ADMIN")

        # 2. SSEC Tenant Admin login
        res_ssec = self.client.post("/api/v1/auth/login", json={
            "username": "ssec",
            "password": "admin123",
            "role": "TENANT_ADMIN",
            "tenant_id": 115,
        })
        self.assertEqual(res_ssec.status_code, 200)
        self.assertEqual(res_ssec.json()["user"]["role"], "TENANT_ADMIN")

        # 3. Teacher login on Tenant 1
        res_tea = self.client.post("/api/v1/auth/login", json={
            "username": "teacher1",
            "password": "teacher123",
            "role": "TEACHER",
            "tenant_id": 1,
        })
        self.assertEqual(res_tea.status_code, 200)
        self.assertEqual(res_tea.json()["user"]["role"], "TEACHER")

        # 4. Student login on Tenant 1
        res_std = self.client.post("/api/v1/auth/login", json={
            "username": "student1",
            "password": "student123",
            "role": "STUDENT",
            "tenant_id": 1,
        })
        self.assertEqual(res_std.status_code, 200)
        self.assertEqual(res_std.json()["user"]["role"], "STUDENT")

    def test_tenant_model_dict_includes_tenant_login_url(self):
        """Verify Tenant.to_dict() contains tenant_login_url."""
        with get_db_context() as db:
            t = db.query(Tenant).filter(Tenant.slug == "ssec").first()
            self.assertIsNotNone(t)
            t_dict = t.to_dict()
            self.assertIn("tenant_login_url", t_dict)
            self.assertIn(t_dict["tenant_login_url"], ["/portal/ssec", "/login/ssec"])


if __name__ == "__main__":
    unittest.main()
