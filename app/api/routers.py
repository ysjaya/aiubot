from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile, Header
from fastapi.responses import StreamingResponse, Response
from sqlmodel import Session, select
from typing import List, Optional
from jose import jwt, JWTError
from datetime import datetime
from pydantic import BaseModel
import logging
import json
import io

from app.db import models
from app.db.database import get_session
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

async def get_github_token(authorization: Optional[str] = Header(None)):
    """Mengekstrak dan memvalidasi token GitHub dari header Authorization"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authentication scheme")
        
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        github_token = payload.get("access_token")
        
        if not github_token:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        
        return github_token
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    except JWTError as e:
        logger.error(f"JWT decode error: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")

# ==================== PROJECT MANAGEMENT ====================

@router.post("/project", response_model=models.Project)
def create_project(name: str, session: Session = Depends(get_session)):
    """Membuat proyek baru"""
    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Project name is required")
    
    project = models.Project(name=name.strip())
    session.add(project)
    session.commit()
    session.refresh(project)
    
    logger.info(f"Created project: {project.id} - {project.name}")
    return project

@router.get("/projects", response_model=List[models.Project])
def list_projects(session: Session = Depends(get_session)):
    """Menampilkan semua proyek"""
    projects = session.exec(
        select(models.Project).order_by(models.Project.created_at.desc())
    ).all()
    return projects

@router.delete("/project/{project_id}")
def delete_project(project_id: int, session: Session = Depends(get_session)):
    """Menghapus proyek beserta semua data terkait"""
    project = session.get(models.Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    session.delete(project)
    session.commit()
    
    logger.info(f"Deleted project: {project_id}")
    return {"ok": True, "message": "Project and its data deleted"}

# ==================== CONVERSATION MANAGEMENT ====================

@router.post("/conversation", response_model=models.Conversation)
def new_conversation(
    project_id: int, 
    title: str, 
    session: Session = Depends(get_session)
):
    """Membuat percakapan baru dalam sebuah proyek"""
    if not title or not title.strip():
        raise HTTPException(status_code=400, detail="Conversation title is required")
    
    project = session.get(models.Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    conv = models.Conversation(project_id=project_id, title=title.strip())
    session.add(conv)
    session.commit()
    session.refresh(conv)
    logger.info(f"Created conversation: {conv.id} - {conv.title}")
    return conv

@router.get("/project/{project_id}/conversations", response_model=List[models.Conversation])
def list_conversations(
    project_id: int, 
    session: Session = Depends(get_session)
):
    """Menampilkan semua percakapan dalam sebuah proyek"""
    project = session.get(models.Project, project_id)
    if not project:
        return []
    
    conversations = session.exec(
        select(models.Conversation)
        .where(models.Conversation.project_id == project_id)
        .order_by(models.Conversation.created_at.desc())
    ).all()
    return conversations

@router.delete("/conversation/{conv_id}")
def delete_conversation(
    conv_id: int,
    session: Session = Depends(get_session)
):
    """Menghapus sebuah percakapan"""
    conv = session.get(models.Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    session.delete(conv)
    session.commit()
    logger.info(f"Deleted conversation: {conv_id}")
    return {"ok": True}

@router.get("/conversation/{conv_id}/chats", response_model=List[models.Chat])
def get_chats(
    conv_id: int,
    session: Session = Depends(get_session)
):
    """Mengambil semua chat dalam sebuah percakapan"""
    conv = session.get(models.Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    chats = session.exec(
        select(models.Chat)
        .where(models.Chat.conversation_id == conv_id)
        .order_by(models.Chat.created_at.asc())
    ).all()
    return chats

# ==================== ATTACHMENT MANAGEMENT ====================

@router.post("/conversation/{conv_id}/attach", response_model=models.Attachment)
async def attach_file(
    conv_id: int,
    file: UploadFile = FastAPIFile(...),
    session: Session = Depends(get_session)
):
    """Melampirkan file ke percakapan"""
    conv = session.get(models.Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    content_bytes = await file.read()
    
    try:
        content = content_bytes.decode('utf-8')
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 text")
    
    if len(content_bytes) > 1_000_000:
        raise HTTPException(status_code=400, detail="File too large (max 1MB)")
    
    attachment = models.Attachment(
        conversation_id=conv_id,
        filename=file.filename,
        original_filename=file.filename,
        content=content,
        mime_type=file.content_type or "text/plain",
        size_bytes=len(content_bytes),
        status=models.FileStatus.ORIGINAL,
        version=1,
        import_source="upload",
        import_metadata=json.dumps({"uploaded_at": datetime.utcnow().isoformat()})
    )
    
    session.add(attachment)
    session.commit()
    session.refresh(attachment)
    
    logger.info(f"Attached file: {attachment.id} - {attachment.filename} to conv {conv_id}")
    return attachment

@router.get("/conversation/{conv_id}/attachments", response_model=List[models.Attachment])
def list_attachments(
    conv_id: int,
    session: Session = Depends(get_session)
):
    """Menampilkan semua lampiran dalam sebuah percakapan"""
    conv = session.get(models.Conversation, conv_id)
    if not conv:
        return []
        
    attachments = session.exec(
        select(models.Attachment)
        .where(models.Attachment.conversation_id == conv_id)
        .where(models.Attachment.status == models.FileStatus.LATEST)
        .order_by(models.Attachment.updated_at.desc())
    ).all()
    
    if not attachments:
        attachments = session.exec(
            select(models.Attachment)
            .where(models.Attachment.conversation_id == conv_id)
            .where(models.Attachment.status == models.FileStatus.ORIGINAL)
            .order_by(models.Attachment.created_at.desc())
        ).all()
    
    return attachments

@router.get("/attachment/{file_id}/download")
def download_attachment(
    file_id: int,
    session: Session = Depends(get_session)
):
    """Mengunduh lampiran file"""
    attachment = session.get(models.Attachment, file_id)
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    
    file_stream = io.BytesIO(attachment.content.encode('utf-8'))
    
    filename = f"{attachment.filename}"
    
    return StreamingResponse(
        file_stream,
        media_type=attachment.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(attachment.size_bytes)
        }
    )

@router.delete("/attachment/{file_id}")
def delete_attachment(
    file_id: int,
    session: Session = Depends(get_session)
):
    """Menghapus lampiran file dan semua versinya"""
    attachment = session.get(models.Attachment, file_id)
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    
    root_id = attachment.parent_file_id if attachment.parent_file_id else attachment.id
    
    versions_to_delete = session.exec(
        select(models.Attachment)
        .where((models.Attachment.id == root_id) | (models.Attachment.parent_file_id == root_id))
    ).all()

    for version in versions_to_delete:
        session.delete(version)
        
    session.commit()
    
    logger.info(f"Deleted attachment and all its versions: {file_id}")
    return {"ok": True}

@router.get("/attachment/{file_id}/versions", response_model=List[models.Attachment])
def get_file_versions(
    file_id: int,
    session: Session = Depends(get_session)
):
    """Mengambil semua versi dari sebuah file"""
    attachment = session.get(models.Attachment, file_id)
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    
    root_id = attachment.parent_file_id if attachment.parent_file_id else attachment.id
    
    versions = session.exec(
        select(models.Attachment)
        .where((models.Attachment.id == root_id) | (models.Attachment.parent_file_id == root_id))
        .order_by(models.Attachment.version.desc())
    ).all()
    
    return versions
