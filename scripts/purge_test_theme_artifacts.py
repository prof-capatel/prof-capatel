"""
==============================================================================
Post-Theme Update Test Record & Dummy Artifact Purge Script
==============================================================================
Scans, identifies, and cleanly purges all temporary test records, debug users,
and dummy artifacts generated during testing and verification of the
Professional Slate corporate theme, while preserving all production/core entities.
==============================================================================
"""

import os
import sys
from pathlib import Path
import logging

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Anaconda OpenSSL DLL directory setup if on Windows
anaconda_bin = r"C:\ProgramData\Anaconda3\Library\bin"
if os.path.exists(anaconda_bin):
    try:
        os.add_dll_directory(anaconda_bin)
    except Exception:
        pass
    if anaconda_bin not in os.environ.get("PATH", ""):
        os.environ["PATH"] = anaconda_bin + os.pathsep + os.environ.get("PATH", "")

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
    LeaveBalance,
    LeaveRequest,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("purge_test_theme_artifacts")

CORE_TENANT_SLUGS = ["default", "pulin1", "ssec", "gecm", "raymond-store-1", "the-retail-store"]
CORE_USERNAMES = ["superadmin", "admin", "teacher1", "student1", "ssec", "gecm", "raymond", "admin_retail"]


def run_theme_test_purge():
    db: Session = SessionLocal()
    try:
        logger.info("Starting post-theme update test record purge...")

        # 1. Clean up temporary test tenants created during test runs
        test_tenants = db.query(Tenant).filter(~Tenant.slug.in_(CORE_TENANT_SLUGS)).all()
        for tt in test_tenants:
            logger.info(f"Purging temporary test tenant #{tt.id}: '{tt.name}' ({tt.slug})")
            db.delete(tt)
        db.flush()

        # 2. Identify test students/employees to purge
        test_students = db.query(Student).filter(
            Student.name.ilike("%test%")
            | Student.name.ilike("Alice%")
            | Student.name.ilike("Bob%")
            | Student.name.ilike("Jane%")
            | Student.name.ilike("Charles%")
            | Student.name.ilike("Alex%")
            | Student.name.ilike("%Xavier%")
            | Student.name.ilike("dummy%"),
        ).all()

        purged_student_ids = [s.id for s in test_students]
        for s in test_students:
            logger.info(f"Targeting test student for deletion: ID #{s.id} - '{s.name}' (Roll: {s.roll_number}, Tenant: {s.tenant_id})")

        if purged_student_ids:
            # Delete attendance records for test students
            deleted_logs = db.query(AttendanceRecord).filter(
                AttendanceRecord.student_id.in_(purged_student_ids)
            ).delete(synchronize_session=False)
            logger.info(f"Deleted {deleted_logs} attendance records for test students.")

            # Delete leave requests and balances
            deleted_reqs = db.query(LeaveRequest).filter(
                LeaveRequest.student_id.in_(purged_student_ids)
            ).delete(synchronize_session=False)
            deleted_bals = db.query(LeaveBalance).filter(
                LeaveBalance.student_id.in_(purged_student_ids)
            ).delete(synchronize_session=False)
            logger.info(f"Deleted {deleted_reqs} leave requests and {deleted_bals} leave balances.")

            # Delete face encodings
            deleted_faces = db.query(FaceEncoding).filter(
                FaceEncoding.student_id.in_(purged_student_ids)
            ).delete(synchronize_session=False)
            logger.info(f"Deleted {deleted_faces} face encoding vectors.")

            # Delete student rows
            deleted_stds = db.query(Student).filter(
                Student.id.in_(purged_student_ids)
            ).delete(synchronize_session=False)
            logger.info(f"Deleted {deleted_stds} test student records.")

        # 3. Clean up temporary test users
        test_users = db.query(User).filter(
            User.username.ilike("test_%")
            | User.username.ilike("dummy_%")
            | User.username.ilike("a.turing_%")
            | User.username.ilike("prof_%")
            | User.username.ilike("tmp_%")
        ).all()

        for u in test_users:
            if u.username not in CORE_USERNAMES:
                logger.info(f"Deleting test user: ID #{u.id} - '{u.username}'")
                db.delete(u)

        # 4. Log audit trail
        audit = AuditLog(
            tenant_id=None,
            user_id=1,
            actor_name="System Automated Theme Purge",
            actor_role="SUPER_ADMIN",
            action_type="TEST_THEME_RECORDS_PURGED",
            target_type="DATABASE",
            target_id="GLOBAL",
            description=f"Post-theme update purge completed. Purged {len(purged_student_ids)} test profiles.",
        )
        db.add(audit)
        db.commit()

        # 5. Final summary
        active_tenants = db.query(Tenant).filter(Tenant.is_deleted == False).count()
        active_users = db.query(User).count()
        active_students = db.query(Student).count()
        active_attendance = db.query(AttendanceRecord).count()

        print("\n========================================================")
        print("   POST-THEME UPDATE PURGE REPORT (Zero Test Records)")
        print("========================================================")
        print(f"  Active Tenants:          {active_tenants}")
        print(f"  Active Users:            {active_users}")
        print(f"  Active Employees/Students:{active_students}")
        print(f"  Attendance Records:      {active_attendance}")
        print(f"  Purged Test Student IDs: {purged_student_ids}")
        print("========================================================\n")

    except Exception as e:
        db.rollback()
        logger.error(f"Error during purge: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_theme_test_purge()
