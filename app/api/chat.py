from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlmodel import Session
from pydantic import BaseModel
from typing import AsyncGenerator
import json
import logging

from app.db.database import get_session
from app.db import models
from app.services.cerebras_chain import ai_chain_stream

logger = logging.getLogger(__name__)
router = APIRouter()

class ChatRequest(BaseModel):
    message: str

# ==================== STREAMING ENDPOINT (HTTP) ====================

async def stream_chat_response(
    message: str,
    project_id: int,
    conv_id: int
) -> AsyncGenerator[str, None]:
    """Generate SSE stream for chat response"""
    
    try:
        messages = [
            {"role": "system", "content": "You are a helpful AI coding assistant."},
            {"role": "user", "content": message}
        ]
        
        async for chunk in ai_chain_stream(
            messages,
            project_id,
            conv_id
        ):
            if isinstance(chunk, str):
                if chunk.strip():
                    yield f"data: {chunk}\n\n"
            else:
                yield f"data: {json.dumps(chunk)}\n\n"
                
    except Exception as e:
        logger.error(f"Error in stream_chat_response: {e}")
        error_data = json.dumps({"status": "error", "message": str(e)})
        yield f"data: {error_data}\n\n"

@router.post("/chat/{conv_id}")
async def chat(
    conv_id: int,
    request: ChatRequest,
    project_id: int,
    session: Session = Depends(get_session)
):
    """Send message and get AI response (streaming)"""
    
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="Message is required")
    
    conv = session.get(models.Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return StreamingResponse(
        stream_chat_response(
            request.message,
            project_id,
            conv_id
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

# ==================== WEBSOCKET ENDPOINT ====================

@router.websocket("/ws/ai")
async def websocket_chat(
    websocket: WebSocket,
    project_id: int,
    conversation_id: int
):
    """WebSocket endpoint for real-time AI chat"""
    
    await websocket.accept()
    logger.info(f"[WebSocket] Connected: project={project_id}, conv={conversation_id}")
    
    try:
        # Wait for message from client
        data = await websocket.receive_text()
        payload = json.loads(data)
        user_message = payload.get("msg", "")
        
        if not user_message:
            await websocket.send_json({
                "status": "error",
                "message": "Empty message"
            })
            await websocket.close()
            return
        
        logger.info(f"[WebSocket] Received: {user_message[:50]}...")
        
        # Verify conversation exists
        with next(get_session()) as session:
            conv = session.get(models.Conversation, conversation_id)
            if not conv:
                await websocket.send_json({
                    "status": "error",
                    "message": "Conversation not found"
                })
                await websocket.close()
                return
        
        # Stream AI response
        messages = [
            {"role": "system", "content": "You are a helpful AI coding assistant."},
            {"role": "user", "content": user_message}
        ]
        
        async for chunk in ai_chain_stream(messages, project_id, conversation_id):
            if isinstance(chunk, str):
                # Text chunk - send as is
                await websocket.send_text(chunk)
            else:
                # Status update - send as JSON
                await websocket.send_json(chunk)
        
        # Send completion signal
        await websocket.send_json({"status": "done"})
        logger.info("[WebSocket] Stream completed")
        
    except WebSocketDisconnect:
        logger.info("[WebSocket] Client disconnected")
    except json.JSONDecodeError:
        logger.error("[WebSocket] Invalid JSON received")
        try:
            await websocket.send_json({
                "status": "error",
                "message": "Invalid message format"
            })
        except:
            pass
    except Exception as e:
        logger.error(f"[WebSocket] Error: {e}", exc_info=True)
        try:
            await websocket.send_json({
                "status": "error",
                "message": str(e)
            })
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass
