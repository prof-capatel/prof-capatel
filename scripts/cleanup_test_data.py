"""
==============================================================================
Production Database Cleanup & Test Data Purge Utility
==============================================================================
Purges ephemeral test tenants, automated test accounts, temporary users,
orphan biometric embeddings, attendance logs, and test subscription plans,
ensuring strict preservation of core production entities:
  - Tenant #1:   Antigravity HQ Campus (slug: default)
  - Tenant #106: pulin1                (slug: pulin1)
  - Tenant #115: SSEC                  (slug: ssec)
  - Tenant #155: GECM                  (slug: gecm)
  - Tenant #292: Raymond Store 1       (slug: raymond-store-1)
  - Global Super Administrator         (tenant_id is NULL)
  - Standard Subscription Plans        (FREE, STANDARD, ENTERPRISE)

Usage:
  python scripts/cleanup_test_data.py --dry-run
  python scripts/cleanup_test_data.py --execute
  python scripts/cleanup_test_data.py --execute --clean-orphan-files
==============================================================================
"""

import os
import sys
import argparse
import datetime
from pathlib import Path
from typing import List, Set, Dict, Any

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Windows OpenSSL DLL directory setup if available
anaconda_bin = r"C:\ProgramData\Anaconda3\Library\bin"
if os.path.exists(anaconda_bin):
    try:
        os.add_dll_directory(anaconda_bin)
    except Exception:
        pass
    if anaconda_bin not in os.environ.get("PATH", ""):
        os.environ["PATH"] = anaconda_bin + os.pathsep + os.environ.get("PATH", "")

import pymysql
from sqlalchemy import text
from src.config import (
    MYSQL_HOST,
    MYSQL_PORT,
    MYSQL_USER,
    MYSQL_PASSWORD,
    MYSQL_DB,
    DATABASE_DIR,
    DATA_DIR,
    FACES_DIR,
    SNAPSHOTS_DIR,
)
from src.database.session import get_db_context, SessionLocal
from src.database.models import (
    Tenant,
    User,
    Student,
    AttendanceRecord,
    FaceEncoding,
    NodeDevice,
    SystemBranding,
    Department,
    ClassModel,
    Division,
    AcademicYear,
    TeacherClassAssignment,
    StudentBatchUpload,
    AuditLog,
    SubscriptionPlan,
    LeaveType,
    LeaveCadreQuota,
    LeaveBalance,
    LeaveRequest,
)

# Explicit Whitelist Specifications
CORE_WHITELIST_SPECS = [
    {"id": 1, "slug": "default", "name": "Antigravity HQ Campus"},
    {"id": 106, "slug": "pulin1", "name": "pulin1"},
    {"id": 115, "slug": "ssec", "name": "SSEC"},
    {"id": 155, "slug": "gecm", "name": "GECM"},
    {"id": 292, "slug": "raymond-store-1", "name": "Raymond Store 1"},
]

STANDARD_PLAN_CODES = {"FREE", "STANDARD", "ENTERPRISE"}


def create_database_backup() -> Path:
    """
    Creates a full SQL dump backup of the target MySQL database before any modifications.
    """
    backup_dir = DATABASE_DIR / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"pre_cleanup_backup_{timestamp}.sql"

    print(f"\n[*] Creating pre-cleanup database backup: {backup_file.name} ...")
    
    conn = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )

    with open(backup_file, "w", encoding="utf-8") as f:
        f.write(f"-- Face Recognition Attendance System Database Dump\n")
        f.write(f"-- Generated At: {datetime.datetime.now().isoformat()}\n")
        f.write(f"-- Database: {MYSQL_DB}\n\n")
        f.write("SET FOREIGN_KEY_CHECKS=0;\n\n")

        with conn.cursor() as cursor:
            cursor.execute("SHOW TABLES;")
            tables = [list(r.values())[0] for r in cursor.fetchall()]

            for table in tables:
                cursor.execute(f"SHOW CREATE TABLE `{table}`;")
                create_sql = cursor.fetchone()["Create Table"]
                f.write(f"-- Table structure for table `{table}`\n")
                f.write(f"DROP TABLE IF EXISTS `{table}`;\n")
                f.write(f"{create_sql};\n\n")

                cursor.execute(f"SELECT * FROM `{table}`;")
                rows = cursor.fetchall()
                if rows:
                    f.write(f"-- Dumping data for table `{table}` ({len(rows)} rows)\n")
                    f.write(f"LOCK TABLES `{table}` WRITE;\n")
                    for row in rows:
                        cols = ", ".join([f"`{k}`" for k in row.keys()])
                        vals = []
                        for v in row.values():
                            if v is None:
                                vals.append("NULL")
                            elif isinstance(v, (int, float)):
                                vals.append(str(v))
                            elif isinstance(v, (datetime.datetime, datetime.date)):
                                vals.append(f"'{v}'")
                            elif isinstance(v, bytes):
                                vals.append(f"0x{v.hex()}")
                            else:
                                escaped = str(v).replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n").replace("\r", "\\r")
                                vals.append(f"'{escaped}'")
                        val_str = ", ".join(vals)
                        f.write(f"INSERT INTO `{table}` ({cols}) VALUES ({val_str});\n")
                    f.write("UNLOCK TABLES;\n\n")

        f.write("SET FOREIGN_KEY_CHECKS=1;\n")

    conn.close()
    file_size_kb = backup_file.stat().st_size / 1024
    print(f"[OK] Database backup saved: {backup_file} ({file_size_kb:.1f} KB)")
    return backup_file


def audit_entities(db) -> Dict[str, Any]:
    """
    Performs comprehensive verification and returns audit metadata for core vs test data.
    """
    # 1. Resolve core tenant IDs
    preserved_ids: Set[int] = set()
    core_tenants_info: List[Dict[str, Any]] = []

    for spec in CORE_WHITELIST_SPECS:
        tenant = None
        if "id" in spec:
            tenant = db.query(Tenant).filter(Tenant.id == spec["id"]).first()
        if not tenant and "slug" in spec:
            tenant = db.query(Tenant).filter(Tenant.slug == spec["slug"]).first()
        if not tenant and "name" in spec:
            tenant = db.query(Tenant).filter(Tenant.name.ilike(f"%{spec['name']}%")).first()

        if tenant:
            preserved_ids.add(tenant.id)
            core_tenants_info.append({
                "id": tenant.id,
                "slug": tenant.slug,
                "name": tenant.name,
                "type": tenant.tenant_type,
                "created_at": tenant.created_at,
            })

    # 2. Identify test tenants
    all_tenants = db.query(Tenant).all()
    test_tenants = [t for t in all_tenants if t.id not in preserved_ids]
    test_tenant_ids = [t.id for t in test_tenants]

    # 3. Identify test users (excluding SUPER_ADMIN)
    test_users = db.query(User).filter(
        User.tenant_id.in_(test_tenant_ids),
        User.role != "SUPER_ADMIN"
    ).all() if test_tenant_ids else []

    # 4. Identify test subscription plans
    test_plans = db.query(SubscriptionPlan).filter(
        ~SubscriptionPlan.plan_code.in_(STANDARD_PLAN_CODES)
    ).all()

    # 5. Child table counts
    child_counts = {}
    if test_tenant_ids:
        child_counts["leave_balances"] = db.query(LeaveBalance).filter(LeaveBalance.tenant_id.in_(test_tenant_ids)).count()
        child_counts["leave_requests"] = db.query(LeaveRequest).filter(LeaveRequest.tenant_id.in_(test_tenant_ids)).count()
        child_counts["leave_cadre_quotas"] = db.query(LeaveCadreQuota).filter(LeaveCadreQuota.tenant_id.in_(test_tenant_ids)).count()
        child_counts["leave_types"] = db.query(LeaveType).filter(LeaveType.tenant_id.in_(test_tenant_ids)).count()
        child_counts["attendance_records"] = db.query(AttendanceRecord).filter(AttendanceRecord.tenant_id.in_(test_tenant_ids)).count()
        child_counts["face_encodings"] = db.query(FaceEncoding).filter(FaceEncoding.tenant_id.in_(test_tenant_ids)).count()
        child_counts["teacher_assignments"] = db.query(TeacherClassAssignment).filter(TeacherClassAssignment.tenant_id.in_(test_tenant_ids)).count()
        child_counts["student_batch_uploads"] = db.query(StudentBatchUpload).filter(StudentBatchUpload.tenant_id.in_(test_tenant_ids)).count()
        child_counts["students"] = db.query(Student).filter(Student.tenant_id.in_(test_tenant_ids)).count()
        child_counts["divisions"] = db.query(Division).filter(Division.tenant_id.in_(test_tenant_ids)).count()
        child_counts["classes"] = db.query(ClassModel).filter(ClassModel.tenant_id.in_(test_tenant_ids)).count()
        child_counts["academic_years"] = db.query(AcademicYear).filter(AcademicYear.tenant_id.in_(test_tenant_ids)).count()
        child_counts["departments"] = db.query(Department).filter(Department.tenant_id.in_(test_tenant_ids)).count()
        child_counts["node_devices"] = db.query(NodeDevice).filter(NodeDevice.tenant_id.in_(test_tenant_ids)).count()
        child_counts["system_branding"] = db.query(SystemBranding).filter(SystemBranding.tenant_id.in_(test_tenant_ids)).count()
        child_counts["audit_logs"] = db.query(AuditLog).filter(AuditLog.tenant_id.in_(test_tenant_ids)).count()
    else:
        for k in ["leave_balances", "leave_requests", "leave_cadre_quotas", "leave_types",
                  "attendance_records", "face_encodings", "teacher_assignments", "student_batch_uploads",
                  "students", "divisions", "classes", "academic_years", "departments",
                  "node_devices", "system_branding", "audit_logs"]:
            child_counts[k] = 0

    return {
        "preserved_ids": preserved_ids,
        "core_tenants": core_tenants_info,
        "test_tenant_ids": test_tenant_ids,
        "test_tenants_count": len(test_tenant_ids),
        "test_users_count": len(test_users),
        "test_plans_count": len(test_plans),
        "test_plans": [p.plan_code for p in test_plans],
        "child_counts": child_counts,
    }


def clean_orphan_files(db, execute: bool = False):
    """
    Audits and optionally deletes orphan image files from data/faces and data/snapshots.
    """
    print("\n" + "-" * 78)
    print(" [*] Filesystem Storage Audit (Face Photos & Attendance Snapshots)")
    print("-" * 78)

    # Gather all referenced photo and snapshot paths from database
    db_face_paths = set()
    for enc in db.query(FaceEncoding).all():
        if enc.photo_path:
            clean = enc.photo_path.replace("\\", "/").lstrip("/")
            db_face_paths.add(clean)
            db_face_paths.add(Path(clean).name)

    db_snapshots = set()
    for att in db.query(AttendanceRecord).all():
        if att.snapshot_path:
            clean = att.snapshot_path.replace("\\", "/").lstrip("/")
            db_snapshots.add(clean)
            db_snapshots.add(Path(clean).name)

    # Audit faces directory
    face_files = list(FACES_DIR.glob("**/*.*")) if FACES_DIR.exists() else []
    orphan_faces = [f for f in face_files if f.name not in db_face_paths]

    # Audit snapshots directory
    snapshot_files = list(SNAPSHOTS_DIR.glob("**/*.*")) if SNAPSHOTS_DIR.exists() else []
    orphan_snapshots = [s for s in snapshot_files if s.name not in db_snapshots]

    print(f" Faces Directory:     {len(face_files)} total files | {len(orphan_faces)} orphan files")
    print(f" Snapshots Directory: {len(snapshot_files)} total files | {len(orphan_snapshots)} orphan files")

    if execute:
        deleted_count = 0
        for f in orphan_faces:
            try:
                f.unlink(missing_ok=True)
                deleted_count += 1
            except Exception as e:
                print(f" [!] Failed to delete orphan face file {f}: {e}")

        for s in orphan_snapshots:
            try:
                s.unlink(missing_ok=True)
                deleted_count += 1
            except Exception as e:
                print(f" [!] Failed to delete orphan snapshot file {s}: {e}")

        print(f" [OK] Purged {deleted_count} orphan image files from filesystem.")
    else:
        print(" [i] Dry-run mode: No filesystem files were deleted.")


def execute_purge(db, audit_data: Dict[str, Any]):
    """
    Executes atomic deletion of all test records inside an ACID transaction.
    """
    test_tenant_ids = audit_data["test_tenant_ids"]
    test_plans = audit_data["test_plans"]

    print("\n" + "=" * 78)
    print(" [PURGE EXECUTION] Starting Atomic Database Purge Transaction")
    print("=" * 78)

    if not test_tenant_ids and not test_plans:
        print(" [*] Database is already clean. Nothing to purge.")
        return

    # Ordered Deletion Sequence
    # 1. Leave Subsystem
    del_leave_balances = db.query(LeaveBalance).filter(LeaveBalance.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False) if test_tenant_ids else 0
    del_leave_requests = db.query(LeaveRequest).filter(LeaveRequest.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False) if test_tenant_ids else 0
    del_leave_cadre = db.query(LeaveCadreQuota).filter(LeaveCadreQuota.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False) if test_tenant_ids else 0
    del_leave_types = db.query(LeaveType).filter(LeaveType.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False) if test_tenant_ids else 0

    # 2. Attendance & Biometric Vectors
    del_attendance = db.query(AttendanceRecord).filter(AttendanceRecord.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False) if test_tenant_ids else 0
    del_encodings = db.query(FaceEncoding).filter(FaceEncoding.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False) if test_tenant_ids else 0

    # 3. Faculty Assignments & Batch Uploads
    del_assignments = db.query(TeacherClassAssignment).filter(TeacherClassAssignment.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False) if test_tenant_ids else 0
    del_batch_uploads = db.query(StudentBatchUpload).filter(StudentBatchUpload.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False) if test_tenant_ids else 0

    # 4. Student Profiles
    del_students = db.query(Student).filter(Student.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False) if test_tenant_ids else 0

    # 5. Academic Hierarchy
    del_divisions = db.query(Division).filter(Division.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False) if test_tenant_ids else 0
    del_classes = db.query(ClassModel).filter(ClassModel.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False) if test_tenant_ids else 0
    del_years = db.query(AcademicYear).filter(AcademicYear.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False) if test_tenant_ids else 0
    del_depts = db.query(Department).filter(Department.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False) if test_tenant_ids else 0

    # 6. Infrastructure, Branding & Auditing
    del_nodes = db.query(NodeDevice).filter(NodeDevice.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False) if test_tenant_ids else 0
    del_branding = db.query(SystemBranding).filter(SystemBranding.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False) if test_tenant_ids else 0
    del_audits = db.query(AuditLog).filter(AuditLog.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False) if test_tenant_ids else 0

    # 7. Test Tenant Users (Strictly preserving SUPER_ADMIN)
    del_users = db.query(User).filter(
        User.tenant_id.in_(test_tenant_ids),
        User.role != "SUPER_ADMIN"
    ).delete(synchronize_session=False) if test_tenant_ids else 0

    # 8. Test Tenants
    del_tenants = db.query(Tenant).filter(Tenant.id.in_(test_tenant_ids)).delete(synchronize_session=False) if test_tenant_ids else 0

    # 9. Test Subscription Plans (PRO_*)
    del_plans = db.query(SubscriptionPlan).filter(
        ~SubscriptionPlan.plan_code.in_(STANDARD_PLAN_CODES)
    ).delete(synchronize_session=False)

    # Commit Transaction
    db.commit()

    print("\n [OK] Transaction Successfully Committed!")
    print("\n [>] Purged Records Breakdown:")
    print(f"     * Test Tenants:              {del_tenants}")
    print(f"     * Test Users:                {del_users}")
    print(f"     * Student Profiles:          {del_students}")
    print(f"     * Attendance Records:        {del_attendance}")
    print(f"     * Face Vectors:              {del_encodings}")
    print(f"     * Academic Structure:        {del_depts} Depts, {del_classes} Classes, {del_divisions} Divs, {del_years} Years")
    print(f"     * Faculty Assignments:       {del_assignments}")
    print(f"     * Batch Upload Logs:         {del_batch_uploads}")
    print(f"     * Edge Node Devices:         {del_nodes}")
    print(f"     * System Branding Entries:   {del_branding}")
    print(f"     * Leave Subsystem Records:   {del_leave_balances} Balances, {del_leave_requests} Requests, {del_leave_types} Types")
    print(f"     * Audit Trail Logs:          {del_audits}")
    print(f"     * Test Subscription Plans:   {del_plans}")

    # Reload Face Engine memory vector cache if engine is active
    try:
        from src.core.face_engine import face_engine
        face_engine.reload_cache(db)
        print(" [OK] In-Memory Face Vector Cache Reloaded.")
    except Exception as e:
        print(f" [i] Face engine cache reload note: {e}")


def print_active_state(db):
    """
    Prints a formatted summary of the preserved database state.
    """
    remaining_tenants = db.query(Tenant).order_by(Tenant.id.asc()).all()
    super_admins = db.query(User).filter(User.role == "SUPER_ADMIN").all()
    plans = db.query(SubscriptionPlan).all()

    print("\n" + "=" * 78)
    print(" [CURRENT DATABASE STATE] Verified Active Entities:")
    print("=" * 78)
    print(f" Global Super Admins: {len(super_admins)} ({', '.join(u.username for u in super_admins)})")
    print(f" Total Active Tenants: {len(remaining_tenants)}")
    print(f"{'ID':<5} | {'Slug':<20} | {'Name':<30} | {'Type':<12} | {'Users':<6} | {'Students':<8} | {'Encodings':<10} | {'Logs':<6}")
    print("-" * 105)

    for t in remaining_tenants:
        u_cnt = db.query(User).filter(User.tenant_id == t.id).count()
        s_cnt = db.query(Student).filter(Student.tenant_id == t.id).count()
        f_cnt = db.query(FaceEncoding).filter(FaceEncoding.tenant_id == t.id).count()
        a_cnt = db.query(AttendanceRecord).filter(AttendanceRecord.tenant_id == t.id).count()
        print(f"{t.id:<5} | {t.slug:<20} | {t.name:<30} | {t.tenant_type:<12} | {u_cnt:<6} | {s_cnt:<8} | {f_cnt:<10} | {a_cnt:<6}")

    print("\n Standard Subscription Plans:")
    for p in plans:
        print(f"  - [{p.plan_code}] {p.name} (Max Encodings: {p.max_face_encodings}, Max Nodes: {p.max_nodes})")
    print("=" * 78 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Purge test records and tenants while preserving core entities.")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Simulate cleanup and print targeted records without making changes.")
    parser.add_argument("--execute", action="store_true", default=False, help="Execute full database cleanup and data purge.")
    parser.add_argument("--clean-orphan-files", action="store_true", default=False, help="Audit and delete orphan images from filesystem.")
    args = parser.parse_args()

    # Default to dry-run if neither --execute nor --dry-run is passed
    is_dry_run = not args.execute

    print("\n" + "=" * 78)
    print(" [DATABASE CLEANUP & TENANT PURGE UTILITY]")
    print(f" Mode: {'DRY RUN (Analysis Only - No Changes)' if is_dry_run else 'LIVE EXECUTION (Modifications Will Be Committed)'}")
    print("=" * 78)

    with get_db_context() as db:
        # 1. Audit core vs test data
        audit_data = audit_entities(db)

        print("\n [1] Core Whitelist Verification:")
        for t in audit_data["core_tenants"]:
            print(f"     [+] Protected: ID #{t['id']:<4} | Slug: '{t['slug']:<18}' | Name: '{t['name']}' ({t['type']})")

        print(f"\n [2] Targeted Test Data Scope:")
        print(f"     * Test Tenants to Delete:         {audit_data['test_tenants_count']}")
        print(f"     * Test Users to Delete:           {audit_data['test_users_count']}")
        print(f"     * Test Subscription Plans:        {audit_data['test_plans_count']} ({', '.join(audit_data['test_plans'][:5])}{'...' if len(audit_data['test_plans']) > 5 else ''})")
        print(f"     * Associated Child Records:       {sum(audit_data['child_counts'].values())} total rows across 16 tables")
        for k, v in audit_data["child_counts"].items():
            if v > 0:
                print(f"       - {k:<25}: {v} rows")

        # 2. Handle Filesystem Audit
        clean_orphan_files(db, execute=(not is_dry_run and args.clean_orphan_files))

        if is_dry_run:
            print("\n [!] DRY RUN COMPLETE: 0 database changes made.")
            print(" [>] To execute cleanup with automatic backup, run:")
            print("     python scripts/cleanup_test_data.py --execute")
            print("     python scripts/cleanup_test_data.py --execute --clean-orphan-files\n")
            return

        # 3. Create Automated Backup
        create_database_backup()

        # 4. Execute Purge
        execute_purge(db, audit_data)

    # 5. Print Final State
    with get_db_context() as db:
        print_active_state(db)


if __name__ == "__main__":
    main()
