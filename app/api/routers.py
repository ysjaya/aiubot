from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile, Header
from sqlmodel import Session, select, delete
from typing import List, Optional
from jose import jwt, JWTError
from datetime import datetime

from app.db import models
from app.db.database import get_session
from app.services import github_import
from app.core.config import settings

router = APIRouter()

# --- Helper Otentikasi ---
async def get_github_token(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authentication scheme")
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload.get("access_token")
    except (ValueError, JWTError):
        raise HTTPException(status_code=401, detail="Invalid token")

# === Project Routes ===
@router.post("/project", response_model=models.Project)
def create_project(name: str, session: Session = Depends(get_session)):
    project = models.Project(name=name)
    session.add(project)
    session.commit()
    session.refresh(project)
    return project

@router.get("/projects", response_model=List[models.Project])
def list_projects(session: Session = Depends(get_session)):
    return session.exec(select(models.Project)).all()

@router.delete("/project/{project_id}")
def delete_project(project_id: int, session: Session = Depends(get_session)):
    project = session.get(models.Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    session.delete(project)
    session.commit()
    return {"ok": True}

# === Conversation Routes ===
@router.post("/conversation", response_model=models.Conversation)
def new_conversation(project_id: int, title: str, session: Session = Depends(get_session)):
    conv = models.Conversation(project_id=project_id, title=title)
    session.add(conv)
    session.commit()
    session.refresh(conv)
    return conv

@router.get("/project/{project_id}/conversations", response_model=List[models.Conversation])
def list_conversations(project_id: int, session: Session = Depends(get_session)):
    return session.exec(select(models.Conversation).where(models.Conversation.project_id == project_id)).all()

@router.delete("/conversation/{conv_id}")
def delete_conversation(conv_id: int, session: Session = Depends(get_session)):
    conv = session.get(models.Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    session.delete(conv)
    session.commit()
    return {"ok": True}

# === Chat Routes ===
@router.get("/conversation/{conv_id}/chats", response_model=List[models.Chat])
def get_chats(conv_id: int, session: Session = Depends(get_session)):
    return session.exec(select(models.Chat).where(models.Chat.conversation_id == conv_id)).all()

# === File Routes ===
@router.post("/file/upload/{project_id}", response_model=models.File)
async def upload_file(
    project_id: int, 
    file: UploadFile = FastAPIFile(...), 
    session: Session = Depends(get_session)
):
    content_bytes = await file.read()
    try:
        content = content_bytes.decode('utf-8')
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File is not a valid UTF-8 text file.")
    
    db_file = models.File(
        project_id=project_id, 
        path=file.filename, 
        content=content,
        updated_at=datetime.utcnow()
    )
    session.add(db_file)
    session.commit()
    session.refresh(db_file)
    return db_file

@router.get("/project/{project_id}/files", response_model=List[models.File])
def get_project_files(project_id: int, session: Session = Depends(get_session)):
    return session.exec(select(models.File).where(models.File.project_id == project_id)).all()

# === GitHub Routes ===
@router.get("/github/repos")
def get_repos(token: str = Depends(get_github_token)):
    return github_import.get_user_repos(token)

@router.get("/github/repo-files")
def get_repo_files(repo_fullname: str, token: str = Depends(get_github_token)):
    return github_import.list_files(repo_fullname, token)

@router.post("/github/import-file", response_model=models.File)
def import_repo_file(
    project_id: int,
    repo_fullname: str,
    file_path: str,
    session: Session = Depends(get_session),
    token: str = Depends(get_github_token)
):
    content = github_import.get_file_content(repo_fullname, file_path, token)
    db_file = models.File(project_id=project_id, path=file_path, content=content, updated_at=datetime.utcnow())
    session.add(db_file)
    session.commit()
    session.refresh(db_file)
    return db_file
