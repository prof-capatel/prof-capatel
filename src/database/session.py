import logging
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
    SystemBranding,
    User,
    AcademicYear,
    ClassModel,
    Division,
    TeacherClassAssignment,
    Student,
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


def seed_default_tenant_and_branding():
    """Seeds default tenant, branding, RBAC users, and academic structure if database is fresh."""
    with SessionLocal() as db:
        try:
            # 1. Default Tenant
            default_tenant = db.query(Tenant).filter(Tenant.id == DEFAULT_TENANT_ID).first()
            if not default_tenant:
                default_tenant = Tenant(
                    id=DEFAULT_TENANT_ID,
                    slug=DEFAULT_TENANT_SLUG,
                    name="FaceAttendance Campus",
                    contact_email="admin@campus.edu",
                    is_active=True,
                    subscription_plan="ENTERPRISE",
                    subscription_status="ACTIVE",
                    max_face_encodings=5000,
                    max_nodes=50,
                )
                db.add(default_tenant)
                db.flush()
                logger.info(f"Seeded default Tenant #{DEFAULT_TENANT_ID} ('{DEFAULT_TENANT_SLUG}').")

            # 2. Default Branding
            branding = db.query(SystemBranding).filter(SystemBranding.tenant_id == DEFAULT_TENANT_ID).first()
            if not branding:
                branding = SystemBranding(
                    tenant_id=DEFAULT_TENANT_ID,
                    institution_name="FaceAttendance Campus",
                    short_code="FA-HUB",
                    tagline="Raspberry Pi Zero Edge Nodes & Central Face Recognition",
                    primary_accent_color="#6366f1",
                    header_badge_text="Thin-Client Hub",
                    cooldown_minutes=60,
                    enable_anti_spoofing=True,
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

            # 4. Seed Academic Hierarchy (Years, Classes, Divisions)
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
                    department="Computer Science",
                    name="FY Computer Science",
                    code="FY-CS",
                )
                db.add(class_fy)
                db.flush()

            class_sy = db.query(ClassModel).filter(ClassModel.tenant_id == DEFAULT_TENANT_ID, ClassModel.name == "SY Computer Science").first()
            if not class_sy:
                class_sy = ClassModel(
                    tenant_id=DEFAULT_TENANT_ID,
                    department="Computer Science",
                    name="SY Computer Science",
                    code="SY-CS",
                )
                db.add(class_sy)
                db.flush()

            class_ty = db.query(ClassModel).filter(ClassModel.tenant_id == DEFAULT_TENANT_ID, ClassModel.name == "TY Computer Science").first()
            if not class_ty:
                class_ty = ClassModel(
                    tenant_id=DEFAULT_TENANT_ID,
                    department="Computer Science",
                    name="TY Computer Science",
                    code="TY-CS",
                )
                db.add(class_ty)
                db.flush()

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

            # Link existing students to FY-CS Division A if not assigned
            unassigned_students = db.query(Student).filter(Student.tenant_id == DEFAULT_TENANT_ID, Student.class_id == None).all()
            for std in unassigned_students:
                std.class_id = class_fy.id
                std.division_id = div_a.id if div_a else None
                std.academic_year_id = acad_year.id if acad_year else None

            db.commit()
            logger.info("Database default seeds completed successfully.")
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

            # 2. Tenants table subscription columns
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

            # 3. Students table academic structure & progression columns
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
