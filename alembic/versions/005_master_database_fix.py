"""Master database fix - Drop file table and ensure all columns exist

Revision ID: 005
Revises: 004
Create Date: 2025-09-30 16:35:00
"""
from alembic import op
import sqlalchemy as sa

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None

def upgrade():
    """Master fix for all database issues"""
    
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    print("\n" + "="*60)
    print("MASTER DATABASE FIX")
    print("="*60)
    
    # 1. Drop file table if exists
    tables = inspector.get_table_names()
    if 'file' in tables:
        print("\n[1/4] Dropping legacy 'file' table...")
        try:
            op.drop_table('file', if_exists=True)
            print("✅ Dropped 'file' table")
        except Exception as e:
            print(f"⚠️  Could not drop file table: {e}")
    else:
        print("\n[1/4] ✅ 'file' table does not exist (OK)")
    
    # 2. Fix attachment table
    print("\n[2/4] Checking attachment table...")
    att_columns = [col['name'] for col in inspector.get_columns('attachment')]
    
    if 'import_source' not in att_columns:
        print("  Adding import_source...")
        op.add_column('attachment', sa.Column('import_source', sa.String(), nullable=True))
        print("  ✅ Added import_source")
    else:
        print("  ✅ import_source exists")
    
    if 'import_metadata' not in att_columns:
        print("  Adding import_metadata...")
        op.add_column('attachment', sa.Column('import_metadata', sa.String(), nullable=True))
        print("  ✅ Added import_metadata")
    else:
        print("  ✅ import_metadata exists")
    
    # 3. Fix chat table
    print("\n[3/4] Checking chat table...")
    chat_columns = [col['name'] for col in inspector.get_columns('chat')]
    
    if 'context_file_ids' not in chat_columns:
        print("  Adding context_file_ids...")
        op.add_column('chat', sa.Column('context_file_ids', sa.String(), nullable=True))
        print("  ✅ Added context_file_ids")
    else:
        print("  ✅ context_file_ids exists")
    
    if 'files_modified' not in chat_columns:
        print("  Adding files_modified...")
        op.add_column('chat', sa.Column('files_modified', sa.String(), nullable=True))
        print("  ✅ Added files_modified")
    else:
        print("  ✅ files_modified exists")
    
    # 4. Summary
    print("\n[4/4] Verification...")
    final_tables = inspector.get_table_names()
    print(f"  Total tables: {len(final_tables)}")
    print(f"  Tables: {', '.join(sorted(final_tables))}")
    
    print("\n" + "="*60)
    print("✅ MASTER FIX COMPLETE")
    print("="*60 + "\n")

def downgrade():
    """Cannot revert master fix"""
    pass
