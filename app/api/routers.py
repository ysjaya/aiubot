from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile, Header
from sqlmodel import Session, select
from typing import List, Optional
from jose import jwt, JWTError
from datetime import datetime
from pydantic import BaseModel
import logging

from app.db import models
from app.db.database import get_session
from app.services import github_import
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

@router.post("/project", response_model=models.Project)
def create_project(name: str, session: Session = Depends(get_session)):
    """Create a new project"""
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
    """List all projects"""
    projects = session.exec(select(models.Project).order_by(models.Project.created_at.desc())).all()
    return projects

@router.delete("/project/{project_id}")
def delete_project(project_id: int, session: Session = Depends(get_session)):
    """Delete a project and all its conversations and files"""
    project = session.get(models.Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    conversations = session.exec(select(models.Conversation).where(models.Conversation.project_id == project_id)).all()
    for conv in conversations:
        chats = session.exec(select(models.Chat).where(models.Chat.conversation_id == conv.id)).all()
        for chat in chats:
            session.delete(chat)
        session.delete(conv)
    
    files = session.exec(select(models.File).where(models.File.project_id == project_id)).all()
    for file in files:
        session.delete(file)
    
    session.delete(project)
    session.commit()
    logger.info(f"Deleted project: {project_id}")
    return {"ok": True}

@router.post("/conversation", response_model=models.Conversation)
def new_conversation(project_id: int, title: str, session: Session = Depends(get_session)):
    """Create a new conversation in a project"""
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
def list_conversations(project_id: int, session: Session = Depends(get_session)):
    """List all conversations in a project"""
    conversations = session.exec(
        select(models.Conversation)
        .where(models.Conversation.project_id == project_id)
        .order_by(models.Conversation.created_at.desc())
    ).all()
    return conversations

@router.delete("/conversation/{conv_id}")
def delete_conversation(conv_id: int, session: Session = Depends(get_session)):
    """Delete a conversation and all its chats"""
    conv = session.get(models.Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    chats = session.exec(select(models.Chat).where(models.Chat.conversation_id == conv_id)).all()
    for chat in chats:
        session.delete(chat)
    
    session.delete(conv)
    session.commit()
    logger.info(f"Deleted conversation: {conv_id}")
    return {"ok": True}

@router.get("/conversation/{conv_id}/chats", response_model=List[models.Chat])
def get_chats(conv_id: int, session: Session = Depends(get_session)):
    """Get all chats in a conversation"""
    conv = session.get(models.Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    chats = session.exec(
        select(models.Chat)
        .where(models.Chat.conversation_id == conv_id)
        .order_by(models.Chat.created_at.asc())
    ).all()
    return chats

@router.post("/file/upload/{project_id}", response_model=models.File)
async def upload_file(
    project_id: int, 
    file: UploadFile = FastAPIFile(...), 
    session: Session = Depends(get_session)
):
    """Upload a file to a project"""
    project = session.get(models.Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    content_bytes = await file.read()
    
    try:
        content = content_bytes.decode('utf-8')
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be a valid UTF-8 text file")
    
    existing_file = session.exec(
        select(models.File)
        .where(models.File.project_id == project_id)
        .where(models.File.path == file.filename)
    ).first()
    
    if existing_file:
        existing_file.content = content
        existing_file.updated_at = datetime.utcnow()
        session.add(existing_file)
        session.commit()
        session.refresh(existing_file)
        logger.info(f"Updated file: {existing_file.id} - {existing_file.path}")
        return existing_file
    else:
        db_file = models.File(
            project_id=project_id, 
            path=file.filename, 
            content=content,
            updated_at=datetime.utcnow()
        )
        session.add(db_file)
        session.commit()
        session.refresh(db_file)
        logger.info(f"Created file: {db_file.id} - {db_file.path}")
        return db_file

@router.get("/project/{project_id}/files", response_model=List[models.File])
def get_project_files(project_id: int, session: Session = Depends(get_session)):
    """Get all files in a project"""
    project = session.get(models.Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    files = session.exec(
        select(models.File)
        .where(models.File.project_id == project_id)
        .order_by(models.File.path.asc())
    ).all()
    return files

@router.get("/github/repos")
def get_repos(token: str = Depends(get_github_token)):
    """Get user's GitHub repositories"""
    try:
        repos = github_import.get_user_repos(token)
        return repos
    except Exception as e:
        logger.error(f"Failed to get repos: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get repositories: {str(e)}")

@router.get("/github/repo-files")
def get_repo_files(repo_fullname: str, token: str = Depends(get_github_token)):
    """Get files in a GitHub repository"""
    try:
        files = github_import.list_files(repo_fullname, token)
        return files
    except Exception as e:
        logger.error(f"Failed to list files: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")

@router.post("/github/import-file", response_model=models.File)
def import_repo_file(
    project_id: int,
    repo_fullname: str,
    file_path: str,
    session: Session = Depends(get_session),
    token: str = Depends(get_github_token)
):
    """Import a file from GitHub repository"""
    project = session.get(models.Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    try:
        content = github_import.get_file_content(repo_fullname, file_path, token)
        
        existing_file = session.exec(
            select(models.File)
            .where(models.File.project_id == project_id)
            .where(models.File.path == file_path)
        ).first()
        
        if existing_file:
            existing_file.content = content
            existing_file.updated_at = datetime.utcnow()
            session.add(existing_file)
            session.commit()
            session.refresh(existing_file)
            logger.info(f"Updated imported file: {existing_file.id} - {existing_file.path}")
            return existing_file
        else:
            db_file = models.File(
                project_id=project_id, 
                path=file_path, 
                content=content, 
                updated_at=datetime.utcnow()
            )
            session.add(db_file)
            session.commit()
            session.refresh(db_file)
            logger.info(f"Created imported file: {db_file.id} - {db_file.path}")
            return db_file
    except Exception as e:
        logger.error(f"Failed to import file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to import file: {str(e)}")

@router.post("/github/import-repos")
def import_repos(
    request: ImportReposRequest,
    session: Session = Depends(get_session),
    token: str = Depends(get_github_token)
):
    """Import multiple repositories"""
    project = session.get(models.Project, request.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    try:
        total_files = 0
        for repo_fullname in request.repos:
            logger.info(f"Importing repository: {repo_fullname}")
            files_data = github_import.get_all_repo_files(repo_fullname, token)
            
            for file_data in files_data:
                file_path = f"{repo_fullname}/{file_data['path']}"
                
                existing_file = session.exec(
                    select(models.File)
                    .where(models.File.project_id == request.project_id)
                    .where(models.File.path == file_path)
                ).first()
                
                if existing_file:
                    existing_file.content = file_data['content']
                    existing_file.updated_at = datetime.utcnow()
                    session.add(existing_file)
                else:
                    db_file = models.File(
                        project_id=request.project_id,
                        path=file_path,
                        content=file_data['content'],
                        updated_at=datetime.utcnow()
                    )
                    session.add(db_file)
                
                total_files += 1
            
            session.commit()
            logger.info(f"Imported {len(files_data)} files from {repo_fullname}")
        
        return {"ok": True, "total_files": total_files, "repos_count": len(request.repos)}
        
    except Exception as e:
        logger.error(f"Failed to import repos: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to import repositories: {str(e)}")
