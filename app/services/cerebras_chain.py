import os
import json
import asyncio
import re
from typing import List, Dict, Optional
from cerebras.cloud.sdk import Cerebras
from openai import OpenAI
from sqlmodel import Session, select
from datetime import datetime

from app.db import models
from app.db.database import get_project_session
from app.core.config import settings
from app.services import web_tools

import logging
logger = logging.getLogger(__name__)

# Initialize clients with error handling
try:
    cerebras_client = Cerebras(api_key=settings.CEREBRAS_API_KEY)
    logger.info("✅ Cerebras client initialized")
except Exception as e:
    logger.error(f"❌ Failed to initialize Cerebras client: {e}")
    cerebras_client = None

try:
    nvidia_client = OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=settings.NVIDIA_API_KEY
    )
    logger.info("✅ NVIDIA client initialized")
except Exception as e:
    logger.error(f"❌ Failed to initialize NVIDIA client: {e}")
    nvidia_client = None

# ==================== ENHANCED PROMPTS ====================

PROMPT_SYSTEM = """You are an advanced AI coding assistant with deep understanding of:
- Code architecture and design patterns
- Best practices and optimization
- File relationships and dependencies
- Debugging and error detection

When analyzing files, you:
1. Understand the complete project structure
2. Track file versions and modifications
3. Provide context-aware responses
4. Suggest improvements proactively
5. Write clean, production-ready code

When modifying code:
- Write COMPLETE updated files, not just snippets
- Include proper imports and all dependencies
- Follow the existing code style
- Add comments for complex logic
- Test for edge cases

CRITICAL: Always reference files with their current version status (📄 Original, ✏️ Modified, ✨ Latest)"""

# ... (rest of prompts remain the same)

# ==================== HELPER FUNCTIONS ====================

async def call_cerebras(messages, model="llama-4-maverick-17b-128e-instruct", **kwargs):
    """Non-streaming Cerebras call with error handling"""
    if not cerebras_client:
        logger.error("Cerebras client not initialized")
        return "Error: AI service not available. Please check API configuration."
    
    try:
        response = await asyncio.to_thread(
            cerebras_client.chat.completions.create,
            messages=messages,
            model=model,
            max_tokens=kwargs.get('max_tokens', 2000),
            temperature=kwargs.get('temperature', 0.7)
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Cerebras API error: {e}", exc_info=True)
        return f"Error: AI service unavailable - {str(e)[:100]}"

def stream_cerebras(messages, model="llama-4-maverick-17b-128e-instruct", **kwargs):
    """Streaming Cerebras call with error handling"""
    if not cerebras_client:
        raise Exception("Cerebras client not initialized")
    
    try:
        return cerebras_client.chat.completions.create(
            messages=messages,
            model=model,
            stream=True,
            max_tokens=kwargs.get('max_tokens', 2000),
            temperature=kwargs.get('temperature', 0.7)
        )
    except Exception as e:
        logger.error(f"Cerebras streaming error: {e}", exc_info=True)
        raise

async def get_conversation_context(
    conv_id: int,
    project_database: str,
    max_files: int = 20
) -> tuple:
    """Get conversation context: files + history"""
    
    try:
        with next(get_project_session(project_database)) as session:
            # Get latest attachments
            attachments = session.exec(
                select(models.Attachment)
                .where(models.Attachment.conversation_id == conv_id)
                .where(models.Attachment.status.in_([
                    models.FileStatus.LATEST,
                    models.FileStatus.ORIGINAL
                ]))
                .order_by(models.Attachment.updated_at.desc())
                .limit(max_files)
            ).all()
            
            # Build file context
            file_contexts = []
            if attachments:
                for att in attachments:
                    status_emoji = {
                        models.FileStatus.ORIGINAL: "📄",
                        models.FileStatus.LATEST: "✨",
                        models.FileStatus.MODIFIED: "✏️"
                    }.get(att.status, "📄")
                    
                    file_info = f"\n{'='*60}\n"
                    file_info += f"{status_emoji} FILE: {att.filename} (v{att.version})\n"
                    
                    if att.modification_summary:
                        file_info += f"Last Change: {att.modification_summary}\n"
                    
                    file_info += f"{'='*60}\n"
                    file_info += f"```\n{att.content}\n```\n"
                    
                    file_contexts.append(file_info)
            
            # Get recent chat history
            recent_chats = session.exec(
                select(models.Chat)
                .where(models.Chat.conversation_id == conv_id)
                .order_by(models.Chat.created_at.desc())
                .limit(10)
            ).all()
            
            chat_history = []
            if recent_chats:
                for chat in reversed(recent_chats):
                    chat_history.append(f"User: {chat.message}")
                    # Truncate long AI responses
                    response = chat.ai_response[:1000] + ("..." if len(chat.ai_response) > 1000 else "")
                    chat_history.append(f"AI: {response}")
            
            return "\n".join(file_contexts), "\n".join(chat_history), list(attachments)
    
    except Exception as e:
        logger.error(f"Error getting conversation context: {e}", exc_info=True)
        return "", "", []

# ==================== MAIN AI CHAIN ====================

async def ai_chain_stream(
    messages,
    project_id: int,
    conv_id: int,
    project_database: str
):
    """
    Enhanced AI chain with intelligent file analysis and updates
    """
    
    user_query = messages[-1]['content']
    logger.info(f"AI Chain started for conv {conv_id}: {user_query[:100]}...")
    
    try:
        # Validate Cerebras client
        if not cerebras_client:
            yield json.dumps({
                "status": "error",
                "message": "AI service not configured. Please check API keys."
            })
            return
        
        # STAGE 1: Load project context
        yield json.dumps({
            "status": "update",
            "message": "📂 Loading project files..."
        })
        
        file_context, chat_history, attachments = await get_conversation_context(
            conv_id,
            project_database
        )
        
        if not file_context:
            yield json.dumps({
                "status": "update",
                "message": "💡 No files attached yet"
            })
        else:
            yield json.dumps({
                "status": "update",
                "message": f"📚 Analyzing {len(attachments)} file(s)..."
            })
        
        # STAGE 2: Generate main response
        yield json.dumps({
            "status": "update",
            "message": "🤖 Generating response..."
        })
        
        # Build prompt
        context_prompt = f"""You are assisting with a coding project.

PROJECT FILES:
{file_context or "No files attached yet."}

RECENT CONVERSATION:
{chat_history or "No previous conversation."}

USER QUESTION:
{user_query}

Instructions:
- Reference specific files with their version status
- If suggesting code changes, explain WHY before showing HOW
- Provide complete, working solutions
- Use Indonesian language for explanations

Respond in well-formatted Markdown."""
        
        system_msg = {"role": "system", "content": PROMPT_SYSTEM}
        user_msg = {"role": "user", "content": context_prompt}
        
        # Stream response
        try:
            stream = stream_cerebras([system_msg, user_msg])
            
            full_response = ""
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    yield content
        
        except Exception as stream_error:
            logger.error(f"Streaming error: {stream_error}", exc_info=True)
            yield json.dumps({
                "status": "error",
                "message": f"Streaming failed: {str(stream_error)[:100]}"
            })
            return
        
        # STAGE 3: Save to database
        yield json.dumps({"status": "done"})
        
        try:
            with next(get_project_session(project_database)) as session:
                db_chat = models.Chat(
                    conversation_id=conv_id,
                    user="user",
                    message=user_query,
                    ai_response=full_response,
                    context_file_ids=json.dumps([att.id for att in attachments]) if attachments else None
                )
                session.add(db_chat)
                session.commit()
                logger.info(f"Chat saved successfully for conv {conv_id}")
        except Exception as db_error:
            logger.error(f"Database save error: {db_error}", exc_info=True)
        
        logger.info("AI Chain completed successfully")
        
    except Exception as e:
        logger.error(f"AI Chain error: {e}", exc_info=True)
        yield json.dumps({
            "status": "error",
            "message": f"Server error: {str(e)[:100]}"
        })
