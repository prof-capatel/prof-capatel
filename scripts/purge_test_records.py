import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from sqlalchemy.orm import Session
from src.database.session import SessionLocal
from src.database.models import (
    Tenant,
    User,
    Student,
    AttendanceRecord,
    FaceEncoding,
    AuditLog,
    SystemBranding,
    LeaveType,
    LeaveBalance,
    LeaveRequest,
    CompanyLocation,
    DesignationMaster,
    SalaryTemplate,
    SalaryComponent,
    EmployeeSalaryStructure,
    SalaryRevisionHistory,
    PayrollBatch,
    PayrollPayslip,
)
from src.utils.auth_utils import hash_password

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("purge_test_records")

CORE_TENANT_SLUGS = ["default", "pulin1", "ssec", "gecm", "raymond-store-1", "the-retail-store"]
CORE_USERNAMES = ["superadmin", "admin", "teacher1", "student1", "ssec", "gecm", "raymond", "admin_retail"]


def purge_test_records():
    db: Session = SessionLocal()
    try:
        logger.info("Starting safe test record cleanup...")

        # 1. Update Tenant #1 System Branding if necessary to align with platform title
        b1 = db.query(SystemBranding).filter(SystemBranding.tenant_id == 1).first()
        if b1 and b1.institution_name in ["Antigravity HQ Campus", "Test School"]:
            b1.institution_name = "Face Recognition - Attendance System"
            b1.tagline = "Enterprise Multi-Tenant Biometric Attendance Platform"
            db.flush()
            logger.info("Updated Tenant #1 branding institution name to 'Face Recognition - Attendance System'.")

        # 2. Clean up non-core test tenants created by automated test runs
        test_tenants = db.query(Tenant).filter(~Tenant.slug.in_(CORE_TENANT_SLUGS)).all()
        for tt in test_tenants:
            logger.info(f"Purging test tenant #{tt.id}: '{tt.name}' ({tt.slug})")
            db.delete(tt)
        db.flush()

        # 3. Identify test students to purge in core tenants
        test_students = db.query(Student).filter(
            Student.name.ilike("%test%") | Student.name.ilike("Alice%") | Student.name.ilike("Bob%") | Student.name.ilike("Jane%") | Student.name.ilike("Charles%") | Student.name.ilike("Alex%") | Student.name.ilike("%Xavier%") | Student.name.ilike("Temporary%"),
        ).all()

        purged_student_ids = []
        for s in test_students:
            purged_student_ids.append(s.id)
            logger.info(f"Targeting test student for deletion: ID #{s.id} - '{s.name}' (Roll: {s.roll_number}, Tenant: {s.tenant_id})")

        if purged_student_ids:
            # Delete payslips for test students
            db.query(PayrollPayslip).filter(PayrollPayslip.student_id.in_(purged_student_ids)).delete(synchronize_session=False)
            # Delete salary revision history and structures for test students
            db.query(SalaryRevisionHistory).filter(SalaryRevisionHistory.student_id.in_(purged_student_ids)).delete(synchronize_session=False)
            db.query(EmployeeSalaryStructure).filter(EmployeeSalaryStructure.student_id.in_(purged_student_ids)).delete(synchronize_session=False)

            # Delete attendance logs associated with test students
            deleted_logs = db.query(AttendanceRecord).filter(
                AttendanceRecord.student_id.in_(purged_student_ids)
            ).delete(synchronize_session=False)
            logger.info(f"Deleted {deleted_logs} attendance records for test students.")

            # Delete leave requests and balances for test students
            deleted_reqs = db.query(LeaveRequest).filter(
                LeaveRequest.student_id.in_(purged_student_ids)
            ).delete(synchronize_session=False)
            deleted_bals = db.query(LeaveBalance).filter(
                LeaveBalance.student_id.in_(purged_student_ids)
            ).delete(synchronize_session=False)
            logger.info(f"Deleted {deleted_reqs} leave requests and {deleted_bals} leave balances for test students.")

            # Delete face encodings associated with test students
            deleted_faces = db.query(FaceEncoding).filter(
                FaceEncoding.student_id.in_(purged_student_ids)
            ).delete(synchronize_session=False)
            logger.info(f"Deleted {deleted_faces} face encoding vectors for test students.")

            # Delete test student rows
            deleted_stds = db.query(Student).filter(
                Student.id.in_(purged_student_ids)
            ).delete(synchronize_session=False)
            logger.info(f"Deleted {deleted_stds} test student records.")

        # 4. Clean up test/orphaned payroll batches and test templates
        test_batches = db.query(PayrollBatch).filter(
            PayrollBatch.batch_number.ilike("%TEST%") | PayrollBatch.batch_number.ilike("%DUMMY%") | (PayrollBatch.period_year > 2050)
        ).all()
        for tb in test_batches:
            logger.info(f"Deleting test payroll batch #{tb.id}: '{tb.batch_number}'")
            db.delete(tb)

        test_templates = db.query(SalaryTemplate).filter(
            SalaryTemplate.name.ilike("test_%") | SalaryTemplate.name.ilike("dummy_%") | SalaryTemplate.code.ilike("TEST_%")
        ).all()
        for tt in test_templates:
            logger.info(f"Deleting test salary template #{tt.id}: '{tt.name}'")
            db.delete(tt)

        test_desigs = db.query(DesignationMaster).filter(
            DesignationMaster.title.ilike("test_%") | DesignationMaster.code.ilike("TEST_%")
        ).all()
        for td in test_desigs:
            logger.info(f"Deleting test designation #{td.id}: '{td.title}'")
            db.delete(td)

        test_locs = db.query(CompanyLocation).filter(
            CompanyLocation.name.ilike("test_%") | CompanyLocation.code.ilike("TEST_%")
        ).all()
        for tl in test_locs:
            logger.info(f"Deleting test location #{tl.id}: '{tl.name}'")
            db.delete(tl)

        db.flush()

        # 5. Ensure core admin accounts have valid standard demo passwords
        core_admins = db.query(User).filter(User.role.in_(["SUPER_ADMIN", "TENANT_ADMIN"])).all()
        for u in core_admins:
            u.password_hash = hash_password("admin123")
        db.flush()
        logger.info(f"Standardized passwords to 'admin123' for {len(core_admins)} administrators.")

        # 6. Delete test users outside core list
        test_users = db.query(User).filter(
            User.username.ilike("test_%") | User.username.ilike("dummy_%") | User.username.ilike("a.turing_%") | User.username.ilike("prof_%")
        ).all()
        for u in test_users:
            if u.username not in CORE_USERNAMES:
                logger.info(f"Deleting test user: ID #{u.id} - '{u.username}'")
                db.delete(u)

        # 7. Audit Log record of cleanup
        audit = AuditLog(
            tenant_id=None,
            user_id=1,
            actor_name="System Automated Purge",
            actor_role="SUPER_ADMIN",
            action_type="TEST_RECORDS_PURGED",
            target_type="DATABASE",
            target_id="GLOBAL",
            description=f"Automated test record purge executed cleanly. Purged students: {purged_student_ids}.",
        )
        db.add(audit)
        db.commit()

        # 8. Report final entity counts
        total_tenants = db.query(Tenant).filter(Tenant.is_deleted == False).count()
        total_users = db.query(User).count()
        total_students = db.query(Student).count()
        total_attendance = db.query(AttendanceRecord).count()

        logger.info(f"Cleanup completed successfully!")
        logger.info(f"Active Tenants: {total_tenants} | Users: {total_users} | Students/Employees: {total_students} | Attendance Records: {total_attendance}")

        print(f"\n--- PURGE REPORT ---")
        print(f"Purged test student IDs: {purged_student_ids}")
        print(f"Preserved Core Tenants: {[(t.id, t.name, t.slug, t.tenant_type) for t in db.query(Tenant).filter(Tenant.is_deleted == False).all()]}")
        print(f"Preserved Users: {[(u.id, u.username, u.role, u.tenant_id) for u in db.query(User).all()]}")
        print(f"Preserved Students/Employees: {[(s.id, s.name, s.user_role, s.tenant_id) for s in db.query(Student).all()]}")
        print(f"--------------------\n")

    except Exception as e:
        db.rollback()
        logger.error(f"Error during purge: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    purge_test_records()
