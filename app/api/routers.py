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
from app.db.database import (
    get_session, create_project_database, 
    delete_project_database, get_project_session
)
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

class ImportReposRequest(BaseModel):
    project_id: int
    repos: List[str]

async def get_github_token(authorization: Optional[str] = Header(None)):
    """Extract and validate GitHub token from Authorization header"""
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
    """Create a new project with isolated database"""
    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Project name is required")
    
    try:
        # Create isolated database
        db_name = create_project_database(name.strip())
        
        # Create project record
        project = models.Project(
            name=name.strip(),
            database_name=db_name
        )
        session.add(project)
        session.commit()
        session.refresh(project)
        
        logger.info(f"Created project: {project.id} - {project.name} (DB: {db_name})")
        return project
        
    except Exception as e:
        logger.error(f"Failed to create project: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(e)}")

@router.get("/projects", response_model=List[models.Project])
def list_projects(session: Session = Depends(get_session)):
    """List all projects"""
    projects = session.exec(
        select(models.Project).order_by(models.Project.created_at.desc())
    ).all()
    return projects

@router.delete("/project/{project_id}")
def delete_project(project_id: int, session: Session = Depends(get_session)):
    """Delete a project and its isolated database"""
    project = session.get(models.Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    try:
        # Delete isolated database
        delete_project_database(project.database_name)
        
        # Delete project record
        session.delete(project)
        session.commit()
        
        logger.info(f"Deleted project: {project_id} and database: {project.database_name}")
        return {"ok": True, "message": f"Project and database deleted"}
        
    except Exception as e:
        logger.error(f"Failed to delete project: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete project: {str(e)}")

# ==================== CONVERSATION MANAGEMENT ====================

@router.post("/conversation", response_model=models.Conversation)
def new_conversation(
    project_id: int, 
    title: str, 
    session: Session = Depends(get_session)
):
    """Create a new conversation in a project"""
    if not title or not title.strip():
        raise HTTPException(status_code=400, detail="Conversation title is required")
    
    project = session.get(models.Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Use project's isolated database
    with next(get_project_session(project.database_name)) as proj_session:
        conv = models.Conversation(project_id=project_id, title=title.strip())
        proj_session.add(conv)
        proj_session.commit()
        proj_session.refresh(conv)
        logger.info(f"Created conversation: {conv.id} - {conv.title}")
        return conv

@router.get("/project/{project_id}/conversations", response_model=List[models.Conversation])
def list_conversations(
    project_id: int, 
    session: Session = Depends(get_session)
):
    """List all conversations in a project"""
    project = session.get(models.Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    with next(get_project_session(project.database_name)) as proj_session:
        conversations = proj_session.exec(
            select(models.Conversation)
            .where(models.Conversation.project_id == project_id)
            .order_by(models.Conversation.created_at.desc())
        ).all()
        return conversations

@router.delete("/conversation/{conv_id}")
def delete_conversation(
    conv_id: int,
    project_id: int,
    session: Session = Depends(get_session)
):
    """Delete a conversation"""
    project = session.get(models.Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    with next(get_project_session(project.database_name)) as proj_session:
        conv = proj_session.get(models.Conversation, conv_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        proj_session.delete(conv)
        proj_session.commit()
        logger.info(f"Deleted conversation: {conv_id}")
        return {"ok": True}

@router.get("/conversation/{conv_id}/chats", response_model=List[models.Chat])
def get_chats(
    conv_id: int,
    project_id: int,
    session: Session = Depends(get_session)
):
    """Get all chats in a conversation"""
    project = session.get(models.Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    with next(get_project_session(project.database_name)) as proj_session:
        conv = proj_session.get(models.Conversation, conv_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        chats = proj_session.exec(
            select(models.Chat)
            .where(models.Chat.conversation_id == conv_id)
            .order_by(models.Chat.created_at.asc())
        ).all()
        return chats

# ==================== ATTACHMENT MANAGEMENT ====================

@router.post("/conversation/{conv_id}/attach", response_model=models.Attachment)
async def attach_file(
    conv_id: int,
    project_id: int,
    file: UploadFile = FastAPIFile(...),
    session: Session = Depends(get_session)
):
    """Attach a file to conversation (Claude-style)"""
    project = session.get(models.Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    with next(get_project_session(project.database_name)) as proj_session:
        conv = proj_session.get(models.Conversation, conv_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Read file content
        content_bytes = await file.read()
        
        # Try to decode as text
        try:
            content = content_bytes.decode('utf-8')
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="File must be UTF-8 text")
        
        # Check file size (max 1MB)
        if len(content_bytes) > 1_000_000:
            raise HTTPException(status_code=400, detail="File too large (max 1MB)")
        
        # Create attachment
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
        
        proj_session.add(attachment)
        proj_session.commit()
        proj_session.refresh(attachment)
        
        logger.info(f"Attached file: {attachment.id} - {attachment.filename} to conv {conv_id}")
        return attachment

@router.get("/conversation/{conv_id}/attachments", response_model=List[models.Attachment])
def list_attachments(
    conv_id: int,
    project_id: int,
    session: Session = Depends(get_session)
):
    """List all attachments in a conversation"""
    project = session.get(models.Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    with next(get_project_session(project.database_name)) as proj_session:
        conv = proj_session.get(models.Conversation, conv_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Get latest version of each unique file
        attachments = proj_session.exec(
            select(models.Attachment)
            .where(models.Attachment.conversation_id == conv_id)
            .where(models.Attachment.status == models.FileStatus.LATEST)
            .order_by(models.Attachment.updated_at.desc())
        ).all()
        
        # If no LATEST, get ORIGINAL
        if not attachments:
            attachments = proj_session.exec(
                select(models.Attachment)
                .where(models.Attachment.conversation_id == conv_id)
                .where(models.Attachment.status == models.FileStatus.ORIGINAL)
                .order_by(models.Attachment.created_at.desc())
            ).all()
        
        return attachments

@router.get("/attachment/{file_id}/download")
def download_attachment(
    file_id: int,
    project_id: int,
    session: Session = Depends(get_session)
):
    """Download a file attachment"""
    project = session.get(models.Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    with next(get_project_session(project.database_name)) as proj_session:
        attachment = proj_session.get(models.Attachment, file_id)
        if not attachment:
            raise HTTPException(status_code=404, detail="Attachment not found")
        
        # Create file stream
        file_stream = io.BytesIO(attachment.content.encode('utf-8'))
        
        # Determine filename with status
        status_prefix = {
            models.FileStatus.ORIGINAL: "",
            models.FileStatus.MODIFIED: "modified_",
            models.FileStatus.LATEST: "latest_"
        }.get(attachment.status, "")
        
        filename = f"{status_prefix}{attachment.filename}"
        
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
    project_id: int,
    session: Session = Depends(get_session)
):
    """Delete a file attachment and all its versions"""
    project = session.get(models.Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    with next(get_project_session(project.database_name)) as proj_session:
        attachment = proj_session.get(models.Attachment, file_id)
        if not attachment:
            raise HTTPException(status_code=404, detail="Attachment not found")
        
        # Delete all versions related to this file
        if attachment.parent_file_id is None:
            # This is an original file, delete all its children
            children = proj_session.exec(
                select(models.Attachment)
                .where(models.Attachment.parent_file_id == file_id)
            ).all()
            for child in children:
                proj_session.delete(child)
        
        proj_session.delete(attachment)
        proj_session.commit()
        
        logger.info(f"Deleted attachment: {file_id}")
        return {"ok": True}

@router.get("/attachment/{file_id}/versions", response_model=List[models.Attachment])
def get_file_versions(
    file_id: int,
    project_id: int,
    session: Session = Depends(get_session)
):
    """Get all versions of a file"""
    project = session.get(models.Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    with next(get_project_session(project.database_name)) as proj_session:
        attachment = proj_session.get(models.Attachment, file_id)
        if not attachment:
            raise HTTPException(status_code=404, detail="Attachment not found")
        
        # Find root file
        root_id = attachment.parent_file_id if attachment.parent_file_id else attachment.id
        
        # Get all versions
        versions = proj_session.exec(
            select(models.Attachment)
            .where(
                (models.Attachment.id == root_id) | 
                (models.Attachment.parent_file_id == root_id)
            )
            .order_by(models.Attachment.version.desc())
        ).all()
        
        return versions

@router.post("/attachment/{file_id}/update", response_model=models.Attachment)
def update_attachment_content(
    file_id: int,
    project_id: int,
    content: str,
    modification_summary: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """Update file content and create new version (used by AI)"""
    project = session.get(models.Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    with next(get_project_session(project.database_name)) as proj_session:
        original = proj_session.get(models.Attachment, file_id)
        if not original:
            raise HTTPException(status_code=404, detail="Attachment not found")
        
        # Mark old LATEST as MODIFIED
        old_latest = proj_session.exec(
            select(models.Attachment)
            .where(models.Attachment.conversation_id == original.conversation_id)
            .where(models.Attachment.filename == original.filename)
            .where(models.Attachment.status == models.FileStatus.LATEST)
        ).first()
        
        if old_latest:
            old_latest.status = models.FileStatus.MODIFIED
            proj_session.add(old_latest)
        
        # Find root file
        root_id = original.parent_file_id if original.parent_file_id else original.id
        
        # Get max version
        max_version = proj_session.exec(
            select(models.Attachment)
            .where(
                (models.Attachment.id == root_id) | 
                (models.Attachment.parent_file_id == root_id)
            )
        ).all()
        next_version = max([f.version for f in max_version]) + 1 if max_version else 2
        
        # Create new version
        new_attachment = models.Attachment(
            conversation_id=original.conversation_id,
            filename=original.filename,
            original_filename=original.original_filename,
            content=content,
            mime_type=original.mime_type,
            size_bytes=len(content.encode('utf-8')),
            status=models.FileStatus.LATEST,
            version=next_version,
            parent_file_id=root_id,
            modification_summary=modification_summary or "AI-generated update",
            import_source=original.import_source,
            import_metadata=json.dumps({
                "updated_at": datetime.utcnow().isoformat(),
                "updated_from_version": original.version
            })
        )
        
        proj_session.add(new_attachment)
        proj_session.commit()
        proj_session.refresh(new_attachment)
        
        logger.info(f"Updated attachment: {new_attachment.id} (v{next_version}) - {new_attachment.filename}")
        return new_attachment

@router.get("/attachment/{file_id}/content")
def get_attachment_content(
    file_id: int,
    project_id: int,
    session: Session = Depends(get_session)
):
    """Get raw file content (for AI processing)"""
    project = session.get(models.Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    with next(get_project_session(project.database_name)) as proj_session:
        attachment = proj_session.get(models.Attachment, file_id)
        if not attachment:
            raise HTTPException(status_code=404, detail="Attachment not found")
        
        return {
            "id": attachment.id,
            "filename": attachment.filename,
            "content": attachment.content,
            "version": attachment.version,
            "status": attachment.status,
            "size_bytes": attachment.size_bytes,
            "modification_summary": attachment.modification_summary
        }
