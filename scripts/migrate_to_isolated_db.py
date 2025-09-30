"""
Migration script to convert old single-database structure to isolated per-project databases

Run this if you have existing data in the old structure.

Usage:
    python scripts/migrate_to_isolated_db.py
"""

import sys
sys.path.append('.')

from sqlmodel import Session, select, create_engine
from app.db import models
from app.db.database import engine, create_project_database, get_project_session
from app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    """Migrate existing data to isolated databases"""
    
    print("\n" + "="*60)
    print("MIGRATION: Single DB → Isolated Project Databases")
    print("="*60 + "\n")
    
    print("⚠️  WARNING: This will:")
    print("   1. Create new isolated databases for each project")
    print("   2. Copy all data to new databases")
    print("   3. Update project records with database names")
    print("\n❗ BACKUP YOUR DATABASE FIRST!\n")
    
    response = input("Continue? (yes/no): ")
    if response.lower() != 'yes':
        print("❌ Migration cancelled")
        return
    
    with Session(engine) as session:
        # Get all existing projects
        projects = session.exec(select(models.Project)).all()
        
        if not projects:
            print("✅ No projects found. Nothing to migrate.")
            return
        
        print(f"\n📊 Found {len(projects)} projects to migrate\n")
        
        for project in projects:
            print(f"\n{'='*60}")
            print(f"Migrating Project: {project.name} (ID: {project.id})")
            print(f"{'='*60}")
            
            try:
                # Create isolated database
                print(f"  📂 Creating isolated database...")
                db_name = create_project_database(project.name)
                
                # Update project with database name
                project.database_name = db_name
                session.add(project)
                session.commit()
                
                print(f"  ✅ Created database: {db_name}")
                
                # Get conversations for this project
                conversations = session.exec(
                    select(models.Conversation)
                    .where(models.Conversation.project_id == project.id)
                ).all()
                
                print(f"  📝 Found {len(conversations)} conversations")
                
                # Copy data to new database
                with next(get_project_session(db_name)) as proj_session:
                    
                    for conv in conversations:
                        # Copy conversation
                        new_conv = models.Conversation(
                            id=conv.id,
                            project_id=conv.project_id,
                            title=conv.title,
                            created_at=conv.created_at
                        )
                        proj_session.add(new_conv)
                        proj_session.flush()
                        
                        # Copy chats
                        chats = session.exec(
                            select(models.Chat)
                            .where(models.Chat.conversation_id == conv.id)
                        ).all()
                        
                        for chat in chats:
                            new_chat = models.Chat(
                                id=chat.id,
                                conversation_id=chat.conversation_id,
                                user=chat.user,
                                message=chat.message,
                                ai_response=chat.ai_response,
                                created_at=chat.created_at,
                                context_file_ids=chat.context_file_ids,
                                files_modified=getattr(chat, 'files_modified', None)
                            )
                            proj_session.add(new_chat)
                        
                        # Copy attachments
                        attachments = session.exec(
                            select(models.Attachment)
                            .where(models.Attachment.conversation_id == conv.id)
                        ).all()
                        
                        for att in attachments:
                            new_att = models.Attachment(
                                id=att.id,
                                conversation_id=att.conversation_id,
                                filename=att.filename,
                                original_filename=att.original_filename,
                                content=att.content,
                                mime_type=att.mime_type,
                                size_bytes=att.size_bytes,
                                status=att.status,
                                version=att.version,
                                parent_file_id=att.parent_file_id,
                                created_at=att.created_at,
                                updated_at=att.updated_at,
                                modification_summary=att.modification_summary,
                                import_source=getattr(att, 'import_source', None),
                                import_metadata=getattr(att, 'import_metadata', None)
                            )
                            proj_session.add(new_att)
                        
                        print(f"    ✓ Copied: {conv.title} ({len(chats)} chats, {len(attachments)} files)")
                    
                    proj_session.commit()
                
                print(f"  ✅ Successfully migrated project: {project.name}")
                
            except Exception as e:
                print(f"  ❌ Error migrating project {project.name}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        print(f"\n{'='*60}")
        print("✅ MIGRATION COMPLETE")
        print(f"{'='*60}\n")
        print("Next steps:")
        print("  1. Verify data in new databases")
        print("  2. Test application functionality")
        print("  3. If all good, you can drop old conversation/chat/attachment tables")
        print("  4. Backup your database!")
        print()

if __name__ == "__main__":
    migrate()
