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
    """Get GitHub token from Replit connector or authorization header"""
    from app.services.replit_connector import get_github_access_token
    
    # First, try to get token from Replit connector
    try:
        github_token = await get_github_access_token()
        if github_token:
            return github_token
    except Exception as e:
        logger.debug(f"Replit connector not available: {e}")
    
    # Fallback to authorization header (legacy support)
    if authorization:
        try:
            scheme, token = authorization.split()
            if scheme.lower() == "bearer":
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
                github_token = payload.get("access_token")
                if github_token:
                    return github_token
        except (ValueError, JWTError) as e:
            logger.debug(f"Authorization header invalid: {e}")
    
    raise HTTPException(
        status_code=401, 
        detail="GitHub not connected. Please connect GitHub in the integrations panel."
    )

# ==================== CONVERSATION MANAGEMENT ====================

class ConversationCreate(BaseModel):
    title: Optional[str] = None
    first_message: Optional[str] = None

class ConversationNameRequest(BaseModel):
    conversation_id: Optional[int] = None  # Optional for backward compatibility
    message: Optional[str] = None

@router.post("/conversation", response_model=models.Conversation)
def new_conversation(
    request: ConversationCreate,
    session: Session = Depends(get_session)
):
    """Membuat percakapan baru dengan judul default atau custom"""
    title = request.title if request.title and request.title.strip() else "New Conversation"
    
    conv = models.Conversation(title=title.strip())
    session.add(conv)
    session.commit()
    session.refresh(conv)
    
    logger.info(f"Created conversation: {conv.id} - {conv.title}")
    return conv

@router.post("/conversation/auto-name")
async def generate_conversation_name(
    request: ConversationNameRequest,
    session: Session = Depends(get_session)
):
    """Generate conversation name using AI based on message or conversation messages"""
    try:
        from app.services.cerebras_chain import generate_conversation_title
        
        # Build messages list
        messages = []
        conversation_id = 0  # Default for simple title generation
        
        # Case 1: conversation_id provided - use existing messages from DB
        if request.conversation_id:
            conv = session.get(models.Conversation, request.conversation_id)
            if not conv:
                raise HTTPException(status_code=404, detail="Conversation not found")
            
            conversation_id = request.conversation_id
            
            # Get chats for this conversation
            chats = session.exec(
                select(models.Chat)
                .where(models.Chat.conversation_id == request.conversation_id)
                .order_by(models.Chat.created_at.asc())
            ).all()
            
            # If message provided in request, add it first
            if request.message:
                messages.append({"role": "user", "content": request.message})
            
            # Add existing chats
            for chat in chats:
                messages.append({"role": "user", "content": chat.user})
                if chat.ai_response:
                    messages.append({"role": "assistant", "content": chat.ai_response})
        
        # Case 2: Only message provided - simple title generation (legacy)
        elif request.message:
            messages.append({"role": "user", "content": request.message})
        
        # Need at least one message to generate title
        if not messages:
            return {
                "success": False,
                "title": "New Conversation",
                "error": "No messages available to generate title"
            }
        
        # ✅ Generate title with both arguments
        title = await generate_conversation_title(messages, conversation_id)
        
        # Update conversation title if conversation_id was provided
        if request.conversation_id:
            conv.title = title
            conv.updated_at = datetime.utcnow()
            session.add(conv)
            session.commit()
            
            logger.info(f"Generated and saved title for conversation {request.conversation_id}: {title}")
        else:
            logger.info(f"Generated title (not saved): {title}")
        
        return {
            "success": True,
            "title": title
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate conversation title: {e}")
        # Fallback to default title
        return {
            "success": False,
            "title": "New Conversation",
            "error": str(e)
        }

@router.get("/conversations", response_model=List[models.Conversation])
def list_conversations(session: Session = Depends(get_session)):
    """Menampilkan semua percakapan"""
    conversations = session.exec(
        select(models.Conversation).order_by(models.Conversation.updated_at.desc())
    ).all()
    return conversations

@router.delete("/conversation/{conv_id}")
def delete_conversation(
    conv_id: int,
    session: Session = Depends(get_session)
):
    """Menghapus sebuah percakapan beserta semua data terkait (cascade delete)"""
    conv = session.get(models.Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Cascade delete akan otomatis menghapus:
    # - Semua Chat
    # - Semua Attachment
    # - Semua DraftVersion
    session.delete(conv)
    session.commit()
    
    logger.info(f"Deleted conversation and all related data: {conv_id}")
    return {"ok": True, "message": "Conversation and all related data deleted"}

@router.patch("/conversation/{conv_id}")
def update_conversation(
    conv_id: int,
    title: str,
    session: Session = Depends(get_session)
):
    """Update conversation title"""
    conv = session.get(models.Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    conv.title = title.strip()
    conv.updated_at = datetime.utcnow()
    session.add(conv)
    session.commit()
    session.refresh(conv)
    
    logger.info(f"Updated conversation {conv_id} title to: {title}")
    return conv

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
