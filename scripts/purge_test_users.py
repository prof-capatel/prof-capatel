"""
==============================================================================
Face Recognition Attendance System - Target Test Users & Logs Purge Script
==============================================================================
Purges all test student/employee/faculty profiles and associated attendance logs
where the name/identifier contains:
  - Alice
  - Jane
  - Charles
  - Transfer
  - Alpha
  - Bob

Cascading cleanup:
  - AttendanceRecord
  - FaceEncoding
  - TeacherClassAssignment
  - Student
  - User (test accounts)
  - Memory Vector Cache Reload (face_engine.reload_cache)
==============================================================================
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Anaconda OpenSSL DLL setup if on Windows
anaconda_bin = r"C:\ProgramData\Anaconda3\Library\bin"
if os.path.exists(anaconda_bin):
    try:
        os.add_dll_directory(anaconda_bin)
    except Exception:
        pass
    if anaconda_bin not in os.environ.get("PATH", ""):
        os.environ["PATH"] = anaconda_bin + os.pathsep + os.environ.get("PATH", "")

from src.database.session import get_db_context
from src.database.models import (
    Tenant,
    User,
    Student,
    AttendanceRecord,
    FaceEncoding,
    TeacherClassAssignment,
    AuditLog,
)
from src.core.face_engine import face_engine


TARGET_KEYWORDS = ["alice", "jane", "charles", "transfer", "alpha", "bob"]


def purge_test_users_and_logs():
    print("\n" + "=" * 78)
    print(" [DATABASE CLEANUP] Purging Targeted Test Users & Attendance Logs")
    print(f" Target Keywords: {', '.join(k.capitalize() for k in TARGET_KEYWORDS)}")
    print("=" * 78)

    with get_db_context() as db:
        # 1. Find matching student/person profiles
        all_students = db.query(Student).all()
        matching_students = []
        for s in all_students:
            search_str = f"{s.name or ''} {s.roll_number or ''} {s.email or ''}".lower()
            if any(k in search_str for k in TARGET_KEYWORDS):
                matching_students.append(s)

        test_student_ids = [s.id for s in matching_students]

        # 2. Find matching user login accounts (preserving SUPER_ADMIN and core admins)
        all_users = db.query(User).filter(User.role != "SUPER_ADMIN").all()
        matching_users = []
        for u in all_users:
            search_str = f"{u.full_name or ''} {u.username or ''} {u.email or ''}".lower()
            # Also clean ephemeral duplicate test teacher entries
            if any(k in search_str for k in TARGET_KEYWORDS) or u.username.startswith("a.turing_"):
                matching_users.append(u)

        test_user_ids = [u.id for u in matching_users]

        print(f" [*] Identified {len(matching_students)} matching Student/Employee profiles to purge.")
        for s in matching_students:
            print(f"     - [Student #{s.id:3d}] {s.name:25s} | Roll: {s.roll_number:15s} | Tenant #{s.tenant_id} | Role: {s.user_role}")

        print(f"\n [*] Identified {len(matching_users)} matching User accounts to purge.")
        for u in matching_users:
            print(f"     - [User #{u.id:3d}] {u.username:20s} | {u.full_name:25s} | Tenant #{u.tenant_id}")

        if not test_student_ids and not test_user_ids:
            print("\n [OK] No matching test profiles or users found. Database is already clean.")
            return

        # 3. Cascading Child Deletions
        del_logs = 0
        del_faces = 0
        del_assignments = 0
        del_audits = 0

        if test_student_ids:
            del_logs = db.query(AttendanceRecord).filter(AttendanceRecord.student_id.in_(test_student_ids)).delete(synchronize_session=False)
            del_faces = db.query(FaceEncoding).filter(FaceEncoding.student_id.in_(test_student_ids)).delete(synchronize_session=False)
            del_students = db.query(Student).filter(Student.id.in_(test_student_ids)).delete(synchronize_session=False)
        else:
            del_students = 0

        if test_user_ids:
            del_assignments = db.query(TeacherClassAssignment).filter(TeacherClassAssignment.teacher_id.in_(test_user_ids)).delete(synchronize_session=False)
            del_audits = db.query(AuditLog).filter(AuditLog.user_id.in_(test_user_ids)).delete(synchronize_session=False)
            del_users = db.query(User).filter(User.id.in_(test_user_ids)).delete(synchronize_session=False)
        else:
            del_users = 0

        # 4. Commit Changes
        db.commit()
        print("\n" + "-" * 78)
        print(" [DELETION REPORT]")
        print(f"   * Student / Employee Profiles Deleted: {del_students}")
        print(f"   * User Login Accounts Deleted:         {del_users}")
        print(f"   * Face Biometric Vectors Deleted:      {del_faces}")
        print(f"   * Attendance Log Entries Deleted:      {del_logs}")
        print(f"   * Teacher Assignments Cleaned:         {del_assignments}")
        print(f"   * User Audit Entries Cleaned:          {del_audits}")
        print("-" * 78)

        # 5. Flush and resync in-memory Face Recognition Vector Cache
        try:
            face_engine.reload_cache(db)
            print(" [OK] In-Memory Face Engine Encodings Resynchronized.")
        except Exception as e:
            print(f" [!] Face engine memory cache reload: {e}")

    # 6. Active Database Entity Verification
    with get_db_context() as db:
        remaining_students = db.query(Student).order_by(Student.tenant_id.asc(), Student.id.asc()).all()
        remaining_users = db.query(User).order_by(User.tenant_id.asc(), User.id.asc()).all()

        print("\n" + "=" * 78)
        print(" [CLEANUP COMPLETE] Current Active Database Entities:")
        print("=" * 78)
        print(f" Total Authentic Profiles Remaining: {len(remaining_students)}")
        for s in remaining_students:
            t = db.query(Tenant).filter(Tenant.id == s.tenant_id).first()
            t_name = t.name if t else f"Tenant #{s.tenant_id}"
            face_c = db.query(FaceEncoding).filter(FaceEncoding.student_id == s.id).count()
            log_c = db.query(AttendanceRecord).filter(AttendanceRecord.student_id == s.id).count()
            print(f"  * Profile #{s.id:3d} [{t_name:22s}]: {s.name:20s} (Roll: {s.roll_number:15s}, Role: {s.user_role:8s}) | Faces: {face_c}, Logs: {log_c}")

        print(f"\n Total Active Users Remaining: {len(remaining_users)}")
        for u in remaining_users:
            t_name = u.tenant.name if u.tenant else "Global Platform"
            print(f"  * User #{u.id:3d} [{t_name:22s}]: {u.username:16s} ({u.full_name:25s}) | Role: {u.role}")
        print("=" * 78 + "\n")


if __name__ == "__main__":
    purge_test_users_and_logs()
