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

PROMPT_FILE_ANALYZER = """Analyze this specific file in detail:

FILE: {filename} (v{version}, {status})
```
{content}
```

Provide:
1. **Purpose**: What does this file do?
2. **Key Functions/Classes**: Main components
3. **Dependencies**: What it imports/requires
4. **Code Quality**: Issues or improvements
5. **Integration**: How it relates to other project files

Be specific and actionable."""

PROMPT_INTELLIGENT_UPDATE = """You are updating code based on user request. Be intelligent and precise.

CURRENT FILE: {filename} (v{version})
```
{current_content}
```

PROJECT CONTEXT:
{project_files}

CONVERSATION:
User: {user_request}

AI Previous Response: {ai_response}

Generate the COMPLETE updated file. Include:
- All necessary imports
- All functions/classes (even unchanged ones)
- Proper error handling
- Comments for new/changed code

Also provide a concise summary (2-3 sentences) of what changed and why.

Respond in JSON:
{{
    "content": "complete updated file content",
    "summary": "brief explanation of changes",
    "changes": ["list", "of", "key", "changes"]
}}"""

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

def detect_code_blocks_with_filenames(response: str) -> List[Dict]:
    """Intelligently detect code blocks that should update files"""
    detected = []
    
    # Pattern 1: ```filename or ```language filename
    # Pattern 2: Explicit mentions like "Update main.py:"
    # Pattern 3: Code blocks after file mentions
    
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
            # Pattern: "Update main.py:", "In app.py:", etc.
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
    """
    Intelligently update a file based on conversation context
    Returns new attachment version or None if update failed
    """
    try:
        logger.info(f"[FILE UPDATE] Processing: {attachment.filename}")
        
        # Build intelligent update prompt
        update_prompt = PROMPT_INTELLIGENT_UPDATE.format(
            filename=attachment.filename,
            version=attachment.version,
            current_content=attachment.content,
            project_files=project_files[:3000],  # Limit context size
            user_request=user_request,
            ai_response=ai_response[:2000]
        )
        
        # Get AI update
        system_msg = {"role": "system", "content": PROMPT_SYSTEM}
        user_msg = {"role": "user", "content": update_prompt}
        
        update_response = await call_cerebras([system_msg, user_msg])
        
        # Parse JSON response
        try:
            # Extract JSON from response (might be wrapped in markdown)
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
            
            # Create new version with badge
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
            logger.info(f"[FILE UPDATE] Summary: {summary}")
            
            return new_att
            
        except json.JSONDecodeError as e:
            logger.error(f"[FILE UPDATE] ❌ Failed to parse AI response: {e}")
            return None
            
    except Exception as e:
        logger.error(f"[FILE UPDATE] ❌ Error updating {attachment.filename}: {e}", exc_info=True)
        return None

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
    logger.info(f"[AI CHAIN] Starting for conv {conv_id}")
    logger.info(f"[AI CHAIN] Query: {user_query[:100]}...")
    
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
        
        # STAGE 2: Check if web search is needed
        web_snippets = ""
        search_keywords = [
            'search', 'find', 'latest', 'how to', 'tutorial',
            'documentation', 'what is', 'cari', 'terbaru'
        ]
        
        if any(keyword in user_query.lower() for keyword in search_keywords):
            yield json.dumps({
                "status": "update",
                "message": "🔍 Searching web for additional info..."
            })
            
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
        
        # STAGE 3: Detect if user wants project analysis
        analysis_keywords = ['analyze', 'analisa', 'review', 'explain project', 'what does this', 'jelaskan']
        wants_analysis = any(kw in user_query.lower() for kw in analysis_keywords)
        
        if wants_analysis and attachments:
            yield json.dumps({
                "status": "update",
                "message": "🔬 Performing deep project analysis..."
            })
            
            # Perform deep analysis
            analysis_prompt = PROMPT_ANALYZE_PROJECT.format(FILES=file_context)
            system_msg = {"role": "system", "content": PROMPT_SYSTEM}
            user_msg = {"role": "user", "content": analysis_prompt}
            
            analysis = await call_cerebras([system_msg, user_msg])
            
            # Stream analysis result
            for char in analysis:
                yield char
            
            # Save to database
            with next(get_project_session(project_database)) as session:
                db_chat = models.Chat(
                    conversation_id=conv_id,
                    user="user",
                    message=user_query,
                    ai_response=analysis,
                    context_file_ids=json.dumps([att.id for att in attachments])
                )
                session.add(db_chat)
                session.commit()
            
            yield json.dumps({"status": "done"})
            return
        
        # STAGE 4: Generate main response
        yield json.dumps({
            "status": "update",
            "message": "🤖 Generating response..."
        })
        
        main_prompt = PROMPT_WITH_CONTEXT.format(
            CONTEXT=file_context or "No files attached yet.",
            CONVERSATION_HISTORY=chat_history or "No previous conversation.",
            WEB_SNIPPETS=web_snippets or "No web search performed.",
            QUESTION=user_query
        )
        
        system_msg = {"role": "system", "content": PROMPT_SYSTEM}
        user_msg = {"role": "user", "content": main_prompt}
        
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
            logger.error(f"[AI CHAIN] Streaming error: {stream_error}", exc_info=True)
            yield json.dumps({
                "status": "error",
                "message": f"Streaming failed: {str(stream_error)[:100]}"
            })
            return
        
        # STAGE 5: Intelligent file modification detection
        if attachments and full_response:
            yield json.dumps({
                "status": "update",
                "message": "💾 Checking for file updates..."
            })
            
            # Detect which files might need updates
            code_blocks = detect_code_blocks_with_filenames(full_response)
            
            # Match code blocks with actual attachments
            files_to_update = []
            for block in code_blocks:
                for att in attachments:
                    if att.filename.lower() in block['filename'].lower() or \
                       block['filename'].lower() in att.filename.lower():
                        files_to_update.append({
                            'attachment': att,
                            'code': block['code'],
                            'confidence': block['confidence']
                        })
                        break
            
            # Also check for explicit file mentions in response
            for att in attachments:
                if att.filename in full_response and \
                   any(word in full_response for word in ['update', 'modify', 'change', 'fix', 'ubah', 'perbaiki']):
                    
                    # Avoid duplicates
                    if not any(f['attachment'].id == att.id for f in files_to_update):
                        files_to_update.append({
                            'attachment': att,
                            'code': None,  # Will be generated by AI
                            'confidence': 'medium'
                        })
            
            # Apply updates
            if files_to_update:
                yield json.dumps({
                    "status": "update",
                    "message": f"✏️ Updating {len(files_to_update)} file(s)..."
                })
                
                updated_files = []
                
                with next(get_project_session(project_database)) as session:
                    for file_update in files_to_update:
                        att = file_update['attachment']
                        
                        # Get fresh attachment from session
                        fresh_att = session.get(models.Attachment, att.id)
                        if not fresh_att:
                            continue
                        
                        # Perform intelligent update
                        new_version = await intelligent_file_update(
                            fresh_att,
                            user_query,
                            full_response,
                            file_context,
                            session
                        )
                        
                        if new_version:
                            updated_files.append(new_version)
                
                # Notify user about updates
                if updated_files:
                    update_notification = "\n\n---\n### ✨ Files Updated:\n\n"
                    for file in updated_files:
                        update_notification += f"- **{file.filename}** (v{file.version}) - {file.modification_summary}\n"
                    
                    yield update_notification
                    
                    # Store which files were modified
                    modified_ids = [f.id for f in updated_files]
                else:
                    modified_ids = []
            else:
                modified_ids = []
        else:
            modified_ids = []
        
        # STAGE 6: Save to database
        yield json.dumps({"status": "done"})
        
        with next(get_project_session(project_database)) as session:
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
        
        yield json.dumps({
            "status": "error",
            "message": f"Server error: {str(e)[:100]}"
        })
