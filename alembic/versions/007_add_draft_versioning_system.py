"""add draft versioning system

Revision ID: 007
Revises: 006
Create Date: 2025-09-30 15:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade():
    # Buat koneksi untuk cek tabel/kolom yang ada
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = [col['name'] for col in inspector.get_columns('attachment')]
    
    # Add new fields to Attachment table (hanya jika belum ada)
    if 'original_filename' not in existing_columns:
        op.add_column('attachment', sa.Column('original_filename', sa.String(), nullable=True))
    if 'content_hash' not in existing_columns:
        op.add_column('attachment', sa.Column('content_hash', sa.String(), nullable=True))
    if 'mime_type' not in existing_columns:
        op.add_column('attachment', sa.Column('mime_type', sa.String(), nullable=True, server_default='text/plain'))
    if 'size_bytes' not in existing_columns:
        op.add_column('attachment', sa.Column('size_bytes', sa.Integer(), nullable=True, server_default='0'))
    if 'version' not in existing_columns:
        op.add_column('attachment', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
    if 'parent_file_id' not in existing_columns:
        op.add_column('attachment', sa.Column('parent_file_id', sa.Integer(), nullable=True))
    if 'modification_summary' not in existing_columns:
        op.add_column('attachment', sa.Column('modification_summary', sa.Text(), nullable=True))
    if 'updated_at' not in existing_columns:
        op.add_column('attachment', sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')))
    
    # Check if draftstatus enum already exists
    result = conn.execute(sa.text("SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'draftstatus')"))
    enum_exists = result.scalar()
    
    # Create DraftVersion table (skip jika sudah ada)
    existing_tables = inspector.get_table_names()
    if 'draftversion' not in existing_tables:
        # Create enum only if doesn't exist
        if not enum_exists:
            draftstatus_enum = postgresql.ENUM('PENDING', 'APPROVED', 'REJECTED', 'PROMOTED', name='draftstatus', create_type=True)
            draftstatus_enum.create(conn, checkfirst=True)
        
        op.create_table(
            'draftversion',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('conversation_id', sa.Integer(), nullable=False),
            sa.Column('project_id', sa.Integer(), nullable=False),
            sa.Column('filename', sa.String(), nullable=False),
            sa.Column('original_filename', sa.String(), nullable=True),
            sa.Column('attachment_id', sa.Integer(), nullable=True),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('content_hash', sa.String(), nullable=False),
            sa.Column('content_length', sa.Integer(), nullable=False),
            sa.Column('version_number', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('status', postgresql.ENUM('PENDING', 'APPROVED', 'REJECTED', 'PROMOTED', name='draftstatus', create_type=False), nullable=False, server_default='PENDING'),
            sa.Column('is_complete', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('has_syntax_errors', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('completeness_score', sa.Float(), nullable=False, server_default='1.0'),
            sa.Column('change_summary', sa.Text(), nullable=True),
            sa.Column('change_details', sa.Text(), nullable=True),
            sa.Column('ai_model', sa.String(), nullable=True, server_default='cerebras'),
            sa.Column('generation_metadata', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('reviewed_at', sa.DateTime(), nullable=True),
            sa.Column('promoted_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['conversation_id'], ['conversation.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['project_id'], ['project.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_draftversion_filename'), 'draftversion', ['filename'], unique=False)


def downgrade():
    # Drop DraftVersion table
    op.drop_index(op.f('ix_draftversion_filename'), table_name='draftversion')
    op.drop_table('draftversion')
    
    # Remove new fields from Attachment
    op.drop_column('attachment', 'updated_at')
    op.drop_column('attachment', 'modification_summary')
    op.drop_column('attachment', 'parent_file_id')
    op.drop_column('attachment', 'version')
    op.drop_column('attachment', 'size_bytes')
    op.drop_column('attachment', 'mime_type')
    op.drop_column('attachment', 'content_hash')
    op.drop_column('attachment', 'original_filename')
