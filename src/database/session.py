from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from src.config import DATABASE_URL
from src.database.models import Base

# SQLite engine with thread-safety for multi-threaded/async access
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def run_db_migrations():
    """Safely adds newly introduced columns to existing SQLite tables if not present."""
    with engine.begin() as conn:
        # 1. Check students table
        try:
            res = conn.execute(text("PRAGMA table_info(students)")).fetchall()
            existing_cols = [row[1] for row in res]
            if "user_role" not in existing_cols:
                conn.execute(text("ALTER TABLE students ADD COLUMN user_role VARCHAR(30) DEFAULT 'student'"))
            if "class_semester" not in existing_cols:
                conn.execute(text("ALTER TABLE students ADD COLUMN class_semester VARCHAR(50) DEFAULT 'General'"))
        except Exception as e:
            print(f"[!] Migration notice on students: {e}")

        # 2. Check attendance_records table
        try:
            res = conn.execute(text("PRAGMA table_info(attendance_records)")).fetchall()
            existing_cols = [row[1] for row in res]
            if "is_manual_override" not in existing_cols:
                conn.execute(text("ALTER TABLE attendance_records ADD COLUMN is_manual_override BOOLEAN DEFAULT 0"))
            if "override_reason" not in existing_cols:
                conn.execute(text("ALTER TABLE attendance_records ADD COLUMN override_reason VARCHAR(255)"))
            if "override_by" not in existing_cols:
                conn.execute(text("ALTER TABLE attendance_records ADD COLUMN override_by VARCHAR(100) DEFAULT 'Admin'"))
        except Exception as e:
            print(f"[!] Migration notice on attendance_records: {e}")

        # 3. Check system_branding table
        try:
            res = conn.execute(text("SELECT COUNT(*) FROM system_branding")).scalar()
            if res == 0:
                conn.execute(text("""
                    INSERT INTO system_branding (id, institution_name, short_code, tagline, primary_accent_color, header_badge_text)
                    VALUES (1, 'FaceAttendance Campus', 'FA-HUB', 'Raspberry Pi Zero Edge Nodes & Central Face Recognition', '#6366f1', 'Thin-Client Hub')
                """))
        except Exception as e:
            pass


def init_db():
    """Creates all database tables and runs schema migrations if they do not already exist."""
    Base.metadata.create_all(bind=engine)
    run_db_migrations()


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
