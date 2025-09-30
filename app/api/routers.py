from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile
from fastapi.responses import StreamingResponse, Response
from sqlmodel import Session, select
from typing import List
import logging
import io

from app.db import models
from app.db.database import get_session

logger = logging.getLogger(__name__)
router = APIRouter()

# ==================== PROJECT ====================
@router.post("/project", response_model=models.Project)
def create_project(name: str, session: Session = Depends(get_session)):
    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Project name required")
    project = models.Project(name=name.strip())
    session.add(project)
    session.commit()
    session.refresh(project)
    logger.info(f"✅ Created project: {project.id}")
    return project

@router.get("/projects", response_model=List[models.Project])
def list_projects(session: Session = Depends(get_session)):
    return session.exec(select(models.Project).order_by(models.Project.created_at.desc())).all()

@router.delete("/project/{project_id}")
def delete_project(project_id: int, session: Session = Depends(get_session)):
    project = session.get(models.Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    session.delete(project)
    session.commit()
    logger.info(f"🗑️ Deleted project: {project_id}")
    return {"ok": True}

# ==================== CONVERSATION ====================
@router.post("/conversation", response_model=models.Conversation)
def new_conversation(project_id: int, title: str, session: Session = Depends(get_session)):
    if not title or not title.strip():
        raise HTTPException(status_code=400, detail="Title required")
    project = session.get(models.Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    conv = models.Conversation(project_id=project_id, title=title.strip())
    session.add(conv)
    session.commit()
    session.refresh(conv)
    logger.info(f"✅ Created conversation: {conv.id}")
    return conv

@router.get("/project/{project_id}/conversations", response_model=List[models.Conversation])
def list_conversations(project_id: int, session: Session = Depends(get_session)):
    return session.exec(
        select(models.Conversation)
        .where(models.Conversation.project_id == project_id)
        .order_by(models.Conversation.created_at.desc())
    ).all()

@router.delete("/conversation/{conv_id}")
def delete_conversation(conv_id: int, session: Session = Depends(get_session)):
    conv = session.get(models.Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    session.delete(conv)
    session.commit()
    logger.info(f"🗑️ Deleted conversation: {conv_id}")
    return {"ok": True}

@router.get("/conversation/{conv_id}/chats", response_model=List[models.Chat])
def get_chats(conv_id: int, session: Session = Depends(get_session)):
    conv = session.get(models.Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return session.exec(
        select(models.Chat)
        .where(models.Chat.conversation_id == conv_id)
        .order_by(models.Chat.created_at.asc())
    ).all()

# ==================== ATTACHMENTS ====================
@router.post("/conversation/{conv_id}/attach", response_model=models.Attachment)
async def attach_file(conv_id: int, file: UploadFile = FastAPIFile(...), session: Session = Depends(get_session)):
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
        version=1
    )
    
    session.add(attachment)
    session.commit()
    session.refresh(attachment)
    logger.info(f"📎 Attached: {attachment.filename}")
    return attachment

@router.get("/conversation/{conv_id}/attachments", response_model=List[models.Attachment])
def list_attachments(conv_id: int, session: Session = Depends(get_session)):
    conv = session.get(models.Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Get all files with their latest versions
    latest_files = {}
    attachments = session.exec(
        select(models.Attachment)
        .where(models.Attachment.conversation_id == conv_id)
        .order_by(models.Attachment.created_at.desc(), models.Attachment.version.desc())
    ).all()
    
    for att in attachments:
        if att.filename not in latest_files:
            latest_files[att.filename] = att
    
    return list(latest_files.values())

@router.get("/attachment/{file_id}/download")
def download_attachment(file_id: int, session: Session = Depends(get_session)):
    attachment = session.get(models.Attachment, file_id)
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    
    return Response(
        content=attachment.content.encode('utf-8'),
        media_type=attachment.mime_type,
        headers={
            "Content-Disposition": f"attachment; filename={attachment.filename}",
            "Content-Length": str(attachment.size_bytes)
        }
    )

@router.delete("/attachment/{file_id}")
def delete_attachment(file_id: int, session: Session = Depends(get_session)):
    attachment = session.get(models.Attachment, file_id)
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    
    filename = attachment.filename
    conv_id = attachment.conversation_id
    
    # Delete all versions of this file
    all_versions = session.exec(
        select(models.Attachment)
        .where(models.Attachment.conversation_id == conv_id)
        .where(models.Attachment.filename == filename)
    ).all()
    
    for v in all_versions:
        session.delete(v)
    
    session.commit()
    logger.info(f"🗑️ Deleted: {filename} (all versions)")
    return {"ok": True}

@router.get("/attachment/{file_id}/versions", response_model=List[models.Attachment])
def get_file_versions(file_id: int, session: Session = Depends(get_session)):
    attachment = session.get(models.Attachment, file_id)
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    
    return session.exec(
        select(models.Attachment)
        .where(models.Attachment.conversation_id == attachment.conversation_id)
        .where(models.Attachment.filename == attachment.filename)
        .order_by(models.Attachment.version.desc())
    ).all()
