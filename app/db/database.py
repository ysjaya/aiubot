from sqlmodel import create_engine, Session, SQLModel
from sqlalchemy import text
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Single engine pointing to DATABASE_URL
engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10
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
        
        # Fix missing columns in chat table
        fix_chat_table_columns()
        
        logger.info("✅ Database initialization complete")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        raise

def fix_conversation_table_columns():
    """Add missing columns to conversation table if they don't exist"""
    try:
        with Session(engine) as session:
            # Check if columns exist
            result = session.exec(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'conversation'
            """))
            
            existing_columns = [row[0] for row in result]
            
            # Add updated_at if missing
            if 'updated_at' not in existing_columns:
                logger.info("Adding updated_at column to conversation table...")
                session.exec(text("""
                    ALTER TABLE conversation 
                    ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                """))
                session.commit()
                logger.info("✅ Added updated_at column")
            
            logger.info("✅ Conversation table columns verified/fixed")
            
    except Exception as e:
        logger.warning(f"⚠️ Could not auto-fix conversation table columns: {e}")
        # Don't raise - let the app continue, migrations might handle it

def fix_chat_table_columns():
    """Add missing columns to chat table if they don't exist"""
    try:
        with Session(engine) as session:
            # Check if columns exist
            result = session.exec(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'chat'
            """))
            
            existing_columns = [row[0] for row in result]
            
            # Add context_file_ids if missing
            if 'context_file_ids' not in existing_columns:
                logger.info("Adding context_file_ids column to chat table...")
                session.exec(text("""
                    ALTER TABLE chat 
                    ADD COLUMN context_file_ids VARCHAR NULL
                """))
                session.commit()
                logger.info("✅ Added context_file_ids column")
            
            # Add files_modified if missing
            if 'files_modified' not in existing_columns:
                logger.info("Adding files_modified column to chat table...")
                session.exec(text("""
                    ALTER TABLE chat 
                    ADD COLUMN files_modified VARCHAR NULL
                """))
                session.commit()
                logger.info("✅ Added files_modified column")
            
            logger.info("✅ Chat table columns verified/fixed")
            
    except Exception as e:
        logger.warning(f"⚠️ Could not auto-fix chat table columns: {e}")
        # Don't raise - let the app continue, migrations might handle it
