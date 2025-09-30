from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session
from pydantic import BaseModel
from typing import AsyncGenerator
import json
import logging

from app.db.database import get_session, get_project_session
from app.db import models
from app.services.cerebras_chain import ai_chain_stream

logger = logging.getLogger(__name__)
router = APIRouter()

class ChatRequest(BaseModel):
    message: str

async def stream_chat_response(
    message: str,
    project_id: int,
    conv_id: int,
    project_database: str
) -> AsyncGenerator[str, None]:
    """Generate SSE stream for chat response"""
    
    try:
        # Build messages array
        messages = [
            {"role": "system", "content": "You are a helpful AI coding assistant."},
            {"role": "user", "content": message}
        ]
        
        # Stream AI response
        async for chunk in ai_chain_stream(
            messages,
            project_id,
            conv_id,
            project_database
        ):
            # Send SSE formatted data
            if isinstance(chunk, str):
                if chunk.strip():
                    yield f"data: {chunk}\n\n"
            else:
                # Handle dict/json responses
                yield f"data: {json.dumps(chunk)}\n\n"
                
    except Exception as e:
        logger.error(f"Error in stream_chat_response: {e}")
        error_data = json.dumps({"status": "error", "message": str(e)})
        yield f"data: {error_data}\n\n"

@router.post("/chat/{conv_id}")
async def chat(
    conv_id: int,
    project_id: int,
    request: ChatRequest,
    session: Session = Depends(get_session)
):
    """Send a message and get AI response (streaming)"""
    
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="Message is required")
    
    # Verify project exists
    project = session.get(models.Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Verify conversation exists in project database
    with next(get_project_session(project.database_name)) as proj_session:
        conv = proj_session.get(models.Conversation, conv_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Return streaming response
    return StreamingResponse(
        stream_chat_response(
            request.message,
            project_id,
            conv_id,
            project.database_name
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
  )
