# app/db/models.py
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, ForeignKey, Integer, String, Text, DateTime, Enum as SQLEnum
from typing import Optional, List
from datetime import datetime
from enum import Enum
import hashlib

class FileStatus(str, Enum):
    ORIGINAL = "original"      # File dari import GitHub
    MODIFIED = "modified"      # File hasil edit AI (draft)
    LATEST = "latest"          # File aktif terbaru, yang digunakan AI & commit

class DraftStatus(str, Enum):
    PENDING = "pending"        # Draft baru, belum di-review
    APPROVED = "approved"      # Draft sudah di-review dan siap commit
    REJECTED = "rejected"      # Draft ditolak
    PROMOTED = "promoted"      # Draft sudah dipromosikan jadi LATEST

class Project(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    conversations: List["Conversation"] = Relationship(back_populates="project")

class Conversation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id")
    title: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    project: Optional[Project] = Relationship(back_populates="conversations")
    chats: List["Chat"] = Relationship(back_populates="conversation")
    attachments: List["Attachment"] = Relationship(back_populates="conversation")
    drafts: List["DraftVersion"] = Relationship(back_populates="conversation")

class Chat(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    conversation_id: int = Field(foreign_key="conversation.id")
    user: str
    message: str = Field(sa_column=Column(Text))
    ai_response: str = Field(sa_column=Column(Text))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    context_file_ids: Optional[str] = None
    files_modified: Optional[str] = None
    
    conversation: Optional[Conversation] = Relationship(back_populates="chats")

class Attachment(SQLModel, table=True):
    """File yang sudah di-approve dan siap digunakan AI atau di-commit"""
    id: Optional[int] = Field(default=None, primary_key=True)
    conversation_id: int = Field(foreign_key="conversation.id")
    project_id: int = Field(foreign_key="project.id")
    
    # File info
    filename: str
    original_filename: Optional[str] = None
    file_path: str = Field(default="")
    
    # Content
    content: Optional[str] = Field(sa_column=Column(Text))
    content_hash: Optional[str] = None  # SHA256 hash untuk validasi
    mime_type: Optional[str] = "text/plain"
    size_bytes: Optional[int] = 0
    
    # Versioning
    status: FileStatus = Field(sa_column=Column(SQLEnum(FileStatus), default=FileStatus.ORIGINAL))
    version: int = Field(default=1)
    parent_file_id: Optional[int] = None  # ID dari versi sebelumnya
    
    # Metadata
    modification_summary: Optional[str] = Field(sa_column=Column(Text), default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Import info
    import_source: Optional[str] = None
    import_metadata: Optional[str] = None
    
    conversation: Optional[Conversation] = Relationship(back_populates="attachments")

    def get_display_status(self) -> str:
        status_map = {
            FileStatus.ORIGINAL: "📄 Original",
            FileStatus.MODIFIED: "✏️ Modified",
            FileStatus.LATEST: "✨ Latest"
        }
        return status_map.get(self.status, "📄")
    
    def get_short_summary(self) -> str:
        if not self.modification_summary:
            return ""
        return self.modification_summary[:100] + ("..." if len(self.modification_summary) > 100 else "")
    
    def compute_content_hash(self) -> str:
        """Hitung SHA256 hash dari content"""
        if self.content:
            return hashlib.sha256(self.content.encode('utf-8')).hexdigest()
        return ""

class DraftVersion(SQLModel, table=True):
    """Draft file yang dihasilkan AI sebelum di-approve"""
    id: Optional[int] = Field(default=None, primary_key=True)
    conversation_id: int = Field(foreign_key="conversation.id")
    project_id: int = Field(foreign_key="project.id")
    
    # File reference
    filename: str = Field(index=True)
    original_filename: Optional[str] = None
    attachment_id: Optional[int] = None  # Link ke Attachment yang sedang diedit
    
    # Content - SELALU LENGKAP 100%
    content: str = Field(sa_column=Column(Text))  # WAJIB LENGKAP, TIDAK BOLEH TRUNCATED
    content_hash: str  # SHA256 hash untuk validasi integritas
    content_length: int  # Jumlah karakter untuk validasi
    
    # Versioning
    version_number: int = Field(default=1)
    status: DraftStatus = Field(sa_column=Column(SQLEnum(DraftStatus), default=DraftStatus.PENDING))
    
    # Validation flags
    is_complete: bool = Field(default=True)  # Flag apakah kode lengkap (tidak ada ...)
    has_syntax_errors: bool = Field(default=False)  # Flag error syntax
    completeness_score: float = Field(default=1.0)  # Score 0-1 untuk kelengkapan
    
    # Metadata
    change_summary: Optional[str] = Field(sa_column=Column(Text))
    change_details: Optional[str] = Field(sa_column=Column(Text))  # JSON list perubahan
    ai_model: Optional[str] = "cerebras"
    generation_metadata: Optional[str] = Field(sa_column=Column(Text))  # JSON metadata
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    reviewed_at: Optional[datetime] = None
    promoted_at: Optional[datetime] = None
    
    # Relations
    conversation: Optional[Conversation] = Relationship(back_populates="drafts")
    
    def get_display_status(self) -> str:
        status_map = {
            DraftStatus.PENDING: "⏳ Pending Review",
            DraftStatus.APPROVED: "✅ Approved",
            DraftStatus.REJECTED: "❌ Rejected",
            DraftStatus.PROMOTED: "✨ Promoted"
        }
        return status_map.get(self.status, "⏳")
    
    def validate_completeness(self) -> bool:
        """Validasi apakah kode benar-benar lengkap"""
        if not self.content:
            return False
        
        # Check untuk marker truncation
        truncation_markers = [
            '...',
            '# ... rest of code',
            '// ... rest of code',
            '/* ... */',
            '# kode lainnya',
            '// kode lainnya',
            '[truncated]',
            '[continued]'
        ]
        
        content_lower = self.content.lower()
        for marker in truncation_markers:
            if marker.lower() in content_lower:
                return False
        
        # Check minimum length (kode lengkap minimal 50 karakter)
        if len(self.content) < 50:
            return False
        
        return True
    
    def compute_hash(self) -> str:
        """Hitung hash dari content"""
        return hashlib.sha256(self.content.encode('utf-8')).hexdigest()
