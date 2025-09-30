"""Remove database_name column from project table

Revision ID: 006
Revises: 005
Create Date: 2025-09-30 16:50:00
"""
from alembic import op
import sqlalchemy as sa

revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None

def upgrade():
    """Remove database_name column"""
    
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    print("\n" + "="*60)
    print("[MIGRATION 006] Remove database_name column")
    print("="*60)
    
    # Check if column exists
    columns = [col['name'] for col in inspector.get_columns('project')]
    
    if 'database_name' in columns:
        print("  Removing database_name column...")
        
        try:
            # Drop index if exists
            indexes = [idx['name'] for idx in inspector.get_indexes('project')]
            if 'ix_project_database_name' in indexes:
                op.drop_index('ix_project_database_name', table_name='project')
                print("  ✅ Dropped index: ix_project_database_name")
        except Exception as e:
            print(f"  ⚠️  Could not drop index: {e}")
        
        # Drop column
        op.drop_column('project', 'database_name')
        print("  ✅ Removed database_name column")
    else:
        print("  ✅ Column already removed")
    
    print("="*60 + "\n")

def downgrade():
    """Add back database_name column"""
    op.add_column('project', 
        sa.Column('database_name', sa.String(), nullable=True)
    )
    op.create_index('ix_project_database_name', 'project', 
                   ['database_name'], unique=True)
