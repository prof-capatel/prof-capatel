"""
==============================================================================
Face Recognition Attendance System - Database Cleanup & Tenant Purge Script
==============================================================================
Purges all ephemeral test tenants, associated users, face embeddings, and logs,
while strictly preserving core entities:
  - Tenant #1: Antigravity HQ Campus (slug: default)
  - Tenant #106: pulin1 (slug: pulin1)
  - Tenant #115: SSEC (slug: ssec)
  - Tenant #155: GECM (slug: gecm)
  - Global Super Admin: superadmin (tenant_id is NULL)

Also standardizes core tenant branding to new system defaults:
  - Theme: Warm Academic (primary_accent_color = '#c2410c')
  - Anti-Spoofing & Liveness Check: OFF (enable_anti_spoofing = False, liveness_mode = 'off')
  - Self-Attendance & Geofencing: OFF (enable_self_attendance = False)
==============================================================================
"""

import os
import sys
from pathlib import Path

# Add project root to path
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
)
from src.core.face_engine import face_engine


PRESERVED_TENANT_SPECS = [
    {"id": 1, "slug": "default", "name": "Antigravity HQ Campus"},
    {"id": 106, "slug": "pulin1", "name": "pulin1"},
    {"id": 115, "slug": "ssec", "name": "SSEC"},
    {"id": 155, "slug": "gecm", "name": "GECM"},
    {"id": 292, "slug": "raymond-store-1", "name": "Raymond Store 1"},
]


def run_database_cleanup():
    print("\n" + "=" * 78)
    print(" [DATABASE CLEANUP] Starting Safe Test Tenant Purge & Configuration Sync")
    print("=" * 78)

    with get_db_context() as db:
        # 1. Identify preserved tenant IDs
        preserved_ids = set()
        for spec in PRESERVED_TENANT_SPECS:
            tenant = None
            if "id" in spec:
                tenant = db.query(Tenant).filter(Tenant.id == spec["id"]).first()
            if not tenant and "slug" in spec:
                tenant = db.query(Tenant).filter(Tenant.slug == spec["slug"]).first()
            if not tenant and "name" in spec:
                tenant = db.query(Tenant).filter(Tenant.name.ilike(f"%{spec['name']}%")).first()

            if tenant:
                preserved_ids.add(tenant.id)
                print(f" [+] Verified Core Preserved Tenant: ID #{tenant.id} | Slug: '{tenant.slug}' | Name: '{tenant.name}'")
            else:
                print(f" [!] Warning: Spec {spec} not found in database by ID or Slug.")

        if not preserved_ids:
            print(" [X] Error: No core tenants identified. Aborting for safety!")
            return

        print(f"\n [*] Total Core Tenants Preserved: {len(preserved_ids)} (IDs: {sorted(list(preserved_ids))})")

        # 2. Query test tenants to be purged
        test_tenants = db.query(Tenant).filter(~Tenant.id.in_(preserved_ids)).all()
        test_tenant_ids = [t.id for t in test_tenants]
        print(f" [*] Identified {len(test_tenant_ids)} Test Tenants to be purged.")

        if test_tenant_ids:
            # 3. Cascading Child Records Deletion
            del_attendances = db.query(AttendanceRecord).filter(AttendanceRecord.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False)
            del_encodings = db.query(FaceEncoding).filter(FaceEncoding.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False)
            del_batch_uploads = db.query(StudentBatchUpload).filter(StudentBatchUpload.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False)
            del_assignments = db.query(TeacherClassAssignment).filter(TeacherClassAssignment.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False)
            del_students = db.query(Student).filter(Student.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False)
            del_divisions = db.query(Division).filter(Division.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False)
            del_classes = db.query(ClassModel).filter(ClassModel.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False)
            del_years = db.query(AcademicYear).filter(AcademicYear.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False)
            del_depts = db.query(Department).filter(Department.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False)
            del_nodes = db.query(NodeDevice).filter(NodeDevice.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False)
            del_branding = db.query(SystemBranding).filter(SystemBranding.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False)
            del_audits = db.query(AuditLog).filter(AuditLog.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False)
            
            # Delete tenant users, strictly preserving global SUPER_ADMIN
            del_users = db.query(User).filter(
                User.tenant_id.in_(test_tenant_ids),
                User.role != "SUPER_ADMIN",
            ).delete(synchronize_session=False)

            # Finally, delete test tenants
            del_tenants = db.query(Tenant).filter(Tenant.id.in_(test_tenant_ids)).delete(synchronize_session=False)

            print("\n [>] Purge Summary:")
            print(f"     - Test Tenants Purged:     {del_tenants}")
            print(f"     - Tenant Users Purged:     {del_users}")
            print(f"     - Student Profiles Purged: {del_students}")
            print(f"     - Face Vectors Purged:     {del_encodings}")
            print(f"     - Attendance Logs Purged:  {del_attendances}")
            print(f"     - Edge Nodes Purged:       {del_nodes}")
            print(f"     - Academic Hierarchy:      {del_depts} Depts, {del_classes} Classes, {del_divisions} Divs")
            print(f"     - System Branding Purged:  {del_branding}")
            print(f"     - Audit Trail Logs Purged: {del_audits}")
        else:
            print(" [*] Database is already clean. No test tenants found.")

        # 4. Standardize Core Tenants Branding Configuration
        print("\n [*] Standardizing Branding Configuration for Preserved Core Tenants...")
        for cid in preserved_ids:
            branding = db.query(SystemBranding).filter(SystemBranding.tenant_id == cid).first()
            tenant = db.query(Tenant).filter(Tenant.id == cid).first()
            t_name = tenant.name if tenant else f"Tenant #{cid}"

            if not branding:
                branding = SystemBranding(
                    tenant_id=cid,
                    institution_name=t_name,
                    short_code=tenant.slug.upper()[:10] if tenant else "HUB",
                    primary_accent_color="#c2410c",
                    enable_anti_spoofing=False,
                    liveness_mode="off",
                    enable_self_attendance=False,
                )
                db.add(branding)
                print(f"     + Created Default Branding for {t_name} (Warm Academic #c2410c, Anti-Spoofing OFF, Self-Attendance OFF)")
            else:
                branding.primary_accent_color = "#c2410c"
                branding.enable_anti_spoofing = False
                branding.liveness_mode = "off"
                branding.enable_self_attendance = False
                print(f"     [OK] Updated Branding for {t_name} (Warm Academic #c2410c, Anti-Spoofing OFF, Self-Attendance OFF)")

        # 5. Commit all database changes
        db.commit()
        print("\n [OK] Database Transaction Committed Successfully.")

        # 6. Flush and resync in-memory Face Recognition Vector Engine
        try:
            face_engine.reload_cache(db)
            print(" [OK] In-Memory Face Engine Encodings Resynchronized.")
        except Exception as e:
            print(f" [!] Note: Face engine memory cache reload: {e}")

    # 7. Final Verification of Active Database State
    with get_db_context() as db:
        remaining_tenants = db.query(Tenant).order_by(Tenant.id.asc()).all()
        super_admins = db.query(User).filter(User.role == "SUPER_ADMIN").all()

        print("\n" + "=" * 78)
        print(" [CLEANUP COMPLETE] Current Active Database Entities:")
        print("=" * 78)
        print(f" Global Super Admins: {len(super_admins)} ({', '.join(u.username for u in super_admins)})")
        print(f" Total Remaining Tenants: {len(remaining_tenants)}")
        for t in remaining_tenants:
            b = db.query(SystemBranding).filter(SystemBranding.tenant_id == t.id).first()
            color = b.primary_accent_color if b else "N/A"
            spoof = "ENABLED" if (b and b.enable_anti_spoofing) else "DISABLED"
            self_att = "ENABLED" if (b and b.enable_self_attendance) else "DISABLED"
            u_count = db.query(User).filter(User.tenant_id == t.id).count()
            s_count = db.query(Student).filter(Student.tenant_id == t.id).count()
            print(f"  * Tenant #{t.id:3d} [{t.slug:10s}] '{t.name}': Users={u_count}, Profiles={s_count} | Theme Color={color} | Anti-Spoof={spoof} | Self-Attendance={self_att}")
        print("=" * 78 + "\n")


if __name__ == "__main__":
    run_database_cleanup()
