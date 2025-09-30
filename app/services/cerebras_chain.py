# app/services/cerebras_chain.py
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
from app.db.database import get_session
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

PROMPT_ANALYZE_PROJECT = """Analyze this project structure and provide insights:

PROJECT FILES:
{FILES}

Provide a comprehensive analysis covering:
1. **Project Purpose**: What does this project do?
2. **Architecture**: Key components and their relationships
3. **Technologies**: Frameworks, libraries, and tools used
4. **File Dependencies**: Which files depend on each other?
5. **Potential Issues**: Code smells, bugs, or areas for improvement
6. **Recommendations**: Suggestions for optimization or refactoring

Format your response in clear, structured Markdown."""

PROMPT_WITH_CONTEXT = """You are assisting with a coding project. Here's the current context:

PROJECT FILES:
{CONTEXT}

RECENT CONVERSATION:
{CONVERSATION_HISTORY}

WEB RESEARCH (if relevant):
{WEB_SNIPPETS}

USER QUESTION:
{QUESTION}

Instructions:
- Reference specific files with their version status (e.g., "In ✨ main.py v3...")
- If suggesting code changes, explain WHY before showing HOW
- Provide complete, working solutions
- If multiple files need changes, address them systematically
- Use Indonesian language for explanations

Respond in well-formatted Markdown."""

PROMPT_INTELLIGENT_UPDATE = """You are updating a file based on user request and AI suggestions.

CURRENT FILE: {filename} (v{version})

CURRENT CONTENT:
```
{current_content}
```

PROJECT CONTEXT:
{project_files}

USER REQUEST:
{user_request}

AI RESPONSE/SUGGESTIONS:
{ai_response}

Your task:
1. Analyze what changes are needed
2. Generate the COMPLETE updated file content
3. Provide a clear summary of changes

Respond with ONLY valid JSON:
{{
    "content": "COMPLETE updated file content here",
    "summary": "Brief description of changes",
    "changes": ["change 1", "change 2", "change 3"]
}}"""

# ==================== HELPER FUNCTIONS ====================

async def call_cerebras(messages: List[Dict]) -> str:
    """Call Cerebras API synchronously"""
    if not cerebras_client:
        raise Exception("Cerebras client not initialized")
    
    try:
        response = await asyncio.to_thread(
            cerebras_client.chat.completions.create,
            messages=messages,
            model="llama3.1-70b",
            max_tokens=4096,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Cerebras API error: {e}")
        raise

def stream_cerebras(messages: List[Dict]):
    """Stream Cerebras API response"""
    if not cerebras_client:
        raise Exception("Cerebras client not initialized")
    
    try:
        return cerebras_client.chat.completions.create(
            messages=messages,
            model="llama3.1-70b",
            max_tokens=4096,
            temperature=0.7,
            stream=True
        )
    except Exception as e:
        logger.error(f"Cerebras streaming error: {e}")
        raise

async def get_conversation_context(conv_id: int):
    """Get conversation context including files and chat history"""
    with next(get_session()) as session:
        # Get attachments
        attachments = session.exec(
            select(models.Attachment)
            .where(models.Attachment.conversation_id == conv_id)
            .order_by(models.Attachment.updated_at.desc())
        ).all()
        
        # Build file context
        file_context = ""
        if attachments:
            for att in attachments:
                status = att.get_display_status()
                file_context += f"\n## {status} {att.filename} (v{att.version})\n"
                file_context += f"```\n{att.content[:2000]}\n```\n"
        
        # Get recent chat history
        chats = session.exec(
            select(models.Chat)
            .where(models.Chat.conversation_id == conv_id)
            .order_by(models.Chat.created_at.desc())
            .limit(5)
        ).all()
        
        chat_history = ""
        for chat in reversed(chats):
            chat_history += f"\nUser: {chat.message}\n"
            chat_history += f"AI: {chat.ai_response[:500]}...\n"
        
        return file_context, chat_history, attachments

def detect_code_blocks_with_filenames(response: str) -> List[Dict]:
    """Intelligently detect code blocks that should update files"""
    detected = []
    
    lines = response.split('\n')
    current_file = None
    in_code_block = False
    code_content = []
    
    for i, line in enumerate(lines):
        # Detect code block start
        if line.strip().startswith('```'):
            if in_code_block:
                # Block end
                if current_file and code_content:
                    detected.append({
                        'filename': current_file,
                        'code': '\n'.join(code_content),
                        'confidence': 'high'
                    })
                in_code_block = False
                code_content = []
                current_file = None
            else:
                # Block start
                in_code_block = True
                # Try to extract filename from marker
                match = re.search(r'```(?:\w+\s+)?([a-zA-Z0-9_\-./]+\.[a-zA-Z]+)', line)
                if match:
                    current_file = match.group(1)
        
        elif in_code_block:
            code_content.append(line)
        
        # Look for file mentions before code blocks
        elif not in_code_block:
            match = re.search(r'\b([a-zA-Z0-9_\-./]+\.[a-zA-Z]+)\b', line.lower())
            if match and any(keyword in line.lower() for keyword in ['update', 'modify', 'change', 'fix', 'in ']):
                current_file = match.group(1)
    
    return detected

async def intelligent_file_update(
    attachment: models.Attachment,
    user_request: str,
    ai_response: str,
    project_files: str,
    session: Session
) -> Optional[models.Attachment]:
    """Intelligently update a file based on conversation context"""
    try:
        logger.info(f"[FILE UPDATE] Processing: {attachment.filename}")
        
        # Build intelligent update prompt
        update_prompt = PROMPT_INTELLIGENT_UPDATE.format(
            filename=attachment.filename,
            version=attachment.version,
            current_content=attachment.content,
            project_files=project_files[:3000],
            user_request=user_request,
            ai_response=ai_response[:2000]
        )
        
        # Get AI update
        system_msg = {"role": "system", "content": PROMPT_SYSTEM}
        user_msg = {"role": "user", "content": update_prompt}
        
        update_response = await call_cerebras([system_msg, user_msg])
        
        # Parse JSON response
        try:
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', update_response, re.DOTALL)
            if json_match:
                update_data = json.loads(json_match.group(1))
            else:
                update_data = json.loads(update_response)
            
            new_content = update_data.get('content', '')
            summary = update_data.get('summary', 'AI-generated update')
            changes = update_data.get('changes', [])
            
            if not new_content or len(new_content) < 10:
                logger.warning(f"[FILE UPDATE] ❌ Generated content too short")
                return None
            
            # Create new version
            root_id = attachment.parent_file_id if attachment.parent_file_id else attachment.id
            
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
                .where(models.Attachment.conversation_id == attachment.conversation_id)
                .where(models.Attachment.filename == attachment.filename)
                .where(models.Attachment.status == models.FileStatus.LATEST)
            ).first()
            
            if old_latest:
                old_latest.status = models.FileStatus.MODIFIED
                session.add(old_latest)
            
            # Create new version
            full_summary = f"✨ TERBARU: {summary}"
            if changes:
                full_summary += f" | Perubahan: {', '.join(changes[:3])}"
            
            new_att = models.Attachment(
                conversation_id=attachment.conversation_id,
                filename=attachment.filename,
                original_filename=attachment.original_filename,
                content=new_content,
                mime_type=attachment.mime_type,
                size_bytes=len(new_content.encode('utf-8')),
                status=models.FileStatus.LATEST,
                version=next_version,
                parent_file_id=root_id,
                modification_summary=full_summary,
                import_source=attachment.import_source,
                import_metadata=json.dumps({
                    "updated_at": datetime.utcnow().isoformat(),
                    "updated_by": "ai",
                    "changes": changes
                })
            )
            
            session.add(new_att)
            session.commit()
            session.refresh(new_att)
            
            logger.info(f"[FILE UPDATE] ✅ {attachment.filename} updated to v{next_version}")
            
            return new_att
            
        except json.JSONDecodeError as e:
            logger.error(f"[FILE UPDATE] ❌ Failed to parse AI response: {e}")
            return None
            
    except Exception as e:
        logger.error(f"[FILE UPDATE] ❌ Error updating {attachment.filename}: {e}", exc_info=True)
        return None

# ==================== MAIN AI CHAIN ====================

async def ai_chain_stream(messages, project_id: int, conv_id: int):
    """Enhanced AI chain with intelligent file analysis and updates"""
    user_query = messages[-1]['content']
    logger.info(f"[AI CHAIN] Starting for conv {conv_id}")
    
    try:
        if not cerebras_client:
            yield json.dumps({
                "status": "error",
                "message": "AI service not configured. Please check API keys."
            })
            return
        
        # Load context
        yield json.dumps({"status": "update", "message": "📂 Loading project files..."})
        
        file_context, chat_history, attachments = await get_conversation_context(conv_id)
        
        if not file_context:
            yield json.dumps({"status": "update", "message": "💡 No files attached yet"})
        else:
            yield json.dumps({"status": "update", "message": f"📚 Analyzing {len(attachments)} file(s)..."})
        
        # Check if web search needed
        web_snippets = ""
        search_keywords = ['search', 'find', 'latest', 'how to', 'tutorial', 'documentation', 'what is', 'cari', 'terbaru']
        
        if any(keyword in user_query.lower() for keyword in search_keywords):
            yield json.dumps({"status": "update", "message": "🔍 Searching web..."})
            
            try:
                search_results = web_tools.search_web(user_query, num_results=3)
                urls = [r['url'] for r in search_results.get('results', [])]
                
                snippets = []
                for url in urls[:2]:
                    try:
                        content = web_tools.scrape_url(url)
                        if content and content['text']:
                            snippets.append(f"**Source:** {url}\n{content['text'][:1500]}\n")
                    except:
                        pass
                
                web_snippets = "\n".join(snippets) if snippets else "No web results found."
            except Exception as e:
                logger.error(f"[AI CHAIN] Web search error: {e}")
                web_snippets = "Web search unavailable."
        
        # Generate response
        yield json.dumps({"status": "update", "message": "🤖 Generating response..."})
        
        main_prompt = PROMPT_WITH_CONTEXT.format(
            CONTEXT=file_context or "No files attached yet.",
            CONVERSATION_HISTORY=chat_history or "No previous conversation.",
            WEB_SNIPPETS=web_snippets or "No web search performed.",
            QUESTION=user_query
        )
        
        system_msg = {"role": "system", "content": PROMPT_SYSTEM}
        user_msg = {"role": "user", "content": main_prompt}
        
        # Stream response
        stream = stream_cerebras([system_msg, user_msg])
        
        full_response = ""
        for chunk in stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_response += content
                yield content
        
        # File modification detection
        if attachments and full_response:
            yield json.dumps({"status": "update", "message": "💾 Checking for file updates..."})
            
            code_blocks = detect_code_blocks_with_filenames(full_response)
            
            files_to_update = []
            for block in code_blocks:
                for att in attachments:
                    if att.filename.lower() in block['filename'].lower() or block['filename'].lower() in att.filename.lower():
                        files_to_update.append({
                            'attachment': att,
                            'code': block['code'],
                            'confidence': block['confidence']
                        })
                        break
            
            # Apply updates
            if files_to_update:
                yield json.dumps({"status": "update", "message": f"✏️ Updating {len(files_to_update)} file(s)..."})
                
                updated_files = []
                
                with next(get_session()) as session:
                    for file_update in files_to_update:
                        att = file_update['attachment']
                        fresh_att = session.get(models.Attachment, att.id)
                        
                        if fresh_att:
                            new_version = await intelligent_file_update(
                                fresh_att,
                                user_query,
                                full_response,
                                file_context,
                                session
                            )
                            
                            if new_version:
                                updated_files.append(new_version)
                
                if updated_files:
                    update_notification = "\n\n---\n### ✨ Files Updated:\n\n"
                    for file in updated_files:
                        update_notification += f"- **{file.filename}** (v{file.version}) - {file.modification_summary}\n"
                    
                    yield update_notification
                    modified_ids = [f.id for f in updated_files]
                else:
                    modified_ids = []
            else:
                modified_ids = []
        else:
            modified_ids = []
        
        # Save to database
        yield json.dumps({"status": "done"})
        
        with next(get_session()) as session:
            db_chat = models.Chat(
                conversation_id=conv_id,
                user="user",
                message=user_query,
                ai_response=full_response,
                context_file_ids=json.dumps([att.id for att in attachments]) if attachments else None,
                files_modified=json.dumps(modified_ids) if modified_ids else None
            )
            session.add(db_chat)
            session.commit()
        
        logger.info("[AI CHAIN] ✅ Complete")
        
    except Exception as e:
        logger.error(f"[AI CHAIN] ❌ Error: {e}", exc_info=True)
        yield json.dumps({"status": "error", "message": f"Server error: {str(e)[:100]}"})
