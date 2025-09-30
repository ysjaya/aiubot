from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, Integer, ForeignKey
from typing import Optional, List
from datetime import datetime
from enum import Enum

class FileStatus(str, Enum):
    ORIGINAL = "original"
    MODIFIED = "modified"
    LATEST = "latest"

class Project(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    conversations: List["Conversation"] = Relationship(back_populates="project")

class Conversation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(sa_column=Column(Integer, ForeignKey("project.id", ondelete="CASCADE")))
    title: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    project: Optional[Project] = Relationship(back_populates="conversations")
    chats: List["Chat"] = Relationship(back_populates="conversation")
    attachments: List["Attachment"] = Relationship(back_populates="conversation")

class Chat(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    conversation_id: int = Field(sa_column=Column(Integer, ForeignKey("conversation.id", ondelete="CASCADE")))
    user: str
    message: str
    ai_response: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    context_file_ids: Optional[str] = Field(default=None)
    conversation: Optional[Conversation] = Relationship(back_populates="chats")

class Attachment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    conversation_id: int = Field(sa_column=Column(Integer, ForeignKey("conversation.id", ondelete="CASCADE")))
    filename: str
    original_filename: str
    content: str
    mime_type: str = Field(default="text/plain")
    size_bytes: int
    status: FileStatus = Field(default=FileStatus.ORIGINAL)
    version: int = Field(default=1)
    parent_file_id: Optional[int] = Field(default=None, sa_column=Column(Integer, ForeignKey("attachment.id", ondelete="SET NULL")))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    modification_summary: Optional[str] = Field(default=None)
    conversation: Optional[Conversation] = Relationship(back_populates="attachments")
    
    def get_display_status(self) -> str:
        status_map = {
            FileStatus.ORIGINAL: "📄 Original",
            FileStatus.MODIFIED: "✏️ Modified",
            FileStatus.LATEST: "✨ Latest"
        }
        return status_map.get(self.status, "📄")
