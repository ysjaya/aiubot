from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
from pydantic import BaseModel
from typing import AsyncGenerator
from datetime import datetime
import json
import logging

from app.db.database import get_session
from app.db import models
from app.services.cerebras_chain import ai_chain_stream

logger = logging.getLogger(__name__)
router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    unlimited: bool = True  # Default to unlimited mode

# ==================== STREAMING ENDPOINT (HTTP) ====================

async def stream_chat_response(
    message: str,
    conv_id: int,
    chat_id: int,
    unlimited: bool = True,
    session: Session = None
) -> AsyncGenerator[str, None]:
    """Generate SSE stream for chat response"""
    
    ai_response_parts = []  # Collect all response parts
    
    try:
        # Get conversation history for context
        previous_chats = []
        if session:
            previous_chats = session.exec(
                select(models.Chat)
                .where(models.Chat.conversation_id == conv_id)
                .where(models.Chat.id != chat_id)  # Exclude current chat
                .order_by(models.Chat.created_at.asc())
            ).all()
        
        # Build messages with history
        messages = [
            {"role": "system", "content": "You are a helpful AI coding assistant."}
        ]
        
        # Add conversation history
        for chat in previous_chats[-10:]:  # Last 10 messages for context
            messages.append({"role": "user", "content": chat.user})
            if chat.ai_response:
                messages.append({"role": "assistant", "content": chat.ai_response})
        
        # Add current message
        messages.append({"role": "user", "content": message})
        
        # Stream AI response
        async for chunk in ai_chain_stream(
            messages,
            conv_id,
            unlimited=unlimited
        ):
            if isinstance(chunk, str):
                # Text chunk
                if chunk.strip():
                    # Collect for saving later
                    ai_response_parts.append(chunk)
                    # Stream to client
                    yield f"data: {chunk}\n\n"
            else:
                # Status update (JSON)
                yield f"data: {json.dumps(chunk)}\n\n"
        
        # Save complete AI response to database
        if ai_response_parts and session:
            complete_response = ''.join(ai_response_parts)
            
            # Update the chat with AI response
            chat = session.get(models.Chat, chat_id)
            if chat:
                chat.ai_response = complete_response
                chat.response_received_at = datetime.utcnow()
                session.add(chat)
                
                # Update conversation timestamp
                conv = session.get(models.Conversation, conv_id)
                if conv:
                    conv.updated_at = datetime.utcnow()
                    session.add(conv)
                
                session.commit()
                logger.info(f"✅ Saved AI response to chat {chat_id}")
            else:
                logger.error(f"❌ Chat {chat_id} not found for saving response")
                
    except Exception as e:
        logger.error(f"Error in stream_chat_response: {e}", exc_info=True)
        error_data = json.dumps({"status": "error", "message": str(e)})
        yield f"data: {error_data}\n\n"

@router.post("/chat/{conv_id}")
async def chat(
    conv_id: int,
    request: ChatRequest,
    session: Session = Depends(get_session)
):
    """Send message and get AI response (streaming)"""
    
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="Message is required")
    
    # Verify conversation exists
    conv = session.get(models.Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # ✅ FIX 1: Save user message to database FIRST
    new_chat = models.Chat(
        conversation_id=conv_id,
        user=request.message.strip(),
        ai_response="",  # Will be filled during streaming
        created_at=datetime.utcnow()
    )
    
    session.add(new_chat)
    session.commit()
    session.refresh(new_chat)
    
    logger.info(f"✅ Created chat {new_chat.id} in conversation {conv_id}")
    
    # ✅ FIX 2: Pass chat_id and session to stream function
    return StreamingResponse(
        stream_chat_response(
            request.message,
            conv_id,
            new_chat.id,  # Pass chat ID
            unlimited=request.unlimited,
            session=session  # Pass session for saving response
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
    conversation_id: int
):
    """WebSocket endpoint for real-time AI chat"""
    
    await websocket.accept()
    logger.info(f"[WebSocket] Connected: conv={conversation_id}")
    
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
        
        # Verify conversation exists and save chat
        with next(get_session()) as session:
            conv = session.get(models.Conversation, conversation_id)
            if not conv:
                await websocket.send_json({
                    "status": "error",
                    "message": "Conversation not found"
                })
                await websocket.close()
                return
            
            # ✅ Save user message
            new_chat = models.Chat(
                conversation_id=conversation_id,
                user=user_message.strip(),
                ai_response="",
                created_at=datetime.utcnow()
            )
            session.add(new_chat)
            session.commit()
            session.refresh(new_chat)
            chat_id = new_chat.id
        
        # Get conversation history
        with next(get_session()) as session:
            previous_chats = session.exec(
                select(models.Chat)
                .where(models.Chat.conversation_id == conversation_id)
                .where(models.Chat.id != chat_id)
                .order_by(models.Chat.created_at.asc())
            ).all()
            
            # Build messages with history
            messages = [
                {"role": "system", "content": "You are a helpful AI coding assistant."}
            ]
            
            for chat in previous_chats[-10:]:
                messages.append({"role": "user", "content": chat.user})
                if chat.ai_response:
                    messages.append({"role": "assistant", "content": chat.ai_response})
            
            messages.append({"role": "user", "content": user_message})
        
        # Stream AI response
        ai_response_parts = []
        
        async for chunk in ai_chain_stream(messages, conversation_id):
            if isinstance(chunk, str):
                # Text chunk - send and collect
                ai_response_parts.append(chunk)
                await websocket.send_text(chunk)
            else:
                # Status update - send as JSON
                await websocket.send_json(chunk)
        
        # ✅ Save complete AI response
        if ai_response_parts:
            with next(get_session()) as session:
                chat = session.get(models.Chat, chat_id)
                if chat:
                    chat.ai_response = ''.join(ai_response_parts)
                    chat.response_received_at = datetime.utcnow()
                    session.add(chat)
                    
                    conv = session.get(models.Conversation, conversation_id)
                    if conv:
                        conv.updated_at = datetime.utcnow()
                        session.add(conv)
                    
                    session.commit()
                    logger.info(f"✅ [WebSocket] Saved AI response to chat {chat_id}")
        
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
