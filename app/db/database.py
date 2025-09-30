from sqlmodel import create_engine, Session, SQLModel
from sqlalchemy import text
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Main engine for metadata storage
engine = create_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)

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
            settings.DATABASE_URL.replace('/postgres', f'/{db_name}'),
            echo=False
        )
        SQLModel.metadata.create_all(project_engine)
        project_engine.dispose()
        
        return db_name
        
    except Exception as e:
        logger.error(f"Failed to create project database: {e}")
        raise

def delete_project_database(database_name: str):
    """Delete project database"""
    try:
        # Terminate all connections first
        with engine.connect() as conn:
            conn.execution_options(isolation_level="AUTOCOMMIT")
            
            # Terminate connections
            conn.execute(text(f"""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = '{database_name}'
                AND pid <> pg_backend_pid()
            """))
            
            # Drop database
            conn.execute(text(f'DROP DATABASE IF EXISTS "{database_name}"'))
        
        logger.info(f"Deleted project database: {database_name}")
        
    except Exception as e:
        logger.error(f"Failed to delete project database: {e}")
        raise

def get_project_session(database_name: str):
    """Get session for specific project database"""
    project_url = settings.DATABASE_URL.replace('/postgres', f'/{database_name}')
    project_engine = create_engine(project_url, echo=False, pool_pre_ping=True)
    
    with Session(project_engine) as session:
        yield session
    
    project_engine.dispose()

def init_main_database():
    """Initialize main metadata database"""
    try:
        SQLModel.metadata.create_all(engine)
        logger.info("Main database initialized")
    except Exception as e:
        logger.error(f"Failed to initialize main database: {e}")
        raise
