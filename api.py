from fastapi import APIRouter, Depends
from sqlmodel import Session, select, delete
from models import Project, Conversation, Chat, File
from db import get_session

router = APIRouter()

# === Project ===
@router.post("/project")
def create_project(name: str, session: Session = Depends(get_session)):
    project = Project(name=name)
    session.add(project)
    session.commit()
    session.refresh(project)
    return project

@router.get("/projects")
def list_projects(session: Session = Depends(get_session)):
    return session.exec(select(Project)).all()

@router.delete("/project/{project_id}")
def delete_project(project_id: int, session: Session = Depends(get_session)):
    session.exec(delete(Project).where(Project.id == project_id))
    session.commit()
    return {"ok": True}

# === Conversation ===
@router.post("/conversation")
def new_conversation(project_id: int, title: str, session: Session = Depends(get_session)):
    conv = Conversation(project_id=project_id, title=title)
    session.add(conv)
    session.commit()
    session.refresh(conv)
    return conv

@router.get("/project/{project_id}/conversations")
def list_conversations(project_id: int, session: Session = Depends(get_session)):
    return session.exec(select(Conversation).where(Conversation.project_id == project_id)).all()

@router.delete("/conversation/{conv_id}")
def delete_conversation(conv_id: int, session: Session = Depends(get_session)):
    session.exec(delete(Conversation).where(Conversation.id == conv_id))
    session.commit()
    return {"ok": True}

# === Chat ===
@router.get("/conversation/{conv_id}/chats")
def get_chats(conv_id: int, session: Session = Depends(get_session)):
    return session.exec(select(Chat).where(Chat.conversation_id == conv_id)).all()

@router.post("/chat")
def save_chat(conversation_id: int, user: str, message: str, ai_response: str, session: Session = Depends(get_session)):
    chat = Chat(conversation_id=conversation_id, user=user, message=message, ai_response=ai_response)
    session.add(chat)
    session.commit()
    session.refresh(chat)
    return chat

@router.delete("/chat/{chat_id}")
def delete_chat(chat_id: int, session: Session = Depends(get_session)):
    session.exec(delete(Chat).where(Chat.id == chat_id))
    session.commit()
    return {"ok": True}
