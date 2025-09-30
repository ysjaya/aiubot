import os
import json
import asyncio
from typing import List, Dict, Optional
from cerebras.cloud.sdk import Cerebras
from openai import OpenAI
from sqlmodel import Session, select

from app.db import models
from app.core.config import settings
from app.services import web_tools

# Initialize clients
cerebras_client = Cerebras(api_key=settings.CEREBRAS_API_KEY)
nvidia_client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=settings.NVIDIA_API_KEY
)

# ==================== PROMPTS ====================

PROMPT_ANALYZE_FILES = """Analyze the following files and provide a comprehensive understanding of:
1. Purpose and functionality of each file
2. Dependencies and relationships
3. Key components and architecture
4. Potential issues or improvements

FILES:
{FILES}

Provide structured analysis in Indonesian."""

PROMPT_WITH_CONTEXT = """You are an advanced AI coding assistant with access to the user's project files.

PROJECT CONTEXT:
{CONTEXT}

USER QUESTION:
{QUESTION}

WEB RESEARCH (if relevant):
{WEB_SNIPPETS}

Instructions:
- Analyze the files carefully before responding
- Reference specific files and line numbers when relevant
- If modifying code, provide complete, working solutions
- Explain your reasoning
- Use Indonesian language for explanations

Respond in Markdown format."""

PROMPT_FILE_UPDATE = """You are updating a file based on this conversation and context.

ORIGINAL FILE ({filename}):
```
{original_content}
```

CONVERSATION CONTEXT:
{conversation_context}

USER REQUEST:
{user_request}

Generate the COMPLETE updated file content. Include ALL code, not just changed parts.
Also provide a brief modification summary (1-2 sentences) explaining what changed.

Respond in JSON format:
{{
    "content": "complete updated file content here",
    "summary": "brief summary of changes"
}}"""

# ==================== HELPER FUNCTIONS ====================

async def call_cerebras(messages, model, **kwargs):
    """Non-streaming Cerebras call"""
    try:
        response = await asyncio.to_thread(
            cerebras_client.chat.completions.create,
            messages=messages,
            model=model,
            **kwargs
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"[CEREBRAS ERROR] {model}: {e}")
        return f"Error: {e}"

async def call_nvidia(messages, model, **kwargs):
    """Non-streaming NVIDIA call"""
    try:
        response = await asyncio.to_thread(
            nvidia_client.chat.completions.create,
            model=model,
            messages=messages,
            **kwargs
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"[NVIDIA ERROR] {model}: {e}")
        return f"Error: {e}"

def stream_cerebras(messages, model, **kwargs):
    """Streaming Cerebras call"""
    return cerebras_client.chat.completions.create(
        messages=messages,
        model=model,
        stream=True,
        **kwargs
    )

async def get_conversation_context(conv_id: int, session: Session) -> str:
    """Get conversation history and attachments for context"""
    # Get latest attachments
    attachments = session.exec(
        select(models.Attachment)
        .where(models.Attachment.conversation_id == conv_id)
        .where(models.Attachment.status.in_([models.FileStatus.LATEST, models.FileStatus.ORIGINAL]))
        .order_by(models.Attachment.updated_at.desc())
    ).all()
    
    context_parts = []
    
    # Add file contents
    if attachments:
        context_parts.append("=== PROJECT FILES ===\n")
        for att in attachments:
            status_label = att.get_display_status()
            context_parts.append(f"\n--- File: {att.filename} ({status_label} v{att.version}) ---")
            if att.modification_summary:
                context_parts.append(f"Changes: {att.modification_summary}")
            context_parts.append(f"```\n{att.content}\n```\n")
    
    # Get recent chat history (last 5 messages)
    recent_chats = session.exec(
        select(models.Chat)
        .where(models.Chat.conversation_id == conv_id)
        .order_by(models.Chat.created_at.desc())
        .limit(5)
    ).all()
    
    if recent_chats:
        context_parts.append("\n=== RECENT CONVERSATION ===")
        for chat in reversed(recent_chats):
            context_parts.append(f"\nUser: {chat.message}")
            context_parts.append(f"AI: {chat.ai_response[:500]}...")  # Truncate long responses
    
    return "\n".join(context_parts)

async def detect_file_modifications(response: str, attachments: List[models.Attachment]) -> List[Dict]:
    """Detect if AI wants to modify any files"""
    modifications = []
    
    # Simple heuristic: look for code blocks with filenames
    import re
    
    # Pattern: ```filename or // filename.ext or # filename.py
    patterns = [
        r'```(?:[\w]+\s+)?([a-zA-Z0-9_\-./]+\.[a-zA-Z]+)',  # ```python app.py
        r'//\s*([a-zA-Z0-9_\-./]+\.[a-zA-Z]+)',  # // app.py
        r'#\s*([a-zA-Z0-9_\-./]+\.[a-zA-Z]+)',  # # app.py
    ]
    
    detected_files = set()
    for pattern in patterns:
        matches = re.findall(pattern, response)
        detected_files.update(matches)
    
    # Match with actual attachments
    for att in attachments:
        if att.filename in detected_files or any(att.filename in response for att in attachments):
            modifications.append({
                'attachment_id': att.id,
                'filename': att.filename,
                'detected': True
            })
    
    return modifications

async def apply_file_modifications(
    modifications: List[Dict],
    full_response: str,
    user_query: str,
    conv_id: int,
    session: Session
):
    """Apply AI-suggested modifications to files"""
    for mod in modifications:
        att = session.get(models.Attachment, mod['attachment_id'])
        if not att:
            continue
        
        print(f"[FILE UPDATE] Updating {att.filename}...")
        
        # Use AI to generate clean file update
        update_prompt = PROMPT_FILE_UPDATE.format(
            filename=att.filename,
            original_content=att.content,
            conversation_context=full_response[:1000],  # Truncate
            user_request=user_query
        )
        
        try:
            update_response = await call_cerebras(
                [{"role": "user", "content": update_prompt}],
                "llama-4-maverick-17b-128e-instruct"
            )
            
            # Parse JSON response
            update_data = json.loads(update_response)
            new_content = update_data.get('content', '')
            summary = update_data.get('summary', 'AI-generated update')
            
            # Create new version
            root_id = att.parent_file_id if att.parent_file_id else att.id
            
            # Get max version
            all_versions = session.exec(
                select(models.Attachment)
                .where(
                    (models.Attachment.id == root_id) | 
                    (models.Attachment.parent_file_id == root_id)
                )
            ).all()
            next_version = max([v.version for v in all_versions]) + 1 if all_versions else 2
            
            # Mark old LATEST as MODIFIED
            old_latest = session.exec(
                select(models.Attachment)
                .where(models.Attachment.conversation_id == conv_id)
                .where(models.Attachment.filename == att.filename)
                .where(models.Attachment.status == models.FileStatus.LATEST)
            ).first()
            
            if old_latest:
                old_latest.status = models.FileStatus.MODIFIED
                session.add(old_latest)
            
            # Create new version
            new_att = models.Attachment(
                conversation_id=conv_id,
                filename=att.filename,
                original_filename=att.original_filename,
                content=new_content,
                mime_type=att.mime_type,
                size_bytes=len(new_content.encode('utf-8')),
                status=models.FileStatus.LATEST,
                version=next_version,
                parent_file_id=root_id,
                modification_summary=summary
            )
            
            session.add(new_att)
            session.commit()
            
            print(f"[FILE UPDATE] ✅ Updated {att.filename} to v{next_version}: {summary}")
            
        except Exception as e:
            print(f"[FILE UPDATE] ❌ Failed to update {att.filename}: {e}")

# ==================== MAIN AI CHAIN ====================

async def ai_chain_stream(messages, project_id, conv_id, session: Session):
    """Enhanced AI chain with file context and intelligent updates"""
    user_query = messages[-1]['content']
    print(f"\n[AI CHAIN] Query: {user_query[:100]}...")
    
    try:
        # STAGE 1: Get conversation context (files + history)
        yield json.dumps({"status": "update", "message": "📂 Loading project context..."})
        context = await get_conversation_context(conv_id, session)
        
        # Get attachments for potential updates
        attachments = session.exec(
            select(models.Attachment)
            .where(models.Attachment.conversation_id == conv_id)
            .where(models.Attachment.status.in_([models.FileStatus.LATEST, models.FileStatus.ORIGINAL]))
        ).all()
        
        # STAGE 2: Web search (if needed)
        web_snippets = ""
        if any(keyword in user_query.lower() for keyword in ['search', 'latest', 'how to', 'tutorial', 'documentation']):
            yield json.dumps({"status": "update", "message": "🔍 Searching web..."})
            search_results = web_tools.search_web(user_query, num_results=3)
            urls = [r['url'] for r in search_results.get('results', [])]
            
            snippets = []
            for url in urls[:2]:  # Limit to 2 URLs
                try:
                    content = web_tools.scrape_url(url)
                    if content and content['text']:
                        snippets.append(f"Source: {url}\n{content['text'][:1500]}")
                except:
                    pass
            
            web_snippets = "\n\n".join(snippets)
        
        # STAGE 3: Generate response with full context
        yield json.dumps({"status": "update", "message": "🤖 Analyzing and generating response..."})
        
        main_prompt = PROMPT_WITH_CONTEXT.format(
            CONTEXT=context,
            QUESTION=user_query,
            WEB_SNIPPETS=web_snippets or "No web search performed."
        )
        
        # Stream response
        stream = stream_cerebras(
            [{"role": "user", "content": main_prompt}],
            "llama-4-maverick-17b-128e-instruct"
        )
        
        full_response = ""
        for chunk in stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_response += content
                yield content
        
        # STAGE 4: Detect and apply file modifications
        if attachments:
            yield json.dumps({"status": "update", "message": "💾 Checking for file updates..."})
            
            modifications = await detect_file_modifications(full_response, attachments)
            
            if modifications:
                yield json.dumps({"status": "update", "message": f"✏️ Updating {len(modifications)} file(s)..."})
                await apply_file_modifications(
                    modifications,
                    full_response,
                    user_query,
                    conv_id,
                    session
                )
                
                # Notify user
                update_msg = "\n\n---\n**📝 Files Updated:**\n"
                for mod in modifications:
                    update_msg += f"- ✨ {mod['filename']} (new version created)\n"
                yield update_msg
        
        # Save to database
        yield json.dumps({"status": "done"})
        
        # Store context file IDs
        file_ids = [str(att.id) for att in attachments] if attachments else []
        
        db_chat = models.Chat(
            conversation_id=conv_id,
            user="user",
            message=user_query,
            ai_response=full_response,
            context_file_ids=json.dumps(file_ids)
        )
        session.add(db_chat)
        session.commit()
        
        print("[AI CHAIN] ✅ Complete")
        
    except Exception as e:
        print(f"[AI CHAIN] ❌ Error: {e}")
        yield json.dumps({"status": "error", "message": str(e)})
