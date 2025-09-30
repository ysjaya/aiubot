"""Add import_source and import_metadata to attachment table

Revision ID: 003
Revises: 002
Create Date: 2025-09-30 16:20:00
"""
from alembic import op
import sqlalchemy as sa

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None

def upgrade():
    """Add missing columns to attachment table"""
    
    # Check if columns exist before adding
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # Get existing columns in attachment table
    columns = [col['name'] for col in inspector.get_columns('attachment')]
    
    # Add import_source if not exists
    if 'import_source' not in columns:
        print("Adding import_source column...")
        op.add_column('attachment', 
            sa.Column('import_source', sa.String(), nullable=True)
        )
        print("✅ import_source column added")
    else:
        print("✅ import_source column already exists")
    
    # Add import_metadata if not exists
    if 'import_metadata' not in columns:
        print("Adding import_metadata column...")
        op.add_column('attachment', 
            sa.Column('import_metadata', sa.String(), nullable=True)
        )
        print("✅ import_metadata column added")
    else:
        print("✅ import_metadata column already exists")

def downgrade():
    """Remove the added columns"""
    op.drop_column('attachment', 'import_metadata')
    op.drop_column('attachment', 'import_source')
