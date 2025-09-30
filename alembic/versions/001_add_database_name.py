"""Add database_name column to project

Revision ID: 001
Revises: 
Create Date: 2025-09-30 05:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Check if column exists
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('project')]
    
    if 'database_name' not in columns:
        print("Adding database_name column...")
        
        # Add column
        op.add_column('project', 
            sa.Column('database_name', sa.String(), nullable=True)
        )
        
        # Update existing rows
        conn.execute(sa.text("""
            UPDATE project 
            SET database_name = 'project_' || 
                LOWER(REPLACE(REPLACE(name, ' ', '_'), '-', '_')) || '_' || 
                TO_CHAR(created_at, 'YYYYMMDD_HH24MISS')
            WHERE database_name IS NULL
        """))
        
        # Create unique index
        op.create_index('ix_project_database_name', 'project', 
                       ['database_name'], unique=True)
        
        # Make non-nullable
        op.alter_column('project', 'database_name', nullable=False)
        
        print("✅ database_name column added successfully")
    else:
        print("✅ database_name column already exists")

def downgrade():
    op.drop_index('ix_project_database_name', table_name='project')
    op.drop_column('project', 'database_name')
