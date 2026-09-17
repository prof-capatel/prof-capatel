"""
Database Test Data Purge Script
Safely purges transient test tenants and records generated during unit tests,
while strictly preserving enrolled employee and student profiles under
whitelisted tenants: ['default', 'pulin1', 'ssec', 'gecm', 'raymond-store-1'].
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.database.session import get_db
from src.database.models import (
    Tenant,
    Student,
    AttendanceRecord,
    NodeDevice,
    User,
    AuditLog,
    SystemBranding,
    ClassModel,
    Division,
    AcademicYear,
    TeacherClassAssignment,
    StudentBatchUpload,
    LeaveBalance,
    LeaveRequest,
    LeaveType,
    WorkShift,
)

def purge_test_data():
    db = next(get_db())
    whitelist = ['default', 'pulin1', 'ssec', 'gecm', 'raymond-store-1']
    
    test_tenants = db.query(Tenant).filter(~Tenant.slug.in_(whitelist)).all()
    test_tenant_ids = [t.id for t in test_tenants]
    print(f"Purging {len(test_tenant_ids)} test tenants: {test_tenant_ids}")

    # 1. Attendance records under test tenants
    deleted_att = db.query(AttendanceRecord).filter(AttendanceRecord.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False)
    print(f"Deleted {deleted_att} attendance records for test tenants.")

    # 2. Test students created during test runs
    test_students = db.query(Student).filter(
        (Student.tenant_id.in_(test_tenant_ids)) | 
        (Student.roll_number.like('FACULTY-%')) | 
        (Student.roll_number.like('EMP-%')) | 
        (Student.roll_number.like('TEST-ROLL-%')) | 
        (Student.roll_number.like('SHARED-ROLL-%'))
    ).all()
    test_student_ids = [s.id for s in test_students]
    print(f"Purging {len(test_student_ids)} test students: {test_student_ids}")

    if test_student_ids:
        db.query(AttendanceRecord).filter(AttendanceRecord.student_id.in_(test_student_ids)).delete(synchronize_session=False)
        db.query(LeaveRequest).filter(LeaveRequest.student_id.in_(test_student_ids)).delete(synchronize_session=False)
        db.query(LeaveBalance).filter(LeaveBalance.student_id.in_(test_student_ids)).delete(synchronize_session=False)
        db.query(Student).filter(Student.id.in_(test_student_ids)).delete(synchronize_session=False)

    # 3. Purge other test tenant entities
    if test_tenant_ids:
        db.query(TeacherClassAssignment).filter(TeacherClassAssignment.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False)
        db.query(Division).filter(Division.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False)
        db.query(ClassModel).filter(ClassModel.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False)
        db.query(AcademicYear).filter(AcademicYear.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False)
        db.query(NodeDevice).filter(NodeDevice.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False)
        db.query(User).filter(User.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False)
        db.query(SystemBranding).filter(SystemBranding.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False)
        db.query(AuditLog).filter(AuditLog.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False)
        db.query(StudentBatchUpload).filter(StudentBatchUpload.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False)
        db.query(LeaveType).filter(LeaveType.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False)
        db.query(WorkShift).filter(WorkShift.tenant_id.in_(test_tenant_ids)).delete(synchronize_session=False)

    # Purge transient test nodes in tenant 1 if any
    db.query(NodeDevice).filter(NodeDevice.node_id.in_(['NODE-TEST-101', 'NODE-TEST-INGEST'])).delete(synchronize_session=False)
    db.query(User).filter(User.username.like('a.turing_%')).delete(synchronize_session=False)

    # 4. Delete test tenants
    if test_tenant_ids:
        db.query(Tenant).filter(Tenant.id.in_(test_tenant_ids)).delete(synchronize_session=False)

    db.commit()
    print("Database test purge completed successfully.")

if __name__ == '__main__':
    purge_test_data()
