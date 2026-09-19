import logging
import uuid
import secrets
from contextlib import contextmanager
import pymysql
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from src.config import (
    DATABASE_URL,
    MYSQL_HOST,
    MYSQL_PORT,
    MYSQL_USER,
    MYSQL_PASSWORD,
    MYSQL_DB,
    DEFAULT_TENANT_ID,
    DEFAULT_TENANT_SLUG,
)
from src.database.models import (
    Base,
    Tenant,
    Department,
    SystemBranding,
    User,
    AcademicYear,
    ClassModel,
    Division,
    TeacherClassAssignment,
    Student,
    SubscriptionPlan,
    LeaveType,
    LeaveBalance,
    LeaveRequest,
    CompanyLocation,
    DesignationMaster,
    SalaryComponent,
    SalaryTemplate,
    EmployeeSalaryStructure,
    SalaryRevisionHistory,
    PayrollBatch,
    PayrollPayslip,
)
from src.utils.auth_utils import hash_password

logger = logging.getLogger("db_session")
logger.setLevel(logging.INFO)


def ensure_mysql_database_exists():
    """
    Connects to MySQL server without database selected and runs
    CREATE DATABASE IF NOT EXISTS to guarantee target database exists.
    """
    try:
        conn = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            charset="utf8mb4",
        )
        with conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{MYSQL_DB}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
            )
        conn.commit()
        conn.close()
        logger.info(f"MySQL database '{MYSQL_DB}' confirmed on {MYSQL_HOST}:{MYSQL_PORT}.")
    except Exception as e:
        logger.error(f"Failed to ensure MySQL database '{MYSQL_DB}': {e}")
        raise


# Ensure database exists before creating SQLAlchemy engine
ensure_mysql_database_exists()

# MySQL engine with connection pooling, recycling, and pre-ping health check
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_default_subscription_plans(db: Session):
    """Seeds default standard SaaS subscription plans if not existing."""
    default_plans = [
        {
            "plan_code": "BASIC",
            "name": "Basic Edition (Attendance Only)",
            "max_face_encodings": 100,
            "max_nodes": 2,
            "price_monthly": 0.0,
            "description": "Core facial recognition biometric attendance and staff directory management.",
        },
        {
            "plan_code": "SMART",
            "name": "Smart Edition (Attendance + Leaves)",
            "max_face_encodings": 500,
            "max_nodes": 10,
            "price_monthly": 29.0,
            "description": "Biometric attendance, multi-shift scheduling, and complete statutory leave management.",
        },
        {
            "plan_code": "PRO",
            "name": "Pro Edition (Full Platform)",
            "max_face_encodings": 5000,
            "max_nodes": 50,
            "price_monthly": 79.0,
            "description": "Full enterprise suite with attendance, leaves, and Indian statutory payroll & CTC.",
        },
        {
            "plan_code": "FREE",
            "name": "Starter Free Tier",
            "max_face_encodings": 50,
            "max_nodes": 2,
            "price_monthly": 0.0,
            "description": "Evaluation tier for small pilot deployments and trial classrooms.",
        },
        {
            "plan_code": "STANDARD",
            "name": "Standard Campus Tier",
            "max_face_encodings": 500,
            "max_nodes": 10,
            "price_monthly": 49.0,
            "description": "Comprehensive biometric attendance for schools and single departments.",
        },
        {
            "plan_code": "ENTERPRISE",
            "name": "Enterprise Multi-Campus",
            "max_face_encodings": 5000,
            "max_nodes": 50,
            "price_monthly": 199.0,
            "description": "High-throughput cluster with unlimited departments and multi-node capture.",
        },
    ]

    for p in default_plans:
        existing = db.query(SubscriptionPlan).filter(SubscriptionPlan.plan_code == p["plan_code"]).first()
        if not existing:
            new_plan = SubscriptionPlan(
                plan_code=p["plan_code"],
                name=p["name"],
                max_face_encodings=p["max_face_encodings"],
                max_nodes=p["max_nodes"],
                price_monthly=p["price_monthly"],
                description=p["description"],
                is_active=True,
            )
            db.add(new_plan)
            logger.info(f"Seeded SubscriptionPlan '{p['plan_code']}'.")
    db.flush()


def seed_default_leave_types(db: Session, tenant_id: int):
    """Seeds default leave master categories (CL, SL, EL, LWP) for a tenant if none exist."""
    existing = db.query(LeaveType).filter(LeaveType.tenant_id == tenant_id).first()
    if not existing:
        defaults = [
            {
                "name": "Casual Leave",
                "code": "CL",
                "description": "Short-term personal emergency or casual leave.",
                "is_paid": True,
                "default_days_per_year": 12.0,
                "accrual_frequency": "ANNUAL",
                "requires_document": False,
            },
            {
                "name": "Medical / Sick Leave",
                "code": "SL",
                "description": "Medical recuperation and sick leave.",
                "is_paid": True,
                "default_days_per_year": 10.0,
                "accrual_frequency": "ANNUAL",
                "requires_document": False,
            },
            {
                "name": "Earned / Annual Leave",
                "code": "EL",
                "description": "Annual earned vacation leave.",
                "is_paid": True,
                "default_days_per_year": 15.0,
                "accrual_frequency": "ANNUAL",
                "requires_document": False,
            },
            {
                "name": "Leave Without Pay",
                "code": "LWP",
                "description": "Unpaid extended leave.",
                "is_paid": False,
                "default_days_per_year": 0.0,
                "accrual_frequency": "ANNUAL",
                "requires_document": False,
            },
        ]
        for item in defaults:
            lt = LeaveType(
                tenant_id=tenant_id,
                name=item["name"],
                code=item["code"],
                description=item["description"],
                is_paid=item["is_paid"],
                default_days_per_year=item["default_days_per_year"],
                accrual_frequency=item["accrual_frequency"],
                requires_document=item["requires_document"],
                is_active=True,
            )
            db.add(lt)
        db.flush()
        logger.info(f"Seeded default LeaveTypes for Tenant #{tenant_id}.")


def seed_default_salary_components(db: Session, tenant_id: int):
    """Seeds master Indian salary components (Basic, HRA, DA, PF, ESI, PT, TDS) for tenant."""
    existing = db.query(SalaryComponent).filter(SalaryComponent.tenant_id == tenant_id).first()
    if not existing:
        defaults = [
            {"name": "Basic Pay", "code": "BASIC", "component_type": "EARNING", "calculation_type": "PERCENTAGE_GROSS", "default_value": 50.0, "is_taxable": True, "is_statutory": False},
            {"name": "House Rent Allowance", "code": "HRA", "component_type": "EARNING", "calculation_type": "PERCENTAGE_BASIC", "default_value": 40.0, "is_taxable": True, "is_statutory": False},
            {"name": "Dearness Allowance", "code": "DA", "component_type": "EARNING", "calculation_type": "PERCENTAGE_BASIC", "default_value": 0.0, "is_taxable": True, "is_statutory": False},
            {"name": "Conveyance Allowance", "code": "CONVEYANCE", "component_type": "EARNING", "calculation_type": "FIXED", "default_value": 1600.0, "is_taxable": True, "is_statutory": False},
            {"name": "Medical Allowance", "code": "MEDICAL", "component_type": "EARNING", "calculation_type": "FIXED", "default_value": 1250.0, "is_taxable": True, "is_statutory": False},
            {"name": "Special Allowance", "code": "SPECIAL_ALLOWANCE", "component_type": "EARNING", "calculation_type": "FIXED", "default_value": 0.0, "is_taxable": True, "is_statutory": False},
            {"name": "Performance Incentive / Bonus", "code": "BONUS_INCENTIVE", "component_type": "EARNING", "calculation_type": "FIXED", "default_value": 0.0, "is_taxable": True, "is_statutory": False},
            {"name": "Employee Provident Fund (EPF)", "code": "EPF_EMPLOYEE", "component_type": "STATUTORY_EMPLOYEE", "calculation_type": "PERCENTAGE_BASIC", "default_value": 12.0, "is_taxable": False, "is_statutory": True},
            {"name": "Employer PF Contribution (EPF/EPS)", "code": "EPF_EMPLOYER", "component_type": "STATUTORY_EMPLOYER", "calculation_type": "PERCENTAGE_BASIC", "default_value": 12.0, "is_taxable": False, "is_statutory": True},
            {"name": "Employee State Insurance (ESIC)", "code": "ESIC_EMPLOYEE", "component_type": "STATUTORY_EMPLOYEE", "calculation_type": "PERCENTAGE_GROSS", "default_value": 0.75, "is_taxable": False, "is_statutory": True},
            {"name": "Employer State Insurance (ESIC)", "code": "ESIC_EMPLOYER", "component_type": "STATUTORY_EMPLOYER", "calculation_type": "PERCENTAGE_GROSS", "default_value": 3.25, "is_taxable": False, "is_statutory": True},
            {"name": "Professional Tax (PT)", "code": "PROFESSIONAL_TAX", "component_type": "STATUTORY_EMPLOYEE", "calculation_type": "FIXED", "default_value": 200.0, "is_taxable": False, "is_statutory": True},
            {"name": "Tax Deducted at Source (TDS)", "code": "TDS", "component_type": "DEDUCTION", "calculation_type": "FIXED", "default_value": 0.0, "is_taxable": False, "is_statutory": True},
            {"name": "Loan & Salary Advance Recovery", "code": "LOAN_ADVANCE", "component_type": "DEDUCTION", "calculation_type": "FIXED", "default_value": 0.0, "is_taxable": False, "is_statutory": False},
        ]
        for c in defaults:
            sc = SalaryComponent(
                tenant_id=tenant_id,
                name=c["name"],
                code=c["code"],
                component_type=c["component_type"],
                calculation_type=c["calculation_type"],
                default_value=c["default_value"],
                is_taxable=c["is_taxable"],
                is_statutory=c["is_statutory"],
                is_active=True,
            )
            db.add(sc)
        db.flush()
        logger.info(f"Seeded default SalaryComponents for Tenant #{tenant_id}.")


def seed_default_salary_templates(db: Session, tenant_id: int):
    """Seeds default reusable Salary Templates for tenant."""
    existing = db.query(SalaryTemplate).filter(SalaryTemplate.tenant_id == tenant_id).first()
    if not existing:
        templates = [
            {
                "name": "Executive Structured CTC",
                "code": "EXEC_STD",
                "compensation_model": "STRUCTURED_SALARY",
                "description": "Standard corporate structured package: 50% Basic, 20% HRA, statutory EPF (12%), ESIC, and PT.",
                "basic_percentage": 50.0,
                "hra_percentage": 20.0,
                "da_percentage": 0.0,
                "conveyance_fixed": 1600.0,
                "medical_fixed": 1250.0,
                "enable_pf": True,
                "pf_capped_at_ceiling": True,
                "enable_esi": True,
                "enable_pt": True,
            },
            {
                "name": "Monthly Fixed Base Pay",
                "code": "MONTHLY_FIXED",
                "compensation_model": "MONTHLY_FIXED",
                "description": "Monthly base compensation pro-rated by working days with overtime multiplier.",
                "basic_percentage": 60.0,
                "hra_percentage": 20.0,
                "da_percentage": 0.0,
                "conveyance_fixed": 0.0,
                "medical_fixed": 0.0,
                "enable_pf": True,
                "pf_capped_at_ceiling": True,
                "enable_esi": True,
                "enable_pt": True,
            },
            {
                "name": "Hourly Operations Worker",
                "code": "HOURLY_OPS",
                "compensation_model": "HOURLY",
                "description": "Wage computed directly by tracked biometric hours worked and overtime multiplier.",
                "basic_percentage": 100.0,
                "hra_percentage": 0.0,
                "da_percentage": 0.0,
                "conveyance_fixed": 0.0,
                "medical_fixed": 0.0,
                "enable_pf": False,
                "pf_capped_at_ceiling": True,
                "enable_esi": True,
                "enable_pt": True,
            },
            {
                "name": "Graduate Trainee / Intern Stipend",
                "code": "INTERN_STIPEND",
                "compensation_model": "STIPEND",
                "description": "Fixed monthly intern stipend pro-rated for unpaid leaves with zero PF deduction.",
                "basic_percentage": 100.0,
                "hra_percentage": 0.0,
                "da_percentage": 0.0,
                "conveyance_fixed": 0.0,
                "medical_fixed": 0.0,
                "enable_pf": False,
                "pf_capped_at_ceiling": True,
                "enable_esi": False,
                "enable_pt": False,
            },
        ]
        for t in templates:
            st = SalaryTemplate(
                tenant_id=tenant_id,
                name=t["name"],
                code=t["code"],
                compensation_model=t["compensation_model"],
                description=t["description"],
                basic_percentage=t["basic_percentage"],
                hra_percentage=t["hra_percentage"],
                da_percentage=t["da_percentage"],
                conveyance_fixed=t["conveyance_fixed"],
                medical_fixed=t["medical_fixed"],
                enable_pf=t["enable_pf"],
                pf_capped_at_ceiling=t["pf_capped_at_ceiling"],
                enable_esi=t["enable_esi"],
                enable_pt=t["enable_pt"],
                is_active=True,
            )
            db.add(st)
        db.flush()
        logger.info(f"Seeded default SalaryTemplates for Tenant #{tenant_id}.")


def seed_default_locations_and_designations(db: Session, tenant_id: int):
    """Seeds default branch location and designations for corporate tenant."""
    existing_loc = db.query(CompanyLocation).filter(CompanyLocation.tenant_id == tenant_id).first()
    if not existing_loc:
        loc = CompanyLocation(
            tenant_id=tenant_id,
            name="Main Corporate Office",
            code="CORP-HQ",
            city="Mumbai",
            state="Maharashtra",
            address="BKC Financial Hub, Bandra East, Mumbai, Maharashtra 400051",
            contact_number="+91 22 2650 0000",
            is_active=True,
        )
        db.add(loc)
        logger.info(f"Seeded default CompanyLocation for Tenant #{tenant_id}.")

    existing_desig = db.query(DesignationMaster).filter(DesignationMaster.tenant_id == tenant_id).first()
    if not existing_desig:
        exec_tpl = db.query(SalaryTemplate).filter(SalaryTemplate.tenant_id == tenant_id, SalaryTemplate.code == "EXEC_STD").first()
        fixed_tpl = db.query(SalaryTemplate).filter(SalaryTemplate.tenant_id == tenant_id, SalaryTemplate.code == "MONTHLY_FIXED").first()

        desigs = [
            {"title": "Senior Software Engineer", "code": "SSE", "salary_template_id": exec_tpl.id if exec_tpl else None, "description": "Lead software development and platform architecture."},
            {"title": "Associate Engineer", "code": "ASE", "salary_template_id": fixed_tpl.id if fixed_tpl else None, "description": "Core engineering delivery and maintenance."},
            {"title": "Project Lead / Manager", "code": "PLM", "salary_template_id": exec_tpl.id if exec_tpl else None, "description": "Operations and project delivery oversight."},
            {"title": "Business Operations Executive", "code": "BOE", "salary_template_id": fixed_tpl.id if fixed_tpl else None, "description": "Corporate operations, logistics, and administration."},
        ]
        for d in desigs:
            dm = DesignationMaster(
                tenant_id=tenant_id,
                title=d["title"],
                code=d["code"],
                salary_template_id=d["salary_template_id"],
                description=d["description"],
                is_active=True,
            )
            db.add(dm)
        logger.info(f"Seeded default Designations for Tenant #{tenant_id}.")
    db.flush()


def seed_default_tenant_and_branding():
    """Seeds default tenant, branding, RBAC users, and academic structure if database is fresh."""
    with SessionLocal() as db:
        try:
            # 0. Subscription Plans
            seed_default_subscription_plans(db)
            seed_default_leave_types(db, DEFAULT_TENANT_ID)
            seed_default_salary_components(db, DEFAULT_TENANT_ID)
            seed_default_salary_templates(db, DEFAULT_TENANT_ID)
            seed_default_locations_and_designations(db, DEFAULT_TENANT_ID)

            # 1. Default Tenant
            default_tenant = db.query(Tenant).filter(Tenant.id == DEFAULT_TENANT_ID).first()
            if not default_tenant:
                default_tenant = Tenant(
                    id=DEFAULT_TENANT_ID,
                    uuid=str(uuid.uuid4()),
                    slug=DEFAULT_TENANT_SLUG,
                    name="FaceAttendance Campus",
                    contact_email="admin@campus.edu",
                    is_active=True,
                    subscription_plan="ENTERPRISE",
                    subscription_status="ACTIVE",
                    max_face_encodings=5000,
                    max_nodes=50,
                    admin_token=secrets.token_urlsafe(32),
                    onboarding_token=secrets.token_urlsafe(32),
                    attendance_slug=secrets.token_urlsafe(24),
                )
                db.add(default_tenant)
                db.flush()
                logger.info(f"Seeded default Tenant #{DEFAULT_TENANT_ID} ('{DEFAULT_TENANT_SLUG}').")
            else:
                updated = False
                if not default_tenant.uuid:
                    default_tenant.uuid = str(uuid.uuid4())
                    updated = True
                if not default_tenant.admin_token:
                    default_tenant.admin_token = secrets.token_urlsafe(32)
                    updated = True
                if not default_tenant.onboarding_token:
                    default_tenant.onboarding_token = secrets.token_urlsafe(32)
                    updated = True
                if not default_tenant.attendance_slug:
                    default_tenant.attendance_slug = secrets.token_urlsafe(24)
                    updated = True
                if updated:
                    db.flush()

            # 2. Default Branding (Warm Academic, Anti-Spoofing OFF, Self-Attendance OFF)
            branding = db.query(SystemBranding).filter(SystemBranding.tenant_id == DEFAULT_TENANT_ID).first()
            if not branding:
                branding = SystemBranding(
                    tenant_id=DEFAULT_TENANT_ID,
                    institution_name="FaceAttendance Campus",
                    short_code="FA-HUB",
                    tagline="Raspberry Pi Zero Edge Nodes & Central Face Recognition",
                    primary_accent_color="#c2410c",
                    header_badge_text="Thin-Client Hub",
                    cooldown_minutes=60,
                    enable_anti_spoofing=False,
                    liveness_mode="off",
                    enable_self_attendance=False,
                )
                db.add(branding)
                logger.info(f"Seeded default SystemBranding for Tenant #{DEFAULT_TENANT_ID}.")

            # 3. Seed Default RBAC Users
            # Super Admin (Global scope, tenant_id=None)
            super_admin = db.query(User).filter(User.role == "SUPER_ADMIN").first()
            if not super_admin:
                super_admin = User(
                    tenant_id=None,
                    username="superadmin",
                    email="superadmin@platform.cloud",
                    password_hash=hash_password("admin123"),
                    role="SUPER_ADMIN",
                    full_name="Global Super Administrator",
                    is_active=True,
                )
                db.add(super_admin)
                logger.info("Seeded default SUPER_ADMIN user ('superadmin').")

            # Tenant Admin (Tenant #1)
            tenant_admin = db.query(User).filter(User.tenant_id == DEFAULT_TENANT_ID, User.role == "TENANT_ADMIN").first()
            if not tenant_admin:
                tenant_admin = User(
                    tenant_id=DEFAULT_TENANT_ID,
                    username="admin",
                    email="dean@campus.edu",
                    password_hash=hash_password("admin123"),
                    role="TENANT_ADMIN",
                    full_name="Campus Dean / Principal",
                    is_active=True,
                )
                db.add(tenant_admin)
                logger.info("Seeded default TENANT_ADMIN user ('admin').")

            # Teacher User (Tenant #1)
            teacher_user = db.query(User).filter(User.tenant_id == DEFAULT_TENANT_ID, User.role == "TEACHER").first()
            if not teacher_user:
                teacher_user = User(
                    tenant_id=DEFAULT_TENANT_ID,
                    username="teacher1",
                    email="s.jenkins@campus.edu",
                    password_hash=hash_password("teacher123"),
                    role="TEACHER",
                    full_name="Prof. Sarah Jenkins",
                    is_active=True,
                )
                db.add(teacher_user)
                db.flush()
                logger.info("Seeded default TEACHER user ('teacher1').")

            # Student User (Tenant #1)
            student_user = db.query(User).filter(User.tenant_id == DEFAULT_TENANT_ID, User.role == "STUDENT").first()
            if not student_user:
                student_user = User(
                    tenant_id=DEFAULT_TENANT_ID,
                    username="student1",
                    email="chirag@student.campus.edu",
                    password_hash=hash_password("student123"),
                    role="STUDENT",
                    full_name="Chirag Patel",
                    is_active=True,
                )
                db.add(student_user)
                logger.info("Seeded default STUDENT user ('student1').")

            # 4. Seed Academic Hierarchy (Departments, Years, Classes, Divisions)
            # Default Departments
            default_departments_data = [
                {"name": "Computer Science", "code": "CS", "description": "Department of Computer Science & Engineering"},
                {"name": "Information Technology", "code": "IT", "description": "Department of Information Technology"},
                {"name": "Artificial Intelligence & Data Science", "code": "AI-DS", "description": "Department of Artificial Intelligence & Data Science"},
                {"name": "Electronics & Communication", "code": "ECE", "description": "Department of Electronics & Communication"},
                {"name": "Mechanical Engineering", "code": "MECH", "description": "Department of Mechanical Engineering"},
                {"name": "Administration", "code": "ADMIN", "description": "Administrative & Institutional Staff"},
            ]
            seeded_departments = {}
            for d_data in default_departments_data:
                dept_obj = db.query(Department).filter(
                    Department.tenant_id == DEFAULT_TENANT_ID,
                    Department.name == d_data["name"]
                ).first()
                if not dept_obj:
                    dept_obj = Department(
                        tenant_id=DEFAULT_TENANT_ID,
                        name=d_data["name"],
                        code=d_data["code"],
                        description=d_data["description"],
                    )
                    db.add(dept_obj)
                    db.flush()
                    logger.info(f"Seeded default Department '{d_data['name']}'.")
                seeded_departments[d_data["name"]] = dept_obj

            cs_dept = seeded_departments.get("Computer Science")
            cs_dept_id = cs_dept.id if cs_dept else None

            # Academic Year
            acad_year = db.query(AcademicYear).filter(AcademicYear.tenant_id == DEFAULT_TENANT_ID, AcademicYear.name == "2026-2027").first()
            if not acad_year:
                acad_year = AcademicYear(
                    tenant_id=DEFAULT_TENANT_ID,
                    name="2026-2027",
                    is_current=True,
                    start_date="2026-07-01",
                    end_date="2027-06-30",
                )
                db.add(acad_year)
                db.flush()
                logger.info("Seeded default AcademicYear '2026-2027'.")

            # Classes
            class_fy = db.query(ClassModel).filter(ClassModel.tenant_id == DEFAULT_TENANT_ID, ClassModel.name == "FY Computer Science").first()
            if not class_fy:
                class_fy = ClassModel(
                    tenant_id=DEFAULT_TENANT_ID,
                    department_id=cs_dept_id,
                    department="Computer Science",
                    name="FY Computer Science",
                    code="FY-CS",
                )
                db.add(class_fy)
                db.flush()
            elif class_fy.department_id is None and cs_dept_id:
                class_fy.department_id = cs_dept_id

            class_sy = db.query(ClassModel).filter(ClassModel.tenant_id == DEFAULT_TENANT_ID, ClassModel.name == "SY Computer Science").first()
            if not class_sy:
                class_sy = ClassModel(
                    tenant_id=DEFAULT_TENANT_ID,
                    department_id=cs_dept_id,
                    department="Computer Science",
                    name="SY Computer Science",
                    code="SY-CS",
                )
                db.add(class_sy)
                db.flush()
            elif class_sy.department_id is None and cs_dept_id:
                class_sy.department_id = cs_dept_id

            class_ty = db.query(ClassModel).filter(ClassModel.tenant_id == DEFAULT_TENANT_ID, ClassModel.name == "TY Computer Science").first()
            if not class_ty:
                class_ty = ClassModel(
                    tenant_id=DEFAULT_TENANT_ID,
                    department_id=cs_dept_id,
                    department="Computer Science",
                    name="TY Computer Science",
                    code="TY-CS",
                )
                db.add(class_ty)
                db.flush()
            elif class_ty.department_id is None and cs_dept_id:
                class_ty.department_id = cs_dept_id

            # Divisions for FY
            div_a = db.query(Division).filter(Division.tenant_id == DEFAULT_TENANT_ID, Division.class_id == class_fy.id, Division.name == "Division A").first()
            if not div_a:
                div_a = Division(
                    tenant_id=DEFAULT_TENANT_ID,
                    class_id=class_fy.id,
                    name="Division A",
                )
                db.add(div_a)
                db.flush()

            div_b = db.query(Division).filter(Division.tenant_id == DEFAULT_TENANT_ID, Division.class_id == class_fy.id, Division.name == "Division B").first()
            if not div_b:
                div_b = Division(
                    tenant_id=DEFAULT_TENANT_ID,
                    class_id=class_fy.id,
                    name="Division B",
                )
                db.add(div_b)
                db.flush()

            # Assign teacher1 to FY-CS Division A
            if teacher_user and class_fy:
                existing_assign = db.query(TeacherClassAssignment).filter(
                    TeacherClassAssignment.tenant_id == DEFAULT_TENANT_ID,
                    TeacherClassAssignment.teacher_id == teacher_user.id,
                    TeacherClassAssignment.class_id == class_fy.id,
                ).first()
                if not existing_assign:
                    assignment = TeacherClassAssignment(
                        tenant_id=DEFAULT_TENANT_ID,
                        teacher_id=teacher_user.id,
                        class_id=class_fy.id,
                        division_id=div_a.id if div_a else None,
                        academic_year_id=acad_year.id if acad_year else None,
                        subject="Data Structures & Algorithms",
                    )
                    db.add(assignment)
                    logger.info("Seeded default TeacherClassAssignment for 'teacher1'.")

            # Link existing students and classes to departments and divisions if unassigned
            all_tenant_classes = db.query(ClassModel).filter(ClassModel.tenant_id == DEFAULT_TENANT_ID).all()
            for cls in all_tenant_classes:
                if cls.department_id is None:
                    matched_dept = db.query(Department).filter(
                        Department.tenant_id == DEFAULT_TENANT_ID,
                        Department.name == cls.department
                    ).first()
                    if matched_dept:
                        cls.department_id = matched_dept.id
                    elif cs_dept_id:
                        cls.department_id = cs_dept_id

            all_tenant_students = db.query(Student).filter(Student.tenant_id == DEFAULT_TENANT_ID).all()
            for std in all_tenant_students:
                if std.department_id is None:
                    matched_dept = db.query(Department).filter(
                        Department.tenant_id == DEFAULT_TENANT_ID,
                        Department.name == std.department
                    ).first()
                    if matched_dept:
                        std.department_id = matched_dept.id
                    elif cs_dept_id:
                        std.department_id = cs_dept_id
                        std.department = cs_dept.name

                if std.class_id is None:
                    std.class_id = class_fy.id
                    std.class_semester = class_fy.name
                if std.division_id is None and div_a:
                    std.division_id = div_a.id
                if std.academic_year_id is None and acad_year:
                    std.academic_year_id = acad_year.id

            db.commit()
            logger.info("Database default seeds and referential links completed successfully.")
        except Exception as e:
            db.rollback()
            logger.warning(f"Default seeding note: {e}")


def run_schema_migrations():
    """Checks and adds newly introduced columns to existing MySQL tables."""
    try:
        with engine.begin() as conn:
            # 1. System Branding columns
            res = conn.execute(text("SHOW COLUMNS FROM system_branding LIKE 'cooldown_minutes'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE system_branding ADD COLUMN cooldown_minutes INT DEFAULT 60 NOT NULL"))

            res = conn.execute(text("SHOW COLUMNS FROM system_branding LIKE 'liveness_mode'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE system_branding ADD COLUMN liveness_mode VARCHAR(20) DEFAULT 'BALANCED' NOT NULL"))

            res = conn.execute(text("SHOW COLUMNS FROM system_branding LIKE 'temporal_frames_required'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE system_branding ADD COLUMN temporal_frames_required INT DEFAULT 3 NOT NULL"))

            res = conn.execute(text("SHOW COLUMNS FROM system_branding LIKE 'enable_anti_spoofing'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE system_branding ADD COLUMN enable_anti_spoofing BOOLEAN DEFAULT TRUE NOT NULL"))

            res = conn.execute(text("SHOW COLUMNS FROM system_branding LIKE 'enable_audio_chime'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE system_branding ADD COLUMN enable_audio_chime BOOLEAN DEFAULT TRUE NOT NULL"))

            res = conn.execute(text("SHOW COLUMNS FROM system_branding LIKE 'enable_haptic_feedback'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE system_branding ADD COLUMN enable_haptic_feedback BOOLEAN DEFAULT TRUE NOT NULL"))

            res = conn.execute(text("SHOW COLUMNS FROM system_branding LIKE 'enable_self_attendance'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE system_branding ADD COLUMN enable_self_attendance BOOLEAN DEFAULT FALSE NOT NULL"))
                logger.info("Migrated system_branding table: added enable_self_attendance column.")

            res = conn.execute(text("SHOW COLUMNS FROM system_branding LIKE 'geo_latitude'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE system_branding ADD COLUMN geo_latitude FLOAT NULL"))
                logger.info("Migrated system_branding table: added geo_latitude column.")

            res = conn.execute(text("SHOW COLUMNS FROM system_branding LIKE 'geo_longitude'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE system_branding ADD COLUMN geo_longitude FLOAT NULL"))
                logger.info("Migrated system_branding table: added geo_longitude column.")

            res = conn.execute(text("SHOW COLUMNS FROM system_branding LIKE 'geo_radius_meters'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE system_branding ADD COLUMN geo_radius_meters FLOAT DEFAULT 150.0 NOT NULL"))
                logger.info("Migrated system_branding table: added geo_radius_meters column.")

            res = conn.execute(text("SHOW COLUMNS FROM system_branding LIKE 'max_gps_accuracy_meters'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE system_branding ADD COLUMN max_gps_accuracy_meters FLOAT DEFAULT 50.0 NOT NULL"))
                logger.info("Migrated system_branding table: added max_gps_accuracy_meters column.")

            res = conn.execute(text("SHOW COLUMNS FROM system_branding LIKE 'self_attendance_face_threshold'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE system_branding ADD COLUMN self_attendance_face_threshold FLOAT DEFAULT 0.52 NOT NULL"))
                logger.info("Migrated system_branding table: added self_attendance_face_threshold column.")

            # 1b. Attendance Records geofencing columns
            res = conn.execute(text("SHOW COLUMNS FROM attendance_records LIKE 'geo_latitude'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE attendance_records ADD COLUMN geo_latitude FLOAT NULL"))
                logger.info("Migrated attendance_records table: added geo_latitude column.")

            res = conn.execute(text("SHOW COLUMNS FROM attendance_records LIKE 'geo_longitude'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE attendance_records ADD COLUMN geo_longitude FLOAT NULL"))
                logger.info("Migrated attendance_records table: added geo_longitude column.")

            res = conn.execute(text("SHOW COLUMNS FROM attendance_records LIKE 'geo_distance_meters'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE attendance_records ADD COLUMN geo_distance_meters FLOAT NULL"))
                logger.info("Migrated attendance_records table: added geo_distance_meters column.")

            res = conn.execute(text("SHOW COLUMNS FROM attendance_records LIKE 'is_self_attendance'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE attendance_records ADD COLUMN is_self_attendance BOOLEAN DEFAULT FALSE NOT NULL"))
                logger.info("Migrated attendance_records table: added is_self_attendance column.")

            # 2. Tenants table subscription & organization type columns
            res = conn.execute(text("SHOW COLUMNS FROM tenants LIKE 'tenant_type'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE tenants ADD COLUMN tenant_type VARCHAR(30) DEFAULT 'educational' NOT NULL"))
                logger.info("Migrated tenants table: added tenant_type column.")

            res = conn.execute(text("SHOW COLUMNS FROM tenants LIKE 'subscription_plan'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE tenants ADD COLUMN subscription_plan VARCHAR(30) DEFAULT 'STANDARD' NOT NULL"))
                logger.info("Migrated tenants table: added subscription_plan column.")

            res = conn.execute(text("SHOW COLUMNS FROM tenants LIKE 'subscription_status'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE tenants ADD COLUMN subscription_status VARCHAR(30) DEFAULT 'ACTIVE' NOT NULL"))
                logger.info("Migrated tenants table: added subscription_status column.")

            res = conn.execute(text("SHOW COLUMNS FROM tenants LIKE 'max_face_encodings'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE tenants ADD COLUMN max_face_encodings INT DEFAULT 500 NOT NULL"))
                logger.info("Migrated tenants table: added max_face_encodings column.")

            res = conn.execute(text("SHOW COLUMNS FROM tenants LIKE 'max_nodes'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE tenants ADD COLUMN max_nodes INT DEFAULT 10 NOT NULL"))
                logger.info("Migrated tenants table: added max_nodes column.")

            res = conn.execute(text("SHOW COLUMNS FROM tenants LIKE 'subscription_expires_at'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE tenants ADD COLUMN subscription_expires_at DATETIME NULL"))
                logger.info("Migrated tenants table: added subscription_expires_at column.")

            res = conn.execute(text("SHOW COLUMNS FROM tenants LIKE 'is_deleted'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE tenants ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE NOT NULL"))
                logger.info("Migrated tenants table: added is_deleted column.")

            res = conn.execute(text("SHOW COLUMNS FROM tenants LIKE 'deleted_at'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE tenants ADD COLUMN deleted_at DATETIME NULL"))
                logger.info("Migrated tenants table: added deleted_at column.")

            # 2b. Tenants table tokenized links columns & backfill
            res = conn.execute(text("SHOW COLUMNS FROM tenants LIKE 'uuid'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE tenants ADD COLUMN uuid VARCHAR(36) NULL"))
                conn.execute(text("CREATE UNIQUE INDEX ix_tenants_uuid ON tenants(uuid)"))
                logger.info("Migrated tenants table: added uuid column.")

            res = conn.execute(text("SHOW COLUMNS FROM tenants LIKE 'admin_token'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE tenants ADD COLUMN admin_token VARCHAR(64) NULL"))
                conn.execute(text("CREATE UNIQUE INDEX ix_tenants_admin_token ON tenants(admin_token)"))
                logger.info("Migrated tenants table: added admin_token column.")

            res = conn.execute(text("SHOW COLUMNS FROM tenants LIKE 'onboarding_token'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE tenants ADD COLUMN onboarding_token VARCHAR(64) NULL"))
                conn.execute(text("CREATE UNIQUE INDEX ix_tenants_onboarding_token ON tenants(onboarding_token)"))
                logger.info("Migrated tenants table: added onboarding_token column.")

            res = conn.execute(text("SHOW COLUMNS FROM tenants LIKE 'attendance_slug'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE tenants ADD COLUMN attendance_slug VARCHAR(64) NULL"))
                conn.execute(text("CREATE UNIQUE INDEX ix_tenants_attendance_slug ON tenants(attendance_slug)"))
                logger.info("Migrated tenants table: added attendance_slug column.")

            # Backfill any existing tenants with missing tokens
            tenant_rows = conn.execute(text("SELECT id, uuid, admin_token, onboarding_token, attendance_slug FROM tenants")).fetchall()
            for r in tenant_rows:
                t_id = r[0]
                t_uuid = r[1] or str(uuid.uuid4())
                t_adm = r[2] or secrets.token_urlsafe(32)
                t_onb = r[3] or secrets.token_urlsafe(32)
                t_att = r[4] or secrets.token_urlsafe(24)
                if not (r[1] and r[2] and r[3] and r[4]):
                    conn.execute(
                        text("UPDATE tenants SET uuid = :u, admin_token = :adm, onboarding_token = :onb, attendance_slug = :att WHERE id = :tid"),
                        {"u": t_uuid, "adm": t_adm, "onb": t_onb, "att": t_att, "tid": t_id}
                    )
                    logger.info(f"Backfilled tokens & uuid for Tenant #{t_id}.")

            # 3. Classes table department_id column
            res = conn.execute(text("SHOW COLUMNS FROM classes LIKE 'department_id'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE classes ADD COLUMN department_id INT NULL"))
                logger.info("Migrated classes table: added department_id column.")

            # 4. Students table academic structure & progression columns
            res = conn.execute(text("SHOW COLUMNS FROM students LIKE 'department_id'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE students ADD COLUMN department_id INT NULL"))
                logger.info("Migrated students table: added department_id column.")

            res = conn.execute(text("SHOW COLUMNS FROM students LIKE 'class_id'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE students ADD COLUMN class_id INT NULL"))
                logger.info("Migrated students table: added class_id column.")

            res = conn.execute(text("SHOW COLUMNS FROM students LIKE 'division_id'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE students ADD COLUMN division_id INT NULL"))
                logger.info("Migrated students table: added division_id column.")

            res = conn.execute(text("SHOW COLUMNS FROM students LIKE 'academic_year_id'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE students ADD COLUMN academic_year_id INT NULL"))
                logger.info("Migrated students table: added academic_year_id column.")

            res = conn.execute(text("SHOW COLUMNS FROM students LIKE 'user_id'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE students ADD COLUMN user_id INT NULL"))
                logger.info("Migrated students table: added user_id column.")

            res = conn.execute(text("SHOW COLUMNS FROM students LIKE 'previous_class_id'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE students ADD COLUMN previous_class_id INT NULL"))
                logger.info("Migrated students table: added previous_class_id column.")

            res = conn.execute(text("SHOW COLUMNS FROM students LIKE 'previous_division_id'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE students ADD COLUMN previous_division_id INT NULL"))
                logger.info("Migrated students table: added previous_division_id column.")

            res = conn.execute(text("SHOW COLUMNS FROM students LIKE 'previous_academic_year_id'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE students ADD COLUMN previous_academic_year_id INT NULL"))
                logger.info("Migrated students table: added previous_academic_year_id column.")

            res = conn.execute(text("SHOW COLUMNS FROM students LIKE 'last_promoted_at'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE students ADD COLUMN last_promoted_at DATETIME NULL"))
                logger.info("Migrated students table: added last_promoted_at column.")

            res = conn.execute(text("SHOW COLUMNS FROM students LIKE 'gender'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE students ADD COLUMN gender VARCHAR(20) DEFAULT 'Other' NULL"))
                logger.info("Migrated students table: added gender column.")

            res = conn.execute(text("SHOW COLUMNS FROM students LIKE 'batch_upload_id'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE students ADD COLUMN batch_upload_id INT NULL"))
                logger.info("Migrated students table: added batch_upload_id column.")

            res = conn.execute(text("SHOW COLUMNS FROM students LIKE 'previous_department_id'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE students ADD COLUMN previous_department_id INT NULL"))
                logger.info("Migrated students table: added previous_department_id column.")

            res = conn.execute(text("SHOW COLUMNS FROM students LIKE 'last_transferred_at'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE students ADD COLUMN last_transferred_at DATETIME NULL"))
                logger.info("Migrated students table: added last_transferred_at column.")

            res = conn.execute(text("SHOW COLUMNS FROM students LIKE 'phone_number'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE students ADD COLUMN phone_number VARCHAR(50) NULL"))
                logger.info("Migrated students table: added phone_number column.")

            res = conn.execute(text("SHOW COLUMNS FROM students LIKE 'hourly_rate'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE students ADD COLUMN hourly_rate FLOAT NULL"))
                logger.info("Migrated students table: added hourly_rate column.")

            res = conn.execute(text("SHOW COLUMNS FROM students LIKE 'monthly_base_salary'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE students ADD COLUMN monthly_base_salary FLOAT NULL"))
                logger.info("Migrated students table: added monthly_base_salary column.")


            # 5. System Branding shift timings & payroll columns
            res = conn.execute(text("SHOW COLUMNS FROM system_branding LIKE 'shift_check_in_time'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE system_branding ADD COLUMN shift_check_in_time VARCHAR(10) DEFAULT '10:30' NOT NULL"))
                logger.info("Migrated system_branding table: added shift_check_in_time column.")

            res = conn.execute(text("SHOW COLUMNS FROM system_branding LIKE 'shift_check_out_time'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE system_branding ADD COLUMN shift_check_out_time VARCHAR(10) DEFAULT '18:00' NOT NULL"))
                logger.info("Migrated system_branding table: added shift_check_out_time column.")

            res = conn.execute(text("SHOW COLUMNS FROM system_branding LIKE 'shift_grace_minutes'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE system_branding ADD COLUMN shift_grace_minutes INT DEFAULT 15 NOT NULL"))
                logger.info("Migrated system_branding table: added shift_grace_minutes column.")

            res = conn.execute(text("SHOW COLUMNS FROM system_branding LIKE 'min_checkout_interval_minutes'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE system_branding ADD COLUMN min_checkout_interval_minutes INT DEFAULT 15 NOT NULL"))
                logger.info("Migrated system_branding table: added min_checkout_interval_minutes column.")

            res = conn.execute(text("SHOW COLUMNS FROM system_branding LIKE 'payroll_structure'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE system_branding ADD COLUMN payroll_structure VARCHAR(30) DEFAULT 'HOURLY' NOT NULL"))
                logger.info("Migrated system_branding table: added payroll_structure column.")

            res = conn.execute(text("SHOW COLUMNS FROM system_branding LIKE 'default_hourly_rate'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE system_branding ADD COLUMN default_hourly_rate FLOAT DEFAULT 15.0 NULL"))
                logger.info("Migrated system_branding table: added default_hourly_rate column.")

            res = conn.execute(text("SHOW COLUMNS FROM system_branding LIKE 'standard_working_hours_per_day'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE system_branding ADD COLUMN standard_working_hours_per_day FLOAT DEFAULT 8.0 NULL"))
                logger.info("Migrated system_branding table: added standard_working_hours_per_day column.")

            res = conn.execute(text("SHOW COLUMNS FROM system_branding LIKE 'enable_overtime'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE system_branding ADD COLUMN enable_overtime BOOLEAN DEFAULT TRUE NOT NULL"))
                logger.info("Migrated system_branding table: added enable_overtime column.")

            res = conn.execute(text("SHOW COLUMNS FROM system_branding LIKE 'overtime_rate_multiplier'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE system_branding ADD COLUMN overtime_rate_multiplier FLOAT DEFAULT 1.5 NULL"))
                logger.info("Migrated system_branding table: added overtime_rate_multiplier column.")

            res = conn.execute(text("SHOW COLUMNS FROM system_branding LIKE 'missed_checkout_policy'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE system_branding ADD COLUMN missed_checkout_policy VARCHAR(30) DEFAULT 'HALF_DAY' NOT NULL"))
                logger.info("Migrated system_branding table: added missed_checkout_policy column.")

            res = conn.execute(text("SHOW COLUMNS FROM system_branding LIKE 'currency_symbol'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE system_branding ADD COLUMN currency_symbol VARCHAR(10) DEFAULT '₹' NOT NULL"))
                logger.info("Migrated system_branding table: added currency_symbol column.")

            res = conn.execute(text("SHOW COLUMNS FROM system_branding LIKE 'holiday_ot_multiplier'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE system_branding ADD COLUMN holiday_ot_multiplier FLOAT DEFAULT 2.0 NULL"))
                logger.info("Migrated system_branding table: added holiday_ot_multiplier column.")

            res = conn.execute(text("SHOW COLUMNS FROM system_branding LIKE 'enable_pf_ceiling'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE system_branding ADD COLUMN enable_pf_ceiling BOOLEAN DEFAULT TRUE NOT NULL"))
                logger.info("Migrated system_branding table: added enable_pf_ceiling column.")

            res = conn.execute(text("SHOW COLUMNS FROM system_branding LIKE 'epf_ceiling_limit'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE system_branding ADD COLUMN epf_ceiling_limit FLOAT DEFAULT 15000.0 NOT NULL"))
                logger.info("Migrated system_branding table: added epf_ceiling_limit column.")

            res = conn.execute(text("SHOW COLUMNS FROM system_branding LIKE 'esi_gross_threshold'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE system_branding ADD COLUMN esi_gross_threshold FLOAT DEFAULT 21000.0 NOT NULL"))
                logger.info("Migrated system_branding table: added esi_gross_threshold column.")

            res = conn.execute(text("SHOW COLUMNS FROM system_branding LIKE 'epf_employee_pct'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE system_branding ADD COLUMN epf_employee_pct FLOAT DEFAULT 12.0 NOT NULL"))
                logger.info("Migrated system_branding table: added epf_employee_pct column.")

            res = conn.execute(text("SHOW COLUMNS FROM system_branding LIKE 'epf_employer_pct'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE system_branding ADD COLUMN epf_employer_pct FLOAT DEFAULT 12.0 NOT NULL"))
                logger.info("Migrated system_branding table: added epf_employer_pct column.")

            res = conn.execute(text("SHOW COLUMNS FROM system_branding LIKE 'esic_employee_pct'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE system_branding ADD COLUMN esic_employee_pct FLOAT DEFAULT 0.75 NOT NULL"))
                logger.info("Migrated system_branding table: added esic_employee_pct column.")

            res = conn.execute(text("SHOW COLUMNS FROM system_branding LIKE 'esic_employer_pct'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE system_branding ADD COLUMN esic_employer_pct FLOAT DEFAULT 3.25 NOT NULL"))
                logger.info("Migrated system_branding table: added esic_employer_pct column.")

            res = conn.execute(text("SHOW COLUMNS FROM system_branding LIKE 'pt_monthly_default'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE system_branding ADD COLUMN pt_monthly_default FLOAT DEFAULT 200.0 NOT NULL"))
                logger.info("Migrated system_branding table: added pt_monthly_default column.")

            # 6. Attendance Records checkin / checkout and shift tracking columns
            res = conn.execute(text("SHOW COLUMNS FROM attendance_records LIKE 'punch_type'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE attendance_records ADD COLUMN punch_type VARCHAR(20) DEFAULT 'CHECK_IN' NOT NULL"))
                logger.info("Migrated attendance_records table: added punch_type column.")

            res = conn.execute(text("SHOW COLUMNS FROM attendance_records LIKE 'check_in_time'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE attendance_records ADD COLUMN check_in_time DATETIME NULL"))
                conn.execute(text("UPDATE attendance_records SET check_in_time = timestamp WHERE check_in_time IS NULL"))
                logger.info("Migrated attendance_records table: added check_in_time column.")

            res = conn.execute(text("SHOW COLUMNS FROM attendance_records LIKE 'check_out_time'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE attendance_records ADD COLUMN check_out_time DATETIME NULL"))
                logger.info("Migrated attendance_records table: added check_out_time column.")

            res = conn.execute(text("SHOW COLUMNS FROM attendance_records LIKE 'work_duration_minutes'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE attendance_records ADD COLUMN work_duration_minutes INT NULL"))
                logger.info("Migrated attendance_records table: added work_duration_minutes column.")

            res = conn.execute(text("SHOW COLUMNS FROM attendance_records LIKE 'shift_status'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE attendance_records ADD COLUMN shift_status VARCHAR(30) DEFAULT 'ON_TIME' NOT NULL"))
                logger.info("Migrated attendance_records table: added shift_status column.")

            # 7. Students offboarding & relieving columns
            res = conn.execute(text("SHOW COLUMNS FROM students LIKE 'employment_status'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE students ADD COLUMN employment_status VARCHAR(30) DEFAULT 'ACTIVE' NOT NULL"))
                conn.execute(text("CREATE INDEX ix_student_tenant_status ON students(tenant_id, employment_status)"))
                logger.info("Migrated students table: added employment_status column.")

            res = conn.execute(text("SHOW COLUMNS FROM students LIKE 'relieved_at'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE students ADD COLUMN relieved_at DATETIME NULL"))
                logger.info("Migrated students table: added relieved_at column.")

            res = conn.execute(text("SHOW COLUMNS FROM students LIKE 'relieving_reason'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE students ADD COLUMN relieving_reason TEXT NULL"))
                logger.info("Migrated students table: added relieving_reason column.")

            res = conn.execute(text("SHOW COLUMNS FROM students LIKE 'relieved_by_user_id'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE students ADD COLUMN relieved_by_user_id INT NULL"))
                logger.info("Migrated students table: added relieved_by_user_id column.")

            # 8. Students shift_id column & work_shifts migration
            res = conn.execute(text("SHOW COLUMNS FROM students LIKE 'shift_id'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE students ADD COLUMN shift_id INT NULL"))
                try:
                    conn.execute(text("CREATE INDEX ix_student_shift_id ON students(shift_id)"))
                except Exception:
                    pass
                logger.info("Migrated students table: added shift_id column.")

            # 9. Students Location, Designation, Banking & Statutory columns
            res = conn.execute(text("SHOW COLUMNS FROM students LIKE 'location_id'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE students ADD COLUMN location_id INT NULL"))
                logger.info("Migrated students table: added location_id column.")


            res = conn.execute(text("SHOW COLUMNS FROM students LIKE 'designation_id'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE students ADD COLUMN designation_id INT NULL"))
                logger.info("Migrated students table: added designation_id column.")

            res = conn.execute(text("SHOW COLUMNS FROM students LIKE 'designation'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE students ADD COLUMN designation VARCHAR(100) NULL"))
                logger.info("Migrated students table: added designation column.")

            res = conn.execute(text("SHOW COLUMNS FROM students LIKE 'pan_number'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE students ADD COLUMN pan_number VARCHAR(30) NULL"))
                logger.info("Migrated students table: added pan_number column.")

            res = conn.execute(text("SHOW COLUMNS FROM students LIKE 'uan_number'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE students ADD COLUMN uan_number VARCHAR(30) NULL"))
                logger.info("Migrated students table: added uan_number column.")

            res = conn.execute(text("SHOW COLUMNS FROM students LIKE 'esic_number'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE students ADD COLUMN esic_number VARCHAR(30) NULL"))
                logger.info("Migrated students table: added esic_number column.")

            res = conn.execute(text("SHOW COLUMNS FROM students LIKE 'bank_name'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE students ADD COLUMN bank_name VARCHAR(100) NULL"))
                logger.info("Migrated students table: added bank_name column.")

            res = conn.execute(text("SHOW COLUMNS FROM students LIKE 'bank_account_number'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE students ADD COLUMN bank_account_number VARCHAR(50) NULL"))
                logger.info("Migrated students table: added bank_account_number column.")

            res = conn.execute(text("SHOW COLUMNS FROM students LIKE 'bank_ifsc_code'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE students ADD COLUMN bank_ifsc_code VARCHAR(30) NULL"))
                logger.info("Migrated students table: added bank_ifsc_code column.")

            # Seed default WorkShift for corporate tenants if none exist
            try:
                corp_tenants = conn.execute(text("SELECT id, name FROM tenants WHERE tenant_type = 'corporate' AND is_deleted = 0")).fetchall()
                for ct in corp_tenants:
                    t_id = ct[0]
                    shifts = conn.execute(text("SELECT id FROM work_shifts WHERE tenant_id = :tid"), {"tid": t_id}).fetchall()
                    if not shifts:
                        b_row = conn.execute(text("SELECT shift_check_in_time, shift_check_out_time, shift_grace_minutes FROM system_branding WHERE tenant_id = :tid"), {"tid": t_id}).fetchone()
                        s_in = b_row[0] if b_row and b_row[0] else "10:30"
                        s_out = b_row[1] if b_row and b_row[1] else "18:00"
                        s_grace = b_row[2] if b_row and b_row[2] is not None else 15
                        conn.execute(
                            text("INSERT INTO work_shifts (tenant_id, name, code, start_time, end_time, grace_period_minutes, break_duration_minutes, half_day_hours, is_default, is_active, created_at) "
                                 "VALUES (:tid, 'General Shift', 'GEN', :sin, :sout, :sgrace, 0, 4.0, 1, 1, NOW())"),
                            {"tid": t_id, "sin": s_in, "sout": s_out, "sgrace": s_grace}
                        )
                        logger.info(f"Seeded default 'General Shift' for corporate Tenant #{t_id}.")
            except Exception as e_shift:
                logger.warning(f"WorkShift seeding note: {e_shift}")

    except Exception as e:
        logger.warning(f"Schema migration note: {e}")


def init_db():
    """Creates all database tables in MySQL and seeds default organization if missing."""
    ensure_mysql_database_exists()
    Base.metadata.create_all(bind=engine)
    run_schema_migrations()
    seed_default_tenant_and_branding()
    logger.info("MySQL Multi-Tenant database tables initialized.")


def get_db():
    """FastAPI dependency for yielding database session with auto-close."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    """Context manager for standalone scripts, background workers, or engines."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
