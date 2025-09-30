import json
import asyncio
import re
from typing import List, Dict
from datetime import datetime
from cerebras.cloud.sdk import Cerebras
from sqlmodel import Session, select

from app.db import models
from app.core.config import settings

cerebras_client = Cerebras(api_key=settings.CEREBRAS_API_KEY)

SYSTEM_PROMPT = """You are an expert AI coding assistant with full project context.

CAPABILITIES:
- Analyze code across multiple files
- Provide precise solutions with file/line references
- Auto-update files when making changes
- Explain technical concepts clearly

RULES:
1. Always reference specific files when discussing code
2. When modifying code, output complete updated files
3. Provide clear modification summaries
4. Use Indonesian for explanations, English for code
5. Be concise and precise

When updating a file, wrap it like this:
```UPDATE:filename.py
<complete updated file content>
```

Always include a summary line after the code block."""

async def call_cerebras(messages, model="llama-4-maverick-17b-128e-instruct"):
    try:
        response = await asyncio.to_thread(
            cerebras_client.chat.completions.create,
            messages=messages,
            model=model,
            temperature=0.7,
            max_tokens=4000
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"[CEREBRAS ERROR] {e}")
        return f"Error: {e}"

def stream_cerebras(messages, model="llama-4-maverick-17b-128e-instruct"):
    return cerebras_client.chat.completions.create(
        messages=messages,
        model=model,
        stream=True,
        temperature=0.7,
        max_tokens=4000
    )

def get_conversation_context(conv_id: int, session: Session) -> tuple[str, List[models.Attachment]]:
    """Get all files in conversation"""
    # Get latest version of each file
    latest_files = {}
    attachments = session.exec(
        select(models.Attachment)
        .where(models.Attachment.conversation_id == conv_id)
        .order_by(models.Attachment.version.desc())
    ).all()
    
    for att in attachments:
        if att.filename not in latest_files:
            latest_files[att.filename] = att
    
    attachments_list = list(latest_files.values())
    
    if not attachments_list:
        return "", []
    
    # Build context
    context_parts = ["=== PROJECT FILES ===\n"]
    for att in attachments_list:
        status = "✨ LATEST" if att.status == models.FileStatus.LATEST else "📄 ORIGINAL"
        context_parts.append(f"\n--- {att.filename} ({status} v{att.version}) ---")
        if att.modification_summary:
            context_parts.append(f"Last change: {att.modification_summary}")
        context_parts.append(f"```\n{att.content}\n```\n")
    
    return "\n".join(context_parts), attachments_list

def extract_file_updates(response: str) -> List[Dict]:
    """Extract file updates from AI response"""
    updates = []
    pattern = r'```UPDATE:([^\n]+)\n(.*?)```'
    matches = re.findall(pattern, response, re.DOTALL)
    
    for filename, content in matches:
        filename = filename.strip()
        content = content.strip()
        
        # Extract summary if present
        summary_match = re.search(r'<!--\s*SUMMARY:\s*(.+?)\s*-->', response)
        summary = summary_match.group(1) if summary_match else "AI-generated update"
        
        updates.append({
            'filename': filename,
            'content': content,
            'summary': summary
        })
    
    return updates

def apply_file_updates(updates: List[Dict], attachments: List[models.Attachment], conv_id: int, session: Session):
    """Apply file updates to database"""
    for update in updates:
        # Find matching attachment
        att = next((a for a in attachments if a.filename == update['filename']), None)
        if not att:
            continue
        
        # Mark old versions as MODIFIED
        old_versions = session.exec(
            select(models.Attachment)
            .where(models.Attachment.conversation_id == conv_id)
            .where(models.Attachment.filename == att.filename)
        ).all()
        
        for old in old_versions:
            if old.status == models.FileStatus.LATEST:
                old.status = models.FileStatus.MODIFIED
                session.add(old)
        
        # Get max version
        max_version = max([v.version for v in old_versions]) if old_versions else 0
        
        # Create new version
        new_att = models.Attachment(
            conversation_id=conv_id,
            filename=att.filename,
            original_filename=att.original_filename,
            content=update['content'],
            mime_type=att.mime_type,
            size_bytes=len(update['content'].encode('utf-8')),
            status=models.FileStatus.LATEST,
            version=max_version + 1,
            parent_file_id=att.id,
            modification_summary=update['summary'],
            updated_at=datetime.utcnow()
        )
        
        session.add(new_att)
        session.commit()
        session.refresh(new_att)
        
        print(f"✅ Updated: {att.filename} → v{new_att.version}")

async def ai_chain_stream(messages, project_id, conv_id, session: Session):
    """Main AI processing pipeline"""
    user_query = messages[-1]['content']
    print(f"\n[AI] Query: {user_query[:100]}...")
    
    try:
        # Load context
        yield json.dumps({"status": "update", "message": "📂 Loading files..."})
        context, attachments = get_conversation_context(conv_id, session)
        
        if not context:
            yield json.dumps({"status": "update", "message": "⚠️ No files attached"})
        
        # Get recent chat history
        recent_chats = session.exec(
            select(models.Chat)
            .where(models.Chat.conversation_id == conv_id)
            .order_by(models.Chat.created_at.desc())
            .limit(3)
        ).all()
        
        chat_history = []
        for chat in reversed(recent_chats):
            chat_history.append({"role": "user", "content": chat.message})
            chat_history.append({"role": "assistant", "content": chat.ai_response[:500]})
        
        # Build final prompt
        full_prompt = f"{SYSTEM_PROMPT}\n\n{context}\n\nUser: {user_query}"
        
        # Stream response
        yield json.dumps({"status": "update", "message": "🤖 Generating response..."})
        
        conversation = chat_history + [{"role": "user", "content": full_prompt}]
        stream = stream_cerebras(conversation)
        
        full_response = ""
        for chunk in stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_response += content
                yield content
        
        # Check for file updates
        updates = extract_file_updates(full_response)
        
        if updates and attachments:
            yield json.dumps({"status": "update", "message": f"💾 Updating {len(updates)} file(s)..."})
            apply_file_updates(updates, attachments, conv_id, session)
            
            yield "\n\n---\n**📝 Files Updated:**\n"
            for u in updates:
                yield f"- ✨ {u['filename']} (v{[a for a in attachments if a.filename == u['filename']][0].version + 1}): {u['summary']}\n"
        
        # Save chat
        db_chat = models.Chat(
            conversation_id=conv_id,
            user="user",
            message=user_query,
            ai_response=full_response,
            context_file_ids=json.dumps([a.id for a in attachments])
        )
        session.add(db_chat)
        session.commit()
        
        yield json.dumps({"status": "done"})
        print("[AI] ✅ Complete")
        
    except Exception as e:
        print(f"[AI ERROR] {e}")
        yield json.dumps({"status": "error", "message": str(e)})
