from sqlmodel import create_engine, Session, SQLModel
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Kita hanya butuh SATU engine sekarang, yang menunjuk ke DATABASE_URL Anda
engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10
)

def get_session():
    """Menyediakan sesi database tunggal"""
    with Session(engine) as session:
        yield session

def init_db():
    """Membuat semua tabel di database tunggal jika belum ada"""
    try:
        # Create all tables for all models
        SQLModel.metadata.create_all(engine)
        logger.info("Database and tables initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {e}")
        raise
