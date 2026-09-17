"""
Unit & Integration Tests for Corporate URL Route Cleanup and Non-Camera Tenant Logout Flow.
Tests:
1. /employees route renders Employee Directory for corporate tenants.
2. /departments and /teams routes render Departments & Teams management.
3. /students and /academic-management preserve backward compatibility.
4. POST /api/v1/auth/logout redirects to /login/{tenant_slug}.
5. GET /login/{tenant_slug} renders clean credential login without camera initialization.
6. GET /portal/{tenant_slug} renders biometric face camera portal.
7. Corporate tenant sidebar navigation contains /employees and /departments.
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
from src.database.models import Tenant, User
from src.server.app import app
from src.server.rbac_middleware import create_access_token


class TestCorporateRoutesAndNonCameraLogout(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.client = TestClient(app)

    def test_01_employees_route_accessibility_and_rendering(self):
        """Test GET /employees renders the directory for a corporate tenant."""
        with get_db_context() as db:
            ssec = db.query(Tenant).filter(Tenant.slug == "ssec").first()
            self.assertIsNotNone(ssec)
            ssec_id = str(ssec.id)
            token = create_access_token(user_id=96, role="TENANT_ADMIN", tenant_id=ssec.id, username="ssec")

        self.client.cookies.set("access_token", token)
        self.client.cookies.set("active_role", "TENANT_ADMIN")
        self.client.cookies.set("active_tenant_id", ssec_id)

        res = self.client.get("/employees")
        self.assertEqual(res.status_code, 200)
        html = res.text
        self.assertIn("Employee Directory", html)
        self.assertIn("Search Name or Employee ID", html)

    def test_02_departments_and_teams_routes_accessibility(self):
        """Test GET /departments and GET /teams redirect corporate tenant to /settings#departmentsSection."""
        with get_db_context() as db:
            ssec = db.query(Tenant).filter(Tenant.slug == "ssec").first()
            ssec_id = str(ssec.id)
            token = create_access_token(user_id=96, role="TENANT_ADMIN", tenant_id=ssec.id, username="ssec")

        self.client.cookies.set("access_token", token)
        self.client.cookies.set("active_role", "TENANT_ADMIN")
        self.client.cookies.set("active_tenant_id", ssec_id)

        # 1. /departments
        res_dept = self.client.get("/departments", follow_redirects=False)
        self.assertEqual(res_dept.status_code, 303)
        self.assertEqual(res_dept.headers.get("location"), "/settings#departmentsSection")

        # 2. /teams (alias)
        res_teams = self.client.get("/teams", follow_redirects=False)
        self.assertEqual(res_teams.status_code, 303)
        self.assertEqual(res_teams.headers.get("location"), "/settings#departmentsSection")

    def test_03_legacy_routes_backward_compatibility(self):
        """Test /students and /academic-management remain fully functional."""
        with get_db_context() as db:
            ssec = db.query(Tenant).filter(Tenant.slug == "ssec").first()
            ssec_id = str(ssec.id)
            token = create_access_token(user_id=96, role="TENANT_ADMIN", tenant_id=ssec.id, username="ssec")

        self.client.cookies.set("access_token", token)
        self.client.cookies.set("active_role", "TENANT_ADMIN")
        self.client.cookies.set("active_tenant_id", ssec_id)

        # Legacy /students
        res_st = self.client.get("/students")
        self.assertEqual(res_st.status_code, 200)

        # Legacy /academic-management redirects corporate to settings
        res_ac = self.client.get("/academic-management", follow_redirects=False)
        self.assertEqual(res_ac.status_code, 303)
        self.assertEqual(res_ac.headers.get("location"), "/settings#departmentsSection")

    def test_04_tenant_logout_redirection_target(self):
        """Test POST /api/v1/auth/logout directs corporate tenant to /login/{tenant_slug}."""
        with get_db_context() as db:
            ssec = db.query(Tenant).filter(Tenant.slug == "ssec").first()
            ssec_id = str(ssec.id)
            token = create_access_token(user_id=96, role="TENANT_ADMIN", tenant_id=ssec.id, username="ssec")

        self.client.cookies.set("access_token", token)
        self.client.cookies.set("active_role", "TENANT_ADMIN")
        self.client.cookies.set("active_tenant_id", ssec_id)

        res = self.client.post("/api/v1/auth/logout")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["redirect_url"], "/login/ssec")

    def test_05_non_camera_tenant_login_page(self):
        """Test GET /login/{tenant_slug} renders text/password form without camera feed."""
        res = self.client.get("/login/ssec")
        self.assertEqual(res.status_code, 200)
        html = res.text

        # Must have clean credential inputs
        self.assertIn("loginUsername", html)
        self.assertIn("loginPassword", html)
        self.assertIn("loginRole", html)
        self.assertIn("SSEC", html)

        # Must NOT contain biometric video stream element or camera-viewport
        self.assertNotIn('<video id="faceVideo"', html)
        self.assertNotIn('class="camera-viewport"', html)
        self.assertNotIn("startCamera()", html)

        # Provides optional switcher to biometric face portal
        self.assertIn("/portal/ssec", html)

    def test_06_biometric_portal_retains_camera(self):
        """Test GET /portal/{tenant_slug} retains the biometric camera scanner view."""
        res = self.client.get("/portal/ssec")
        self.assertEqual(res.status_code, 200)
        html = res.text
        self.assertIn("camera-viewport", html)
        self.assertIn("faceVideo", html)
        self.assertIn("playShutterAndChime", html)

    def test_07_sidebar_navigation_links(self):
        """Test corporate tenant sidebar displays streamlined navigation links and nests departments into settings."""
        with get_db_context() as db:
            ssec = db.query(Tenant).filter(Tenant.slug == "ssec").first()
            ssec_id = str(ssec.id)
            token = create_access_token(user_id=96, role="TENANT_ADMIN", tenant_id=ssec.id, username="ssec")

        self.client.cookies.set("access_token", token)
        self.client.cookies.set("active_role", "TENANT_ADMIN")
        self.client.cookies.set("active_tenant_id", ssec_id)

        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        html = res.text
        self.assertIn('href="/employees"', html)
        self.assertIn('href="/enroll"', html)
        self.assertIn('Register New Employee', html)
        self.assertIn('href="/settings"', html)
        self.assertIn('Settings & Themes', html)
        # Obsolete menus and standalone departments are removed from sidebar
        self.assertNotIn('href="/departments"', html)
        self.assertNotIn('href="/nodes"', html)
        self.assertNotIn('href="/mobile-capture"', html)


if __name__ == "__main__":
    unittest.main()
