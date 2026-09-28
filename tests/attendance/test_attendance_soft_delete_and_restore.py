import unittest
from datetime import date, datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database.models import (
    Base,
    Tenant,
    Student,
    AttendanceRecord,
    AuditLog,
    User,
    EmployeeSalaryStructure,
    SalaryTemplate,
    SystemBranding,
    Department,
)
from src.database.session import get_db
from src.server.app import app
from src.server.tenant_middleware import get_current_tenant
from src.server.rbac_middleware import get_current_user, get_current_user_optional
from src.core.payroll_engine import calculate_employee_payroll


class TestAttendanceSoftDeleteAndRestore(unittest.TestCase):

    def setUp(self):
        self.test_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.test_engine)
        Base.metadata.create_all(bind=self.test_engine)
        self.db = self.TestingSessionLocal()

        self.tenant = Tenant(
            name="SoftDelete Test Corp",
            slug="soft-delete-test",
            tenant_type="corporate",
            subscription_plan="PRO",
            is_active=True,
        )
        self.db.add(self.tenant)
        self.db.flush()

        self.admin_user = User(
            tenant_id=self.tenant.id,
            username="admin_test",
            email="admin@test.org",
            role="TENANT_ADMIN",
            full_name="Admin Test",
            password_hash="fakehash",
            is_active=True,
        )
        self.db.add(self.admin_user)

        self.branding = SystemBranding(
            tenant_id=self.tenant.id,
            institution_name="SoftDelete Test Corp",
            short_code="STC",
            currency_symbol="₹",
            payroll_structure="STRUCTURED_SALARY",
        )
        self.db.add(self.branding)

        self.dept = Department(
            tenant_id=self.tenant.id,
            name="Operations",
            code="OPS",
        )
        self.db.add(self.dept)
        self.db.commit()

        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        def override_get_current_tenant():
            return self.tenant

        def override_get_current_user():
            return self.admin_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_tenant] = override_get_current_tenant
        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_current_user_optional] = override_get_current_user

        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(bind=self.test_engine)

    def test_soft_delete_and_restore_lifecycle(self):
        # 1. Create student and attendance record
        student = Student(
            tenant_id=self.tenant.id,
            name="Alice Smith",
            roll_number="EMP-SD-001",
            user_role="employee",
            department="Operations",
            is_active=True,
        )
        self.db.add(student)
        self.db.commit()
        self.db.refresh(student)

        now = datetime.now()
        rec = AttendanceRecord(
            tenant_id=self.tenant.id,
            student_id=student.id,
            node_id="NODE-TEST-01",
            timestamp=now,
            confidence_distance=0.12,
            status="PRESENT",
            punch_type="CHECK_IN",
            check_in_time=now,
            is_deleted=False,
        )
        self.db.add(rec)
        self.db.commit()
        self.db.refresh(rec)
        rec_id = rec.id

        # 2. Verify active query returns the record
        res = self.client.get("/api/v1/attendance/records?roll_number=EMP-SD-001")
        self.assertEqual(res.status_code, 200)
        records = res.json().get("records", [])
        self.assertTrue(any(r["id"] == rec_id for r in records))

        # 3. Soft delete the record via DELETE API
        del_res = self.client.delete(f"/api/v1/attendance/records/{rec_id}")
        self.assertEqual(del_res.status_code, 200)
        del_data = del_res.json()
        self.assertEqual(del_data.get("status"), "success")
        self.assertTrue(del_data.get("is_deleted"))

        # Verify DB state
        self.db.refresh(rec)
        self.assertTrue(rec.is_deleted)
        self.assertIsNotNone(rec.deleted_at)
        self.assertEqual(rec.deleted_by, "admin_test")

        # Verify Audit Log
        audit = self.db.query(AuditLog).filter(
            AuditLog.tenant_id == self.tenant.id,
            AuditLog.action_type == "ATTENDANCE_RECORD_DELETED",
            AuditLog.target_id == str(rec_id),
        ).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.actor_name, "Admin Test")

        # 4. Verify default query omits the soft-deleted record
        res_active = self.client.get("/api/v1/attendance/records?roll_number=EMP-SD-001")
        self.assertEqual(res_active.status_code, 200)
        records_active = res_active.json().get("records", [])
        self.assertFalse(any(r["id"] == rec_id for r in records_active))

        # 5. Verify query with view_mode=deleted returns the record
        res_deleted = self.client.get("/api/v1/attendance/records?roll_number=EMP-SD-001&view_mode=deleted")
        self.assertEqual(res_deleted.status_code, 200)
        records_deleted = res_deleted.json().get("records", [])
        self.assertTrue(any(r["id"] == rec_id for r in records_deleted))

        # 6. Verify query with view_mode=all returns the record
        res_all = self.client.get("/api/v1/attendance/records?roll_number=EMP-SD-001&view_mode=all")
        self.assertEqual(res_all.status_code, 200)
        records_all = res_all.json().get("records", [])
        self.assertTrue(any(r["id"] == rec_id for r in records_all))

        # 7. Restore the record via restore API
        restore_res = self.client.post(f"/api/v1/attendance/records/{rec_id}/restore")
        self.assertEqual(restore_res.status_code, 200)
        restore_data = restore_res.json()
        self.assertEqual(restore_data.get("status"), "success")
        self.assertFalse(restore_data.get("is_deleted"))

        # Verify DB state
        self.db.refresh(rec)
        self.assertFalse(rec.is_deleted)
        self.assertIsNone(rec.deleted_at)
        self.assertIsNone(rec.deleted_by)

        # Verify Audit Log for restore
        audit_restore = self.db.query(AuditLog).filter(
            AuditLog.tenant_id == self.tenant.id,
            AuditLog.action_type == "ATTENDANCE_RECORD_RESTORED",
            AuditLog.target_id == str(rec_id),
        ).first()
        self.assertIsNotNone(audit_restore)

        # 8. Verify record is back in active records query
        res_restored = self.client.get("/api/v1/attendance/records?roll_number=EMP-SD-001")
        self.assertEqual(res_restored.status_code, 200)
        records_restored = res_restored.json().get("records", [])
        self.assertTrue(any(r["id"] == rec_id for r in records_restored))

    def test_soft_deleted_attendance_excluded_from_payroll(self):
        student = Student(
            tenant_id=self.tenant.id,
            name="Bob Builder",
            roll_number="EMP-SD-002",
            user_role="employee",
            monthly_base_salary=30000.0,
            is_active=True,
        )
        self.db.add(student)
        self.db.commit()
        self.db.refresh(student)

        # Active salary structure
        struct = EmployeeSalaryStructure(
            tenant_id=self.tenant.id,
            student_id=student.id,
            compensation_model="STRUCTURED_SALARY",
            monthly_gross=45000.0,
            monthly_basic=25000.0,
            monthly_da=2500.0,
            monthly_hra=5000.0,
            daily_rate=1500.0,
            hourly_rate=187.5,
            effective_from_date=date(2026, 9, 1),
            is_current=True,
        )
        self.db.add(struct)

        # 1 active record and 1 soft-deleted record
        rec1 = AttendanceRecord(
            tenant_id=self.tenant.id,
            student_id=student.id,
            node_id="NODE-1",
            timestamp=datetime(2026, 9, 10, 10, 0, 0),
            confidence_distance=0.1,
            status="PRESENT",
            punch_type="CHECK_IN",
            check_in_time=datetime(2026, 9, 10, 10, 0, 0),
            check_out_time=datetime(2026, 9, 10, 18, 0, 0),
            work_duration_minutes=480,
            is_deleted=False,
        )
        rec2_deleted = AttendanceRecord(
            tenant_id=self.tenant.id,
            student_id=student.id,
            node_id="NODE-1",
            timestamp=datetime(2026, 9, 11, 10, 0, 0),
            confidence_distance=0.1,
            status="PRESENT",
            punch_type="CHECK_IN",
            check_in_time=datetime(2026, 9, 11, 10, 0, 0),
            check_out_time=datetime(2026, 9, 11, 18, 0, 0),
            work_duration_minutes=480,
            is_deleted=True,
            deleted_at=datetime.now(),
            deleted_by="admin_test",
        )
        self.db.add_all([rec1, rec2_deleted])
        self.db.commit()

        payroll_res = calculate_employee_payroll(
            db=self.db,
            tenant=self.tenant,
            student=student,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 30),
            total_working_days=26.0,
        )

        # Present days should be exactly 1.0 (rec1), soft-deleted rec2 must be ignored
        self.assertEqual(payroll_res["present_days"], 1.0)

        # Parameter breakdown inspection
        params = payroll_res.get("breakdown", {}).get("parameters", {})
        self.assertEqual(params.get("monthly_basic"), 25000.0)
        self.assertEqual(params.get("da_percentage"), 10.0)
        self.assertEqual(params.get("hra_percentage"), 20.0)
        self.assertIn("daily_salary_rate", params)
        self.assertEqual(params.get("compensation_model"), "STRUCTURED_SALARY")


if __name__ == "__main__":
    unittest.main()
