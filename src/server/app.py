from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.config import DATA_DIR, FACES_DIR, SNAPSHOTS_DIR
from src.core.face_engine import face_engine
from src.database.session import init_db
from src.server.routes import (
    views_dashboard,
    api_auth,
    api_super_admin,
    api_academic,
    api_teacher,
    api_tenants,
    api_nodes,
    api_enrollment,
    api_attendance,
    api_branding,
    api_payroll,
    api_leave,
    api_employee_portal,
    api_shifts,
)

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("attendance_app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes MySQL database schema and preloads partitioned FaceEngine cache into RAM."""
    logger.info("Initializing Multi-Tenant MySQL Attendance SaaS...")
    # 1. Initialize DB schema
    init_db()
    logger.info("MySQL database schema and default tenant initialized.")

    # 2. Preload face embeddings into in-memory matrix partitioned by tenant
    try:
        face_engine.initialize()
    except Exception as e:
        logger.warning(f"FaceEngine initialization notice: {e}")

    logger.info("Server startup complete. Ready for multi-tenant node streams.")
    yield
    logger.info("Server shutting down.")


# Create FastAPI application
app = FastAPI(
    title="Multi-Tenant Thin-Client Face Recognition Attendance SaaS",
    description="Central recognition server for classroom edge capture nodes across multiple institutions.",
    version="2.0.0",
    lifespan=lifespan,
)

# Enable CORS for cross-origin or local network edge devices
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static Assets & Data Storage
app.mount("/static", StaticFiles(directory="src/server/static"), name="static")
app.mount("/data", StaticFiles(directory=str(DATA_DIR)), name="data")

# Register Routers
app.include_router(views_dashboard.router)
app.include_router(api_auth.router)
app.include_router(api_super_admin.router)
app.include_router(api_academic.router)
app.include_router(api_teacher.router)
app.include_router(api_tenants.router)
app.include_router(api_nodes.router)
app.include_router(api_enrollment.router)
app.include_router(api_attendance.router)
app.include_router(api_branding.router)
app.include_router(api_payroll.router)
app.include_router(api_leave.router)
app.include_router(api_employee_portal.router)
app.include_router(api_shifts.router)


@app.get("/health")
def health_check():
    """Health check endpoint for node discovery."""
    return {"status": "healthy", "service": "Multi-Tenant Face Recognition Attendance SaaS"}
