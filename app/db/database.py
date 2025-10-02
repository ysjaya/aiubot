from sqlmodel import create_engine, Session, SQLModel
from sqlalchemy import text
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Single engine pointing to DATABASE_URL with optimized pooling
engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
)

def get_session():
    """Provide database session"""
    with Session(engine) as session:
        yield session

def init_db():
    """Initialize database and ensure all columns exist"""
    try:
        # Create all tables
        SQLModel.metadata.create_all(engine)
        logger.info("✅ Database tables created/verified")
        
        # Fix missing columns in conversation table
        fix_conversation_table_columns()
        
        # Fix missing columns in attachment table
        fix_attachment_table_columns()
        
        # Fix missing columns in chat table
        fix_chat_table_columns()
        
        # Fix missing columns in draftversion table
        fix_draftversion_table_columns()
        
        logger.info("✅ Database initialization complete")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        raise

def fix_conversation_table_columns():
    """Add missing columns and remove old columns from conversation table"""
    try:
        with Session(engine) as session:
            # Efficient single query to check required columns
            result = session.exec(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'conversation' 
                AND column_name IN ('project_id', 'updated_at')
            """))
            
            existing_columns = {row[0] for row in result}
            
            # Only run migrations if needed
            needs_migration = False
            
            if 'project_id' in existing_columns:
                logger.info("Removing project_id column from conversation table...")
                session.exec(text("ALTER TABLE conversation DROP COLUMN project_id CASCADE"))
                needs_migration = True
            
            if 'updated_at' not in existing_columns:
                logger.info("Adding updated_at column to conversation table...")
                session.exec(text("ALTER TABLE conversation ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
                needs_migration = True
            
            if needs_migration:
                session.commit()
                logger.info("✅ Conversation table migrated")
            
    except Exception as e:
        logger.warning(f"⚠️ Could not auto-fix conversation table: {e}")

def fix_attachment_table_columns():
    """Add missing columns to attachment table if they don't exist"""
    try:
        with Session(engine) as session:
            # Quick check for file_path column only
            result = session.exec(text("""
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'attachment' AND column_name = 'file_path'
            """))
            
            if not result.first():
                logger.info("Adding file_path column to attachment table...")
                session.exec(text("ALTER TABLE attachment ADD COLUMN file_path VARCHAR DEFAULT ''"))
                session.commit()
                logger.info("✅ Attachment table migrated")
            
    except Exception as e:
        logger.warning(f"⚠️ Could not auto-fix attachment table: {e}")

def fix_chat_table_columns():
    """Add missing columns to chat table if they don't exist"""
    try:
        with Session(engine) as session:
            # Batch check for required columns
            result = session.exec(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'chat' 
                AND column_name IN ('response_received_at', 'context_file_ids', 'files_modified')
            """))
            
            existing_columns = {row[0] for row in result}
            needs_migration = False
            
            if 'response_received_at' not in existing_columns:
                logger.info("Adding response_received_at column...")
                session.exec(text("ALTER TABLE chat ADD COLUMN response_received_at TIMESTAMP NULL"))
                needs_migration = True
            
            if 'context_file_ids' not in existing_columns:
                logger.info("Adding context_file_ids column...")
                session.exec(text("ALTER TABLE chat ADD COLUMN context_file_ids VARCHAR NULL"))
                needs_migration = True
            
            if 'files_modified' not in existing_columns:
                logger.info("Adding files_modified column...")
                session.exec(text("ALTER TABLE chat ADD COLUMN files_modified VARCHAR NULL"))
                needs_migration = True
            
            if needs_migration:
                session.commit()
                logger.info("✅ Chat table migrated")
            
    except Exception as e:
        logger.warning(f"⚠️ Could not auto-fix chat table: {e}")

def fix_draftversion_table_columns():
    """Remove old columns from draftversion table"""
    try:
        with Session(engine) as session:
            # Quick check for project_id column
            result = session.exec(text("""
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'draftversion' AND column_name = 'project_id'
            """))
            
            if result.first():
                logger.info("Removing project_id column from draftversion...")
                session.exec(text("ALTER TABLE draftversion DROP COLUMN project_id CASCADE"))
                session.commit()
                logger.info("✅ DraftVersion table migrated")
            
    except Exception as e:
        logger.warning(f"⚠️ Could not auto-fix draftversion table: {e}")
