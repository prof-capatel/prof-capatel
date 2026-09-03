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
from src.database.models import Base, Tenant, SystemBranding

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
    """Seeds default tenant and branding record if database is fresh."""
    with SessionLocal() as db:
        try:
            default_tenant = db.query(Tenant).filter(Tenant.id == DEFAULT_TENANT_ID).first()
            if not default_tenant:
                default_tenant = Tenant(
                    id=DEFAULT_TENANT_ID,
                    slug=DEFAULT_TENANT_SLUG,
                    name="FaceAttendance Campus",
                    contact_email="admin@campus.edu",
                    is_active=True,
                )
                db.add(default_tenant)
                db.flush()
                logger.info(f"Seeded default Tenant #{DEFAULT_TENANT_ID} ('{DEFAULT_TENANT_SLUG}').")

            branding = db.query(SystemBranding).filter(SystemBranding.tenant_id == DEFAULT_TENANT_ID).first()
            if not branding:
                branding = SystemBranding(
                    tenant_id=DEFAULT_TENANT_ID,
                    institution_name="FaceAttendance Campus",
                    short_code="FA-HUB",
                    tagline="Raspberry Pi Zero Edge Nodes & Central Face Recognition",
                    primary_accent_color="#6366f1",
                    header_badge_text="Thin-Client Hub",
                )
                db.add(branding)
                logger.info(f"Seeded default SystemBranding for Tenant #{DEFAULT_TENANT_ID}.")

            db.commit()
        except Exception as e:
            db.rollback()
            logger.warning(f"Default tenant seeding note: {e}")


def run_schema_migrations():
    """Checks and adds newly introduced columns to existing MySQL tables."""
    try:
        with engine.begin() as conn:
            # Check if cooldown_minutes exists in system_branding
            res = conn.execute(text("SHOW COLUMNS FROM system_branding LIKE 'cooldown_minutes'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE system_branding ADD COLUMN cooldown_minutes INT DEFAULT 60 NOT NULL"))
                logger.info("Migrated system_branding table: added cooldown_minutes column.")

            res = conn.execute(text("SHOW COLUMNS FROM system_branding LIKE 'liveness_mode'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE system_branding ADD COLUMN liveness_mode VARCHAR(20) DEFAULT 'BALANCED' NOT NULL"))
                logger.info("Migrated system_branding table: added liveness_mode column.")

            res = conn.execute(text("SHOW COLUMNS FROM system_branding LIKE 'temporal_frames_required'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE system_branding ADD COLUMN temporal_frames_required INT DEFAULT 3 NOT NULL"))
                logger.info("Migrated system_branding table: added temporal_frames_required column.")

            res = conn.execute(text("SHOW COLUMNS FROM system_branding LIKE 'enable_anti_spoofing'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE system_branding ADD COLUMN enable_anti_spoofing BOOLEAN DEFAULT TRUE NOT NULL"))
                logger.info("Migrated system_branding table: added enable_anti_spoofing column.")

            res = conn.execute(text("SHOW COLUMNS FROM system_branding LIKE 'enable_audio_chime'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE system_branding ADD COLUMN enable_audio_chime BOOLEAN DEFAULT TRUE NOT NULL"))
                logger.info("Migrated system_branding table: added enable_audio_chime column.")

            res = conn.execute(text("SHOW COLUMNS FROM system_branding LIKE 'enable_haptic_feedback'")).fetchall()
            if not res:
                conn.execute(text("ALTER TABLE system_branding ADD COLUMN enable_haptic_feedback BOOLEAN DEFAULT TRUE NOT NULL"))
                logger.info("Migrated system_branding table: added enable_haptic_feedback column.")
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
