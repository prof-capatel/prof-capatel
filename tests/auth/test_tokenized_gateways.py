import os
import sys
from pathlib import Path
import unittest
import uuid
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
from src.database.models import Tenant, SystemBranding, User, Student, AttendanceRecord
from src.server.app import app
from src.server.rbac_middleware import create_access_token
from src.utils.auth_utils import hash_password
from src.utils.timezone import get_ist_now


class TestTokenizedGatewaysAndMapPicker(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Initialize DB and create TestClient."""
        init_db()
        cls.client = TestClient(app)

        # Ensure Super Admin exists for authenticated super-admin endpoints
        with get_db_context() as db:
            super_user = db.query(User).filter(User.username == "superadmin").first()
            if not super_user:
                super_user = User(
                    tenant_id=1,
                    username="superadmin",
                    email="superadmin@global.system",
                    password_hash=hash_password("admin123"),
                    role="SUPER_ADMIN",
                    full_name="Global Super Administrator",
                    is_active=True,
                )
                db.add(super_user)
                db.commit()
                db.refresh(super_user)
            else:
                super_user.password_hash = hash_password("admin123")
                db.commit()

            cls.super_admin_token = create_access_token(
                user_id=super_user.id,
                role="SUPER_ADMIN",
                tenant_id=1,
                username="superadmin",
            )

    def test_01_tenant_uuid_and_tokens_backfill(self):
        """Verify default tenant has UUID, admin_token, onboarding_token, and attendance_slug."""
        with get_db_context() as db:
            default_tenant = db.query(Tenant).filter(Tenant.id == 1).first()
            self.assertIsNotNone(default_tenant, "Default tenant should exist")
            self.assertIsNotNone(default_tenant.uuid, "Default tenant should have uuid")
            self.assertIsNotNone(default_tenant.admin_token, "Default tenant should have admin_token")
            self.assertIsNotNone(default_tenant.onboarding_token, "Default tenant should have onboarding_token")
            self.assertIsNotNone(default_tenant.attendance_slug, "Default tenant should have attendance_slug")
            
            t_dict = default_tenant.to_dict()
            self.assertIn("admin_login_url", t_dict)
            self.assertIn("onboarding_url", t_dict)
            self.assertIn("checkin_url", t_dict)
            self.assertTrue(t_dict["admin_login_url"].startswith("/auth/token-login/"))
            self.assertTrue(t_dict["onboarding_url"].startswith("/onboard/"))
            self.assertTrue(t_dict["checkin_url"].startswith("/check-in/"))

    def test_02_super_admin_create_corporate_tenant(self):
        """Verify Super Admin tenant provisioning returns direct access links."""
        test_slug = f"corp-test-{uuid.uuid4().hex[:6]}"
        headers = {"Authorization": f"Bearer {self.super_admin_token}"}
        payload = {
            "name": "Acme Global Corp",
            "slug": test_slug,
            "contact_email": "admin@acme.corp",
            "tenant_type": "corporate",
            "subscription_plan": "ENTERPRISE",
            "max_face_encodings": 1000,
            "max_nodes": 20,
            "admin_username": f"admin_{test_slug[:8]}",
            "admin_password": "CorpAdminPassword@2026",
            "admin_full_name": "Corporate Admin Lead",
        }

        resp = self.client.post("/api/v1/super-admin/tenants", json=payload, headers=headers)
        self.assertEqual(resp.status_code, 201, f"Create tenant failed: {resp.text}")
        data = resp.json()
        self.assertEqual(data["status"], "success")
        tenant_obj = data["tenant"]
        links_obj = data["links"]
        self.assertEqual(tenant_obj["slug"], test_slug)
        self.assertEqual(tenant_obj["tenant_type"], "corporate")
        self.assertIsNotNone(tenant_obj.get("uuid"))
        self.assertIsNotNone(tenant_obj.get("admin_token"))
        self.assertIsNotNone(tenant_obj.get("onboarding_token"))
        self.assertIsNotNone(tenant_obj.get("attendance_slug"))
        self.assertIsNotNone(links_obj.get("admin_login_url"))
        self.assertIsNotNone(links_obj.get("onboarding_url"))
        self.assertIsNotNone(links_obj.get("checkin_url"))

        tenant_id = tenant_obj["id"]
        tenant_uuid = tenant_obj["uuid"]
        admin_token = tenant_obj["admin_token"]
        onboarding_token = tenant_obj["onboarding_token"]
        attendance_slug = tenant_obj["attendance_slug"]

        # Test GET tenant links endpoint
        links_resp = self.client.get(f"/api/v1/super-admin/tenants/{tenant_id}/links", headers=headers)
        self.assertEqual(links_resp.status_code, 200)
        links_data = links_resp.json()
        self.assertEqual(links_data["uuid"], tenant_uuid)
        self.assertEqual(links_data["links"]["admin_login_url"], f"/auth/token-login/{tenant_uuid}/{admin_token}")

        # Test Token Rotation endpoint
        rotate_resp = self.client.post(
            f"/api/v1/super-admin/tenants/{tenant_id}/regenerate-tokens?rotate_admin=true&rotate_onboarding=true",
            headers=headers
        )
        self.assertEqual(rotate_resp.status_code, 200)
        rotated_data = rotate_resp.json()
        new_admin_url = rotated_data["links"]["admin_login_url"]
        self.assertNotEqual(links_data["links"]["admin_login_url"], new_admin_url, "Token should be regenerated")

    def test_03_passwordless_admin_token_login(self):
        """Verify GET /auth/token-login/{tenant_uuid}/{admin_token} establishes authenticated session."""
        with get_db_context() as db:
            tenant = db.query(Tenant).filter(Tenant.id == 1).first()
            tenant_uuid = tenant.uuid or tenant.slug
            admin_token = tenant.admin_token

        # Follow redirects = False to verify cookie and redirect status
        resp = self.client.get(f"/auth/token-login/{tenant_uuid}/{admin_token}", follow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(resp.headers.get("location"), "/")
        self.assertIn("access_token", resp.cookies)
        self.assertIn("active_role", resp.cookies)
        self.assertEqual(resp.cookies["active_role"], "TENANT_ADMIN")

    def test_04_public_onboarding_page_and_registration(self):
        """Verify GET /onboard/{tenant_uuid}/{onboarding_token} and POST /api/v1/enroll/onboard/register."""
        with get_db_context() as db:
            tenant = db.query(Tenant).filter(Tenant.id == 1).first()
            tenant_uuid = tenant.uuid or tenant.slug
            onboarding_token = tenant.onboarding_token

        # 1. Test HTML Page render
        page_resp = self.client.get(f"/onboard/{tenant_uuid}/{onboarding_token}")
        self.assertEqual(page_resp.status_code, 200)
        self.assertIn("Face Registration Portal", page_resp.text)

        # 2. Test Register API
        test_roll = f"EMP-{uuid.uuid4().hex[:6].upper()}"
        reg_payload = {
            "tenant_uuid": tenant_uuid,
            "onboarding_token": onboarding_token,
            "roll_number": test_roll,
            "name": "Jane Employee",
            "email": f"{test_roll.lower()}@corporate.com",
            "department": "Engineering",
        }
        reg_resp = self.client.post("/api/v1/enroll/onboard/register", json=reg_payload)
        self.assertEqual(reg_resp.status_code, 200, f"Register failed: {reg_resp.text}")
        reg_data = reg_resp.json()
        self.assertEqual(reg_data["status"], "success")
        self.assertEqual(reg_data["student"]["roll_number"], test_roll)

    def test_05_permanent_self_attendance_checkin_page(self):
        """Verify GET /check-in/{tenant_uuid}/{attendance_slug} serves self_attendance.html."""
        with get_db_context() as db:
            tenant = db.query(Tenant).filter(Tenant.id == 1).first()
            tenant_uuid = tenant.uuid or tenant.slug
            attendance_slug = tenant.attendance_slug
            tenant_name = tenant.name
            
            # Ensure branding has self-attendance enabled and geofence set
            branding = tenant.branding
            if not branding:
                branding = SystemBranding(tenant_id=tenant.id, institution_name=tenant.name, short_code="TEST-HUB")
                db.add(branding)
            branding.institution_name = tenant.name
            branding.enable_self_attendance = True
            branding.geo_latitude = 23.0225
            branding.geo_longitude = 72.5714
            db.commit()

        resp = self.client.get(f"/check-in/{tenant_uuid}/{attendance_slug}")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Campus Geofence Radar", resp.text)
        self.assertIn(tenant_name, resp.text)

    def test_06_map_geofence_branding_sync(self):
        """Verify geofence coordinates update via /api/v1/branding and reflection in /self-config."""
        headers = {"Authorization": f"Bearer {self.super_admin_token}"}
        update_data = {
            "institution_name": "Antigravity HQ Campus",
            "short_code": "AGY-HQ",
            "enable_self_attendance": True,
            "geo_latitude": 23.0225,
            "geo_longitude": 72.5714,
            "geo_radius_meters": 200.0,
            "max_gps_accuracy_meters": 60.0,
        }

        put_resp = self.client.post("/api/v1/branding", json=update_data, headers=headers)
        self.assertEqual(put_resp.status_code, 200, f"Branding update failed: {put_resp.text}")

        # Check /api/v1/attendance/self-config
        with get_db_context() as db:
            tenant = db.query(Tenant).filter(Tenant.id == 1).first()
            tenant_slug = tenant.slug

        cfg_resp = self.client.get(f"/api/v1/attendance/self-config?tenant_slug={tenant_slug}")
        self.assertEqual(cfg_resp.status_code, 200)
        cfg = cfg_resp.json()
        self.assertTrue(cfg["enable_self_attendance"])
        self.assertAlmostEqual(cfg["geo_latitude"], 23.0225, places=4)
        self.assertAlmostEqual(cfg["geo_longitude"], 72.5714, places=4)
        self.assertEqual(cfg["geo_radius_meters"], 200.0)


    def test_07_tenant_scoped_logs_and_filters(self):
        """Verify dynamic tenant-scoped department, custom roles, and corporate headers on /logs."""
        with get_db_context() as db:
            # Create a corporate tenant
            corp_slug = f"corp-filter-{uuid.uuid4().hex[:6]}"
            corp_tenant = Tenant(
                name="Acme Tech Innovations",
                slug=corp_slug,
                tenant_type="corporate",
                is_active=True,
            )
            db.add(corp_tenant)
            db.commit()
            db.refresh(corp_tenant)
            corp_tenant_id = corp_tenant.id

            # Create an admin user belonging strictly to this corporate tenant
            corp_user = User(
                tenant_id=corp_tenant_id,
                username=f"admin_{corp_slug}",
                email=f"admin@{corp_slug}.corp",
                password_hash=hash_password("admin123"),
                role="TENANT_ADMIN",
                full_name="Corp Admin Lead",
                is_active=True,
            )
            db.add(corp_user)
            db.commit()
            db.refresh(corp_user)
            corp_user_id = corp_user.id
            corp_username = corp_user.username

            # Add a student with custom user_role and custom department
            custom_role_member = Student(
                tenant_id=corp_tenant_id,
                roll_number="DEV-999",
                name="Alex Engineer",
                department="AI Research Division",
                user_role="lead_architect",
                is_active=True,
            )
            db.add(custom_role_member)
            db.commit()

            corp_token = create_access_token(
                user_id=corp_user_id,
                role="TENANT_ADMIN",
                tenant_id=corp_tenant_id,
                username=corp_username,
            )

        # 1. Request /logs as corporate tenant admin
        headers = {
            "Authorization": f"Bearer {corp_token}",
            "X-Tenant-ID": str(corp_tenant_id),
        }
        resp = self.client.get("/logs", headers=headers)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("AI Research Division", resp.text)
        self.assertIn("lead_architect", resp.text)
        self.assertIn("Employee Code / ID", resp.text)
        self.assertIn("Check-In", resp.text)
        self.assertIn("Check-Out", resp.text)

        # 2. Test filtered attendance records & export
        rec_resp = self.client.get(
            "/api/v1/attendance/records?department=AI Research Division&user_role=lead_architect",
            headers=headers,
        )
        self.assertEqual(rec_resp.status_code, 200)
        rec_data = rec_resp.json()
        self.assertEqual(rec_data["status"], "success")

        # 3. Test export with filters
        export_resp = self.client.get(
            "/api/v1/attendance/export?department=AI Research Division&user_role=lead_architect&export_format=csv",
            headers=headers,
        )
        self.assertEqual(export_resp.status_code, 200)
        self.assertIn("text/csv", export_resp.headers.get("content-type", ""))

    def test_08_sidebar_navigation_visibility(self):
        """Verify /face-demo is hidden and /self-attendance is strictly conditional on enable_self_attendance."""
        with get_db_context() as db:
            tenant = db.query(Tenant).filter(Tenant.id == 1).first()
            branding = tenant.branding
            if not branding:
                branding = SystemBranding(tenant_id=tenant.id, institution_name=tenant.name, short_code="TEST-HUB")
                db.add(branding)
            # Disable self-attendance
            branding.enable_self_attendance = False
            db.commit()

        # 1. When disabled, /face-demo should not be in sidebar and /self-attendance should not be in sidebar
        resp_disabled = self.client.get("/")
        self.assertEqual(resp_disabled.status_code, 200)
        self.assertNotIn("Visual Demo (No DB)", resp_disabled.text)
        self.assertNotIn("Self-Attendance (GPS)", resp_disabled.text)

        # 2. When enabled, /self-attendance should appear in sidebar while /face-demo remains removed
        with get_db_context() as db:
            branding = db.query(SystemBranding).filter(SystemBranding.tenant_id == 1).first()
            branding.enable_self_attendance = True
            db.commit()

        resp_enabled = self.client.get("/")
        self.assertEqual(resp_enabled.status_code, 200)
        self.assertNotIn("Visual Demo (No DB)", resp_enabled.text)
        self.assertIn("Self-Attendance (GPS)", resp_enabled.text)

    def test_09_corporate_dashboard_metrics_and_labels(self):
        """Verify dynamic metrics, terminology, and KPIs on dashboard for corporate tenants."""
        with get_db_context() as db:
            corp_slug = f"corp-kpi-{uuid.uuid4().hex[:6]}"
            corp_tenant = Tenant(
                name="Apex Global Technologies",
                slug=corp_slug,
                tenant_type="corporate",
                is_active=True,
            )
            db.add(corp_tenant)
            db.commit()
            db.refresh(corp_tenant)
            corp_tenant_id = corp_tenant.id

            corp_user = User(
                tenant_id=corp_tenant_id,
                username=f"admin_{corp_slug}",
                email=f"lead@{corp_slug}.com",
                password_hash=hash_password("admin123"),
                role="TENANT_ADMIN",
                full_name="Apex VP Admin",
                is_active=True,
            )
            db.add(corp_user)
            db.commit()
            db.refresh(corp_user)

            # Add two active corporate profiles
            emp1 = Student(
                tenant_id=corp_tenant_id,
                roll_number="APX-101",
                name="Dev Employee",
                department="Engineering",
                user_role="employee",
                is_active=True,
            )
            emp2 = Student(
                tenant_id=corp_tenant_id,
                roll_number="APX-102",
                name="Product Manager",
                department="Product",
                user_role="manager",
                is_active=True,
            )
            db.add_all([emp1, emp2])
            db.commit()
            db.refresh(emp1)

            # Record attendance for emp1 today
            record = AttendanceRecord(
                tenant_id=corp_tenant_id,
                student_id=emp1.id,
                node_id="CORP-LOBBY-01",
                timestamp=get_ist_now(),
                confidence_distance=0.15,
                status="PRESENT",
            )
            db.add(record)
            db.commit()

            corp_token = create_access_token(
                user_id=corp_user.id,
                role="TENANT_ADMIN",
                tenant_id=corp_tenant_id,
                username=corp_user.username,
            )

        headers = {
            "Authorization": f"Bearer {corp_token}",
            "X-Tenant-ID": str(corp_tenant_id),
        }

        # 1. HTML Dashboard Render
        dash_resp = self.client.get("/", headers=headers)
        self.assertEqual(dash_resp.status_code, 200)
        self.assertIn("Total Enrolled Employees", dash_resp.text)
        self.assertIn("Checked-In Today", dash_resp.text)
        self.assertNotIn("Enrolled Students", dash_resp.text)

        # 2. Stats API Endpoint
        stats_resp = self.client.get("/api/v1/attendance/stats", headers=headers)
        self.assertEqual(stats_resp.status_code, 200)
        stats = stats_resp.json()
        self.assertTrue(stats["is_corporate"])
        self.assertEqual(stats["member_label"], "Employees")
        self.assertEqual(stats["total_members"], 2)
        self.assertEqual(stats["present_today"], 1)
        self.assertEqual(stats["attendance_percentage"], 50.0)

    def test_10_corporate_analytics_and_compliance_export(self):
        """Verify corporate analytics aggregation, department breakdowns, and compliance export."""
        with get_db_context() as db:
            corp_slug = f"corp-ana-{uuid.uuid4().hex[:6]}"
            corp_tenant = Tenant(
                name="Apex Global Technologies",
                slug=corp_slug,
                tenant_type="company",
                is_active=True,
            )
            db.add(corp_tenant)
            db.commit()
            db.refresh(corp_tenant)
            corp_tenant_id = corp_tenant.id

            corp_user = User(
                tenant_id=corp_tenant_id,
                username=f"admin_{corp_slug}",
                email=f"admin@{corp_slug}.com",
                password_hash=hash_password("admin123"),
                role="TENANT_ADMIN",
                full_name="Company HR Admin",
                is_active=True,
            )
            db.add(corp_user)
            db.commit()
            db.refresh(corp_user)

            emp1 = Student(
                tenant_id=corp_tenant_id,
                roll_number="CMP-001",
                name="Alice Dev",
                department="DevOps",
                user_role="employee",
                is_active=True,
            )
            emp2 = Student(
                tenant_id=corp_tenant_id,
                roll_number="CMP-002",
                name="Bob Lead",
                department="Management",
                user_role="manager",
                is_active=True,
            )
            db.add_all([emp1, emp2])
            db.commit()

            corp_token = create_access_token(
                user_id=corp_user.id,
                role="TENANT_ADMIN",
                tenant_id=corp_tenant_id,
                username=corp_user.username,
            )

        headers = {
            "Authorization": f"Bearer {corp_token}",
            "X-Tenant-ID": str(corp_tenant_id),
        }

        # 1. Analytics HTML Page
        ana_page = self.client.get("/analytics", headers=headers)
        self.assertEqual(ana_page.status_code, 200)
        self.assertIn("Workforce Analytics", ana_page.text)
        self.assertIn("Total Enrolled Employees", ana_page.text)
        self.assertIn("Low Attendance Employees / Defaulters List", ana_page.text)
        self.assertIn("Employee Profile", ana_page.text)
        self.assertIn("Employee ID", ana_page.text)
        self.assertIn("Days Present", ana_page.text)

        # 2. Analytics JSON API
        ana_resp = self.client.get("/api/v1/attendance/analytics?defaulter_threshold=75.0", headers=headers)
        self.assertEqual(ana_resp.status_code, 200)
        ana_data = ana_resp.json()
        self.assertEqual(ana_data["status"], "success")
        self.assertTrue(ana_data["is_corporate"])
        self.assertEqual(ana_data["member_label"], "Employees")
        self.assertEqual(ana_data["headcount"]["employees"], 1)
        self.assertEqual(ana_data["headcount"]["managers"], 1)
        self.assertEqual(len(ana_data["departments"]), 2)

        # 3. Compliance CSV Export
        exp_resp = self.client.get("/api/v1/attendance/export-compliance?export_format=csv", headers=headers)
        self.assertEqual(exp_resp.status_code, 200)
        csv_text = exp_resp.text
        self.assertIn("Corporate Attendance & Workforce Compliance Audit", csv_text)
        self.assertIn("Employee Code / ID", csv_text)
        self.assertIn("Designation / Role", csv_text)
        self.assertIn("Working Days Recorded", csv_text)
        self.assertIn("Days Present", csv_text)
        self.assertNotIn("Class / Semester", csv_text)


if __name__ == "__main__":
    unittest.main()
