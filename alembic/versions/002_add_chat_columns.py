"""Add context_file_ids and files_modified to chat table

Revision ID: 002
Revises: 001
Create Date: 2025-09-30 16:15:00
"""
from alembic import op
import sqlalchemy as sa

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None

def upgrade():
    """Add missing columns to chat table"""
    
    # Check if columns exist before adding
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # Get existing columns in chat table
    columns = [col['name'] for col in inspector.get_columns('chat')]
    
    # Add context_file_ids if not exists
    if 'context_file_ids' not in columns:
        print("Adding context_file_ids column...")
        op.add_column('chat', 
            sa.Column('context_file_ids', sa.String(), nullable=True)
        )
        print("✅ context_file_ids column added")
    else:
        print("✅ context_file_ids column already exists")
    
    # Add files_modified if not exists
    if 'files_modified' not in columns:
        print("Adding files_modified column...")
        op.add_column('chat', 
            sa.Column('files_modified', sa.String(), nullable=True)
        )
        print("✅ files_modified column added")
    else:
        print("✅ files_modified column already exists")

def downgrade():
    """Remove the added columns"""
    op.drop_column('chat', 'files_modified')
    op.drop_column('chat', 'context_file_ids')
