from sqlmodel import create_engine, Session, SQLModel
from sqlalchemy import text
from app.core.config import settings
import logging
from functools import lru_cache
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# --- PERBAIKAN DITAMBAHKAN DI SINI ---
connect_args = {"client_encoding": "utf8"}

# Main engine for metadata storage with connection pooling
engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
    connect_args=connect_args  # <-- Tambahan
)

def get_session():
    """Get database session"""
    with Session(engine) as session:
        yield session

def create_project_database(project_name: str) -> str:
    """Create isolated database for a project"""
    # Sanitize project name for database naming
    db_name = f"project_{project_name.lower().replace(' ', '_').replace('-', '_')}"
    db_name = ''.join(c for c in db_name if c.isalnum() or c == '_')[:50]
    
    # Make unique with timestamp
    from datetime import datetime
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    db_name = f"{db_name}_{timestamp}"
    
    try:
        # Create database
        with engine.connect() as conn:
            conn.execution_options(isolation_level="AUTOCOMMIT")
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
        
        logger.info(f"Created project database: {db_name}")
        
        # Create tables in new database
        project_engine = create_engine(
            settings.DATABASE_URL.rsplit('/', 1)[0] + f'/{db_name}',
            echo=False,
            pool_pre_ping=True,
            connect_args=connect_args # <-- Tambahan juga di sini untuk engine proyek
        )
        SQLModel.metadata.create_all(project_engine)
        project_engine.dispose()
        
        return db_name
        
    except Exception as e:
        logger.error(f"Failed to create project database: {e}")
        raise

def delete_project_database(database_name: str):
    """Delete project database and clear cache"""
    try:
        logger.info(f"Clearing cache for database: {database_name}")
        get_project_engine.cache_clear()
        
        with engine.connect() as conn:
            conn.execution_options(isolation_level="AUTOCOMMIT")
            
            conn.execute(text(f"""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = '{database_name}'
                AND pid <> pg_backend_pid()
            """))
            
            conn.execute(text(f'DROP DATABASE IF EXISTS "{database_name}"'))
        
        logger.info(f"Deleted project database: {database_name}")
        
    except Exception as e:
        logger.error(f"Failed to delete project database: {e}")
        raise

@lru_cache(maxsize=100)
def get_project_engine(database_name: str):
    """Get cached engine for specific project database"""
    project_url = settings.DATABASE_URL.rsplit('/', 1)[0] + f'/{database_name}'
    
    try:
        eng = create_engine(
            project_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            pool_recycle=3600,
            connect_args=connect_args # <-- Tambahan
        )
        
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        return eng
        
    except Exception as e:
        logger.error(f"Failed to create engine for {database_name}: {e}")
        raise Exception(f"Database '{database_name}' does not exist or is inaccessible")

@contextmanager
def get_project_session(database_name: str):
    """Get session for specific project database with error handling"""
    try:
        project_engine = get_project_engine(database_name)
        
        with Session(project_engine) as session:
            yield session
            
    except Exception as e:
        logger.error(f"Failed to get project session for {database_name}: {e}")
        raise

def init_main_database():
    """Initialize main metadata database"""
    try:
        SQLModel.metadata.create_all(engine)
        logger.info("Main database initialized")
    except Exception as e:
        logger.error(f"Failed to initialize main database: {e}")
        raise

def cleanup_stale_engines():
    """Manually clear engine cache - call this periodically or after errors"""
    get_project_engine.cache_clear()
    logger.info("Cleared all cached database engines")
