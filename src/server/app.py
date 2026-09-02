from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.config import DATA_DIR, FACES_DIR, SNAPSHOTS_DIR
from src.core.face_engine import face_engine
from src.database.session import init_db
from src.server.routes import api_nodes, api_enrollment, api_attendance, api_branding, views_dashboard

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("attendance_app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes SQLite database and preloads FaceEngine cache into RAM."""
    logger.info("Initializing Attendance System...")
    # 1. Initialize DB schema
    init_db()
    logger.info("SQLite database schema initialized.")

    # 2. Preload face embeddings into in-memory matrix
    try:
        face_engine.initialize()
    except Exception as e:
        logger.warning(f"FaceEngine initialization notice: {e}")

    logger.info("Server startup complete. Ready for node streams.")
    yield
    logger.info("Server shutting down.")


# Create FastAPI application
app = FastAPI(
    title="Thin-Client Face Recognition Attendance Hub",
    description="Central recognition server for classroom edge capture nodes (Raspberry Pi Zero).",
    version="1.0.0",
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
app.include_router(api_nodes.router)
app.include_router(api_enrollment.router)
app.include_router(api_attendance.router)
app.include_router(api_branding.router)


@app.get("/health")
def health_check():
    """Health check endpoint for node discovery."""
    return {"status": "healthy", "service": "Face Recognition Attendance Server"}
