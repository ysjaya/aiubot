"""Fix file table foreign key to use CASCADE DELETE

Revision ID: 004
Revises: 003
Create Date: 2025-09-30 16:30:00
"""
from alembic import op
import sqlalchemy as sa

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None

def upgrade():
    """Add CASCADE DELETE to file foreign key"""
    
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # Check if file table exists
    tables = inspector.get_table_names()
    
    if 'file' in tables:
        print("⚠️  Found 'file' table, fixing foreign key...")
        
        # Drop old constraint
        try:
            op.drop_constraint('file_project_id_fkey', 'file', type_='foreignkey')
            print("✅ Dropped old constraint")
        except Exception as e:
            print(f"⚠️  Could not drop constraint: {e}")
        
        # Add new constraint with CASCADE
        try:
            op.create_foreign_key(
                'file_project_id_fkey',
                'file', 'project',
                ['project_id'], ['id'],
                ondelete='CASCADE'
            )
            print("✅ Added CASCADE DELETE constraint")
        except Exception as e:
            print(f"❌ Failed to add constraint: {e}")
    else:
        print("✅ 'file' table does not exist (OK)")

def downgrade():
    """Revert to original constraint"""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    
    if 'file' in tables:
        op.drop_constraint('file_project_id_fkey', 'file', type_='foreignkey')
        op.create_foreign_key(
            'file_project_id_fkey',
            'file', 'project',
            ['project_id'], ['id']
  )
