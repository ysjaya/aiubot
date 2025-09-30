# app/db/models.py
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, ForeignKey, Integer, String, Text, DateTime, Enum as SQLEnum
from typing import Optional, List
from datetime import datetime
from enum import Enum

class FileStatus(str, Enum):
    ORIGINAL = "original"      # File dari import GitHub
    MODIFIED = "modified"      # File hasil edit AI (draft)
    LATEST = "latest"          # File aktif terbaru, yang digunakan AI & commit

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
    id: Optional[int] = Field(default=None, primary_key=True)
    conversation_id: int = Field(foreign_key="conversation.id")
    project_id: int = Field(foreign_key="project.id")
    filename: str
    file_path: str = Field(default="")
    content: Optional[str] = Field(sa_column=Column(Text))
    status: FileStatus = Field(sa_column=Column(SQLEnum(FileStatus), default=FileStatus.ORIGINAL))
    created_at: datetime = Field(default_factory=datetime.utcnow)
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
    
