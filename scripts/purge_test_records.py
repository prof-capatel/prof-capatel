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
    LeaveCadreQuota,
    LeaveBalance,
    LeaveRequest,
)
from src.utils.auth_utils import hash_password

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("purge_test_records")

CORE_TENANT_SLUGS = ["default", "pulin1", "ssec", "gecm", "raymond-store-1"]
CORE_USERNAMES = ["superadmin", "admin", "teacher1", "student1", "ssec", "gecm", "raymond"]


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
            Student.name.ilike("%test%") | Student.name.ilike("Alice%") | Student.name.ilike("Bob%") | Student.name.ilike("Jane%") | Student.name.ilike("Charles%") | Student.name.ilike("Alex%") | Student.name.ilike("%Xavier%"),
        ).all()

        purged_student_ids = []
        for s in test_students:
            purged_student_ids.append(s.id)
            logger.info(f"Targeting test student for deletion: ID #{s.id} - '{s.name}' (Roll: {s.roll_number}, Tenant: {s.tenant_id})")

        # 3. Delete attendance logs associated with test students
        if purged_student_ids:
            deleted_logs = db.query(AttendanceRecord).filter(
                AttendanceRecord.student_id.in_(purged_student_ids)
            ).delete(synchronize_session=False)
            logger.info(f"Deleted {deleted_logs} attendance records for test students.")

            # 4. Delete leave requests and balances for test students
            deleted_reqs = db.query(LeaveRequest).filter(
                LeaveRequest.student_id.in_(purged_student_ids)
            ).delete(synchronize_session=False)
            deleted_bals = db.query(LeaveBalance).filter(
                LeaveBalance.student_id.in_(purged_student_ids)
            ).delete(synchronize_session=False)
            logger.info(f"Deleted {deleted_reqs} leave requests and {deleted_bals} leave balances for test students.")

            # 5. Delete face encodings associated with test students
            deleted_faces = db.query(FaceEncoding).filter(
                FaceEncoding.student_id.in_(purged_student_ids)
            ).delete(synchronize_session=False)
            logger.info(f"Deleted {deleted_faces} face encoding vectors for test students.")

            # 6. Delete test student rows
            deleted_stds = db.query(Student).filter(
                Student.id.in_(purged_student_ids)
            ).delete(synchronize_session=False)
            logger.info(f"Deleted {deleted_stds} test student records.")

        # 6. Ensure core admin accounts have valid standard demo passwords
        core_admins = db.query(User).filter(User.role.in_(["SUPER_ADMIN", "TENANT_ADMIN"])).all()
        for u in core_admins:
            u.password_hash = hash_password("admin123")
        db.flush()
        logger.info(f"Standardized passwords to 'admin123' for {len(core_admins)} administrators.")

        # 7. Delete test users outside core list
        test_users = db.query(User).filter(
            User.username.ilike("test_%") | User.username.ilike("dummy_%") | User.username.ilike("a.turing_%") | User.username.ilike("prof_%")
        ).all()
        for u in test_users:
            if u.username not in CORE_USERNAMES:
                logger.info(f"Deleting test user: ID #{u.id} - '{u.username}'")
                db.delete(u)

        # 8. Audit Log record of cleanup
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
