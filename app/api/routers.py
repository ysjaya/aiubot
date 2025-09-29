from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, delete
from typing import List

from app.db import models
from app.db.database import get_session

router = APIRouter()

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

@router.post("/chat", response_model=models.Chat)
def save_chat(conversation_id: int, user: str, message: str, ai_response: str, session: Session = Depends(get_session)):
    chat = models.Chat(conversation_id=conversation_id, user=user, message=message, ai_response=ai_response)
    session.add(chat)
    session.commit()
    session.refresh(chat)
    return chat
