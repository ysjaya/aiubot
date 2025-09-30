from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, ForeignKey, Integer, String, Text, DateTime, Enum as SQLEnum
from typing import Optional, List
from datetime import datetime
from enum import Enum

class FileStatus(str, Enum):
    ORIGINAL = "original"
    MODIFIED = "modified"
    LATEST = "latest"

class Project(SQLModel, table=True):
    """Project with isolated database"""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    database_name: str = Field(unique=True, index=True)  # Isolated DB per project
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    conversations: List["Conversation"] = Relationship(
        back_populates="project",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )

class Conversation(SQLModel, table=True):
    """Conversation within a project"""
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(sa_column=Column(Integer, ForeignKey("project.id", ondelete="CASCADE")))
    title: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    project: Optional[Project] = Relationship(back_populates="conversations")
    chats: List["Chat"] = Relationship(
        back_populates="conversation",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    attachments: List["Attachment"] = Relationship(
        back_populates="conversation",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )

class Chat(SQLModel, table=True):
    """Chat messages with file context tracking"""
    id: Optional[int] = Field(default=None, primary_key=True)
    conversation_id: int = Field(sa_column=Column(Integer, ForeignKey("conversation.id", ondelete="CASCADE")))
    user: str
    message: str = Field(sa_column=Column(Text))
    ai_response: str = Field(sa_column=Column(Text))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Track which files were in context
    context_file_ids: Optional[str] = Field(default=None)  # JSON array of file IDs
    files_modified: Optional[str] = Field(default=None)  # JSON array of modified file IDs
    
    # Relationships
    conversation: Optional[Conversation] = Relationship(back_populates="chats")

class Attachment(SQLModel, table=True):
    """File attachments with versioning (Claude-style)"""
    id: Optional[int] = Field(default=None, primary_key=True)
    conversation_id: int = Field(sa_column=Column(Integer, ForeignKey("conversation.id", ondelete="CASCADE")))
    
    # File info
    filename: str = Field(index=True)
    original_filename: str  # Original name when uploaded
    content: str = Field(sa_column=Column(Text))
    mime_type: str = Field(default="text/plain")
    size_bytes: int
    
    # Versioning (Claude-style)
    status: FileStatus = Field(
        default=FileStatus.ORIGINAL,
        sa_column=Column(SQLEnum(FileStatus), nullable=False)
    )
    version: int = Field(default=1)
    parent_file_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("attachment.id", ondelete="SET NULL"))
    )
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    modification_summary: Optional[str] = Field(default=None, sa_column=Column(Text))
    
    # Import source tracking
    import_source: Optional[str] = Field(default=None)  # "github", "upload", "manual"
    import_metadata: Optional[str] = Field(default=None)  # JSON metadata
    
    # Relationships
    conversation: Optional[Conversation] = Relationship(back_populates="attachments")
    
    def get_display_status(self) -> str:
        """Get human-readable status badge"""
        status_map = {
            FileStatus.ORIGINAL: "📄 Original",
            FileStatus.MODIFIED: "✏️ Modified",
            FileStatus.LATEST: "✨ Latest"
        }
        return status_map.get(self.status, "📄")
    
    def get_short_summary(self) -> str:
        """Get short modification summary"""
        if not self.modification_summary:
            return ""
        return self.modification_summary[:100] + ("..." if len(self.modification_summary) > 100 else "")
