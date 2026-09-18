"""
Unit & Integration Tests for Decoupled Authentication Architecture & Dedicated Login Portals.
Tests isolated Super Admin portal (/super-admin/login), unique tenant portals (/portal/{slug}),
and strict session boundary isolation.
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


class TestDecoupledAuthPortals(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.client = TestClient(app, cookies={})

    def test_super_admin_login_page_renders_isolated_ui(self):
        """Verify dedicated /super-admin/login page renders clean control plane UI without tenant dropdowns."""
        res = self.client.get("/super-admin/login")
        self.assertEqual(res.status_code, 200)
        html = res.text
        self.assertIn("Super Admin Control Plane", html)
        self.assertIn("saUsername", html)
        self.assertIn("saPassword", html)
        self.assertNotIn("Select Organization", html)
        self.assertNotIn("loginRole", html)

    def test_super_admin_unauthenticated_redirect(self):
        """Verify unauthenticated /super-admin access redirects to /super-admin/login."""
        client_no_auth = TestClient(app, cookies={})
        res = client_no_auth.get("/super-admin", follow_redirects=False)
        self.assertEqual(res.status_code, 303)
        self.assertIn("/super-admin/login", res.headers.get("location", ""))

    def test_super_admin_login_api_endpoint(self):
        """Verify POST /api/v1/auth/super-admin/login authenticates superadmin and rejects tenant accounts."""
        # 1. Valid Super Admin login
        res_valid = self.client.post("/api/v1/auth/super-admin/login", json={
            "username": "superadmin",
            "password": "admin123",
        })
        self.assertEqual(res_valid.status_code, 200)
        data = res_valid.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["user"]["role"], "SUPER_ADMIN")
        self.assertIn("access_token", data)
        self.assertEqual(data["redirect_url"], "/super-admin")

        # 2. Rejection of tenant admin credentials on Super Admin portal
        res_invalid = self.client.post("/api/v1/auth/super-admin/login", json={
            "username": "ssec",
            "password": "admin123",
        })
        self.assertEqual(res_invalid.status_code, 401)
        self.assertIn("Invalid Super Administrator credentials", res_invalid.json().get("detail", ""))

    def test_tenant_portal_login_page_renders_scoped_ui(self):
        """Verify /portal/{slug} and /login/{slug} render dedicated tenant UI with strictly scoped roles."""
        # 1. SSEC Corporate Face Biometric Portal & Login Page
        res_ssec_portal = self.client.get("/portal/ssec")
        self.assertEqual(res_ssec_portal.status_code, 200)
        html_ssec_portal = res_ssec_portal.text
        self.assertIn("SSEC", html_ssec_portal)
        self.assertIn("Corporate Enterprise Portal", html_ssec_portal)
        self.assertIn("camera-viewport", html_ssec_portal)
        self.assertNotIn("Global Platform Portal", html_ssec_portal)
        self.assertNotIn("Super Admin Portal", html_ssec_portal)

        # SSEC Credential login
        res_ssec_login = self.client.get("/login/ssec")
        self.assertEqual(res_ssec_login.status_code, 200)
        html_ssec_login = res_ssec_login.text
        self.assertIn('value="EMPLOYEE"', html_ssec_login)
        self.assertNotIn('value="STUDENT"', html_ssec_login)
        self.assertNotIn('value="TEACHER"', html_ssec_login)

        # 2. pulin1 Corporate Portal & Login
        res_pulin_portal = self.client.get("/portal/pulin1")
        self.assertEqual(res_pulin_portal.status_code, 200)
        html_pulin_portal = res_pulin_portal.text
        self.assertIn("pulin1", html_pulin_portal)
        self.assertIn("Corporate Enterprise Portal", html_pulin_portal)

        res_pulin_login = self.client.get("/login/pulin1")
        self.assertEqual(res_pulin_login.status_code, 200)
        self.assertIn('value="EMPLOYEE"', res_pulin_login.text)
        self.assertNotIn('value="STUDENT"', res_pulin_login.text)

        # 3. GECM Corporate Portal
        res_gecm = self.client.get("/portal/gecm")
        self.assertEqual(res_gecm.status_code, 200)
        html_gecm = res_gecm.text
        self.assertIn("GECM", html_gecm)
        self.assertNotIn("Global Platform Portal", html_gecm)
        self.assertNotIn("Global Platform Portal", html_gecm)
        self.assertNotIn("Super Admin Portal", html_gecm)

        # 4. Default Educational Portal
        res_default = self.client.get("/portal/default")
        self.assertEqual(res_default.status_code, 200)
        html_default = res_default.text
        self.assertIn("Academic Campus Portal", html_default)
        self.assertIn('value="TEACHER"', html_default)
        self.assertIn('value="STUDENT"', html_default)
        self.assertNotIn('value="EMPLOYEE"', html_default)
        self.assertNotIn("Global Platform Portal", html_default)
        self.assertNotIn("Super Admin Portal", html_default)

    def test_tokenized_tenant_portal_url(self):
        """Verify tokenized tenant portal link /portal/{uuid}/{token} resolves correctly."""
        with get_db_context() as db:
            tenant = db.query(Tenant).filter(Tenant.slug == "ssec").first()
            self.assertIsNotNone(tenant)
            t_uuid = tenant.uuid
            t_token = tenant.admin_token

        res = self.client.get(f"/portal/{t_uuid}/{t_token}")
        self.assertEqual(res.status_code, 200)
        self.assertIn("SSEC", res.text)
        self.assertIn("Corporate Enterprise Portal", res.text)

    def test_tenant_login_api_endpoint(self):
        """Verify POST /api/v1/auth/tenant/login authenticates within tenant and isolates session."""
        # 1. SSEC Tenant Admin login
        res_ssec = self.client.post("/api/v1/auth/tenant/login", json={
            "username": "ssec",
            "password": "admin123",
            "tenant_identifier": "ssec",
            "role": "TENANT_ADMIN",
        })
        self.assertEqual(res_ssec.status_code, 200)
        data_ssec = res_ssec.json()
        self.assertEqual(data_ssec["status"], "success")
        self.assertEqual(data_ssec["user"]["role"], "TENANT_ADMIN")
        self.assertEqual(data_ssec["user"]["tenant_id"], 115)
        self.assertEqual(data_ssec["redirect_url"], "/")

        # 2. Teacher login on default tenant
        res_tea = self.client.post("/api/v1/auth/tenant/login", json={
            "username": "teacher1",
            "password": "teacher123",
            "tenant_identifier": "default",
            "role": "TEACHER",
        })
        self.assertEqual(res_tea.status_code, 200)
        data_tea = res_tea.json()
        self.assertEqual(data_tea["user"]["role"], "TEACHER")
        self.assertEqual(data_tea["redirect_url"], "/teacher-portal")

        # 3. Rejection of cross-tenant credential attack (e.g. ssec user trying to authenticate against default tenant)
        res_cross = self.client.post("/api/v1/auth/tenant/login", json={
            "username": "ssec",
            "password": "admin123",
            "tenant_identifier": "default",
        })
        self.assertEqual(res_cross.status_code, 401)

    def test_tenant_model_dict_includes_portal_urls(self):
        """Verify Tenant.to_dict() provides portal_url and tokenized_portal_url."""
        with get_db_context() as db:
            t = db.query(Tenant).filter(Tenant.slug == "ssec").first()
            self.assertIsNotNone(t)
            t_dict = t.to_dict()
            self.assertIn("portal_url", t_dict)
            self.assertEqual(t_dict["portal_url"], "/portal/ssec")
            self.assertIn("tokenized_portal_url", t_dict)


if __name__ == "__main__":
    unittest.main()
