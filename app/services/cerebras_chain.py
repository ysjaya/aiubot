# app/services/cerebras_chain_draft.py
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
from app.services.code_validator import CodeCompletenessValidator, validate_and_retry

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

CRITICAL RULES FOR CODE GENERATION - READ CAREFULLY:
==================================================
✅ RULE 1: ALWAYS write 100% COMPLETE code - NEVER truncate
✅ RULE 2: Include ALL imports, ALL functions, ALL classes - ZERO omissions
✅ RULE 3: Write the ENTIRE file from first line to last line
✅ RULE 4: Never use placeholders like "... rest of code" or "... kode lainnya"
✅ RULE 5: If code is long, write it completely anyway - no shortcuts allowed
✅ RULE 6: Every function MUST have complete implementation - no stubs
✅ RULE 7: Every class MUST have all methods fully written - no TODO comments
✅ RULE 8: NEVER write "# ... (continue)" or similar truncation markers
✅ RULE 9: NEVER assume user will fill in missing parts
✅ RULE 10: NEVER truncate or summarize code sections
==================================================

USER EXPECTS: 100% COMPLETE, READY-TO-USE CODE FOR IMMEDIATE DOWNLOAD.

ABSOLUTELY NO EXCEPTIONS TO THESE RULES. IF YOU TRUNCATE CODE, IT WILL BE REJECTED.
"""

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

CRITICAL: If you provide code, it MUST be 100% COMPLETE from start to finish.
NO truncation, NO "...", NO shortcuts. User needs DOWNLOADABLE, WORKING CODE.

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
2. Generate the COMPLETE updated file content (100% LENGKAP, NO TRUNCATION)
3. Provide a clear summary of changes

CRITICAL REQUIREMENTS:
- The "content" field MUST contain the ENTIRE file from start to finish
- Include ALL imports, ALL functions, ALL classes
- Do NOT use "...", "rest of code", or any truncation markers
- Write the COMPLETE file as if user will download it immediately
- Every line of code must be present - no omissions

Respond with ONLY valid JSON:
{{
    "content": "COMPLETE FULL FILE CONTENT HERE - EVERY SINGLE LINE",
    "summary": "Brief description of changes",
    "changes": ["change 1", "change 2", "change 3"]
}}

REMEMBER: The content field must have the FULL FILE, not a snippet."""

# ==================== HELPER FUNCTIONS ====================

async def call_cerebras(messages: List[Dict]) -> str:
    """Call Cerebras API synchronously"""
    if not cerebras_client:
        raise Exception("Cerebras client not initialized")
    
    try:
        response = await asyncio.to_thread(
            cerebras_client.chat.completions.create,
            messages=messages,
            model="qwen-3-235b-a22b-instruct-2507",
            max_tokens=16384,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Cerebras API error: {e}")
        raise

def stream_cerebras(messages: List[Dict], max_tokens: int = 16384):
    """Stream Cerebras API response with configurable max_tokens"""
    if not cerebras_client:
        raise Exception("Cerebras client not initialized")
    
    try:
        return cerebras_client.chat.completions.create(
            messages=messages,
            model="qwen-3-235b-a22b-instruct-2507",
            max_tokens=max_tokens,
            temperature=0.7,
            stream=True
        )
    except Exception as e:
        logger.error(f"Cerebras streaming error: {e}")
        raise

def stream_cerebras_unlimited(messages: List[Dict], max_total_tokens: int = 100000):
    """Stream Cerebras API with auto-continue for unlimited output"""
    if not cerebras_client:
        raise Exception("Cerebras client not initialized")
    
    current_messages = messages.copy()
    total_generated = 0
    continue_count = 0
    max_continues = 20
    
    while continue_count < max_continues and total_generated < max_total_tokens:
        try:
            stream = cerebras_client.chat.completions.create(
                messages=current_messages,
                model="qwen-3-235b-a22b-instruct-2507",
                max_tokens=16384,
                temperature=0.7,
                stream=True
            )
            
            accumulated_response = ""
            finish_reason = None
            
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    accumulated_response += content
                    total_generated += len(content)
                    yield content
                
                if chunk.choices[0].finish_reason:
                    finish_reason = chunk.choices[0].finish_reason
            
            if finish_reason == "stop" or finish_reason is None:
                logger.info(f"[UNLIMITED] Stream completed normally after {continue_count} continues")
                break
            elif finish_reason == "length":
                logger.info(f"[UNLIMITED] Hit token limit, continuing... ({continue_count + 1}/{max_continues})")
                current_messages.append({
                    "role": "assistant",
                    "content": accumulated_response
                })
                current_messages.append({
                    "role": "user", 
                    "content": "Lanjutkan respons Anda dari posisi terakhir. INGAT: Tulis kode LENGKAP 100%, jangan gunakan '...' atau potong kode."
                })
                continue_count += 1
            else:
                logger.info(f"[UNLIMITED] Stopped with reason: {finish_reason}")
                break
                
        except Exception as e:
            logger.error(f"[UNLIMITED] Error during streaming: {e}")
            raise
    
    if continue_count >= max_continues:
        logger.warning(f"[UNLIMITED] Reached max continues limit ({max_continues})")
        yield "\n\n_[Output limit reached - maximum continuation attempts exceeded]_"
    elif total_generated >= max_total_tokens:
        logger.warning(f"[UNLIMITED] Reached total token limit ({max_total_tokens})")
        yield "\n\n_[Output limit reached - maximum total tokens generated]_"

async def generate_conversation_title(first_message: str) -> str:
    """Generate conversation title based on first message using AI"""
    if not cerebras_client:
        logger.warning("Cerebras client not available, using default title")
        return "New Conversation"
    
    try:
        messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant that generates short, concise conversation titles. Generate a title that is 2-5 words, descriptive, and captures the main topic. Respond ONLY with the title, nothing else."
            },
            {
                "role": "user",
                "content": f"Generate a short conversation title (2-5 words) for this message:\n\n{first_message[:200]}"
            }
        ]
        
        title = await call_cerebras(messages)
        title = title.strip().strip('"').strip("'")
        
        # Limit length
        if len(title) > 50:
            title = title[:50].strip()
        
        logger.info(f"[AI TITLE] Generated title: {title}")
        return title
        
    except Exception as e:
        logger.error(f"[AI TITLE] Failed to generate title: {e}")
        return "New Conversation"

async def get_conversation_context(conv_id: int):
    """Get conversation context including files and chat history"""
    with next(get_session()) as session:
        # Get attachments with LATEST status
        attachments = session.exec(
            select(models.Attachment)
            .where(models.Attachment.conversation_id == conv_id)
            .where(models.Attachment.status == models.FileStatus.LATEST)
            .order_by(models.Attachment.updated_at.desc())
        ).all()
        
        # Build file context
        file_context = ""
        if attachments:
            for att in attachments:
                status = att.get_display_status()
                file_context += f"\n## {status} {att.filename} (v{att.version})\n"
                file_context += f"```\n{att.content[:3000]}\n```\n"
        
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
            if match and any(keyword in line.lower() for keyword in ['update', 'modify', 'change', 'fix', 'in ', 'file']):
                current_file = match.group(1)
    
    return detected

async def save_to_draft_with_validation(
    conversation_id: int,
    filename: str,
    content: str,
    attachment_id: Optional[int],
    change_summary: str,
    change_details: List[str],
    session: Session
) -> Optional[models.DraftVersion]:
    """
    Save AI-generated code to DraftVersion with completeness validation
    
    Returns DraftVersion if successful, None if validation fails
    """
    try:
        logger.info(f"[DRAFT] Saving draft for {filename}...")
        
        # Validate completeness
        content_clean, validation_result = validate_and_retry(content, filename)
        
        if not validation_result['is_complete']:
            logger.error(f"[DRAFT] ❌ Code validation FAILED for {filename}")
            logger.error(f"[DRAFT] Issues: {validation_result['issues']}")
            # Save draft but mark as incomplete
            is_complete = False
            completeness_score = validation_result['score']
        else:
            logger.info(f"[DRAFT] ✅ Code validation PASSED for {filename} (score: {validation_result['score']:.2f})")
            is_complete = True
            completeness_score = validation_result['score']
        
        # Compute hash and length
        content_hash = models.DraftVersion.compute_hash(models.DraftVersion(
            conversation_id=conversation_id,
            filename=filename,
            content=content,
            content_hash="",
            content_length=len(content)
        ))
        
        # Get next version number
        existing_drafts = session.exec(
            select(models.DraftVersion)
            .where(models.DraftVersion.conversation_id == conversation_id)
            .where(models.DraftVersion.filename == filename)
        ).all()
        
        next_version = max([d.version_number for d in existing_drafts], default=0) + 1
        
        # Create draft
        draft = models.DraftVersion(
            conversation_id=conversation_id,
            filename=filename,
            original_filename=filename,
            attachment_id=attachment_id,
            content=content,
            content_hash=content_hash,
            content_length=len(content),
            version_number=next_version,
            status=models.DraftStatus.PENDING if not is_complete else models.DraftStatus.APPROVED,
            is_complete=is_complete,
            has_syntax_errors=False,
            completeness_score=completeness_score,
            change_summary=change_summary,
            change_details=json.dumps(change_details),
            ai_model="cerebras",
            generation_metadata=json.dumps({
                "validation": validation_result,
                "created_at": datetime.utcnow().isoformat()
            })
        )
        
        session.add(draft)
        session.commit()
        session.refresh(draft)
        
        logger.info(f"[DRAFT] ✅ Saved draft v{next_version} for {filename} (complete={is_complete}, score={completeness_score:.2f})")
        
        return draft
        
    except Exception as e:
        logger.error(f"[DRAFT] ❌ Error saving draft for {filename}: {e}", exc_info=True)
        return None

async def promote_draft_to_attachment(
    draft: models.DraftVersion,
    session: Session
) -> Optional[models.Attachment]:
    """
    Promote an approved draft to Attachment with LATEST status
    Auto-promote if draft is complete and approved
    """
    try:
        if not draft.is_complete:
            logger.warning(f"[PROMOTE] ⚠️ Cannot promote incomplete draft {draft.filename}")
            return None
        
        logger.info(f"[PROMOTE] Promoting draft {draft.filename} v{draft.version_number} to LATEST...")
        
        # Mark old LATEST as MODIFIED
        old_latest = session.exec(
            select(models.Attachment)
            .where(models.Attachment.conversation_id == draft.conversation_id)
            .where(models.Attachment.filename == draft.filename)
            .where(models.Attachment.status == models.FileStatus.LATEST)
        ).first()
        
        if old_latest:
            old_latest.status = models.FileStatus.MODIFIED
            session.add(old_latest)
        
        # Determine version number for new Attachment
        all_attachments = session.exec(
            select(models.Attachment)
            .where(models.Attachment.conversation_id == draft.conversation_id)
            .where(models.Attachment.filename == draft.filename)
        ).all()
        
        next_att_version = max([a.version for a in all_attachments], default=0) + 1
        
        # Create new LATEST Attachment
        new_att = models.Attachment(
            conversation_id=draft.conversation_id,
            filename=draft.filename,
            original_filename=draft.original_filename,
            file_path=draft.filename,
            content=draft.content,
            content_hash=draft.content_hash,
            mime_type="text/plain",
            size_bytes=draft.content_length,
            status=models.FileStatus.LATEST,
            version=next_att_version,
            parent_file_id=old_latest.id if old_latest else None,
            modification_summary=draft.change_summary,
            import_source="ai_draft",
            import_metadata=json.dumps({
                "draft_id": draft.id,
                "draft_version": draft.version_number,
                "promoted_at": datetime.utcnow().isoformat()
            })
        )
        
        session.add(new_att)
        
        # Mark draft as PROMOTED
        draft.status = models.DraftStatus.PROMOTED
        draft.promoted_at = datetime.utcnow()
        session.add(draft)
        
        session.commit()
        session.refresh(new_att)
        
        logger.info(f"[PROMOTE] ✅ {draft.filename} promoted to Attachment v{next_att_version} with LATEST status")
        
        return new_att
        
    except Exception as e:
        logger.error(f"[PROMOTE] ❌ Error promoting draft {draft.filename}: {e}", exc_info=True)
        return None

async def intelligent_file_update(
    attachment: models.Attachment,
    user_request: str,
    ai_response: str,
    project_files: str,
    session: Session
) -> Optional[models.Attachment]:
    """
    Intelligently update a file based on conversation context
    Uses DraftVersion system with validation
    """
    try:
        logger.info(f"[FILE UPDATE] Processing: {attachment.filename}")
        
        # Build intelligent update prompt with COMPLETE CODE enforcement
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
            
            # Save to draft with validation
            draft = await save_to_draft_with_validation(
                conversation_id=attachment.conversation_id,
                filename=attachment.filename,
                content=new_content,
                attachment_id=attachment.id,
                change_summary=summary,
                change_details=changes,
                session=session
            )
            
            if not draft:
                logger.error(f"[FILE UPDATE] ❌ Failed to create draft for {attachment.filename}")
                return None
            
            # Auto-promote if complete
            if draft.is_complete and draft.status == models.DraftStatus.APPROVED:
                new_att = await promote_draft_to_attachment(draft, session)
                if new_att:
                    logger.info(f"[FILE UPDATE] ✅ {attachment.filename} updated and promoted to v{new_att.version}")
                    return new_att
            else:
                logger.warning(f"[FILE UPDATE] ⚠️ Draft created but not complete enough for auto-promotion")
                logger.warning(f"[FILE UPDATE] Score: {draft.completeness_score:.2f}, Issues: {json.loads(draft.generation_metadata).get('validation', {}).get('issues', [])}")
                return None
            
        except json.JSONDecodeError as e:
            logger.error(f"[FILE UPDATE] ❌ Failed to parse AI response: {e}")
            return None
            
    except Exception as e:
        logger.error(f"[FILE UPDATE] ❌ Error updating {attachment.filename}: {e}", exc_info=True)
        return None

# ==================== MAIN AI CHAIN ====================

async def ai_chain_stream(messages, conv_id: int, unlimited: bool = True):
    """
    Enhanced AI chain with intelligent file analysis, draft system, and completeness validation
    """
    user_query = messages[-1]['content']
    logger.info(f"[AI CHAIN] Starting for conv {conv_id} (unlimited={unlimited})")
    
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
        if unlimited:
            yield json.dumps({"status": "update", "message": "🤖 Generating response (Unlimited Mode - 100% Complete Code)..."})
        else:
            yield json.dumps({"status": "update", "message": "🤖 Generating response (100% Complete Code)..."})
        
        main_prompt = PROMPT_WITH_CONTEXT.format(
            CONTEXT=file_context or "No files attached yet.",
            CONVERSATION_HISTORY=chat_history or "No previous conversation.",
            WEB_SNIPPETS=web_snippets or "No web search performed.",
            QUESTION=user_query
        )
        
        system_msg = {"role": "system", "content": PROMPT_SYSTEM}
        user_msg = {"role": "user", "content": main_prompt}
        
        # Stream response with unlimited or normal mode
        full_response = ""
        if unlimited:
            # Use unlimited streaming with auto-continue
            for content in stream_cerebras_unlimited([system_msg, user_msg], max_total_tokens=100000):
                full_response += content
                yield content
        else:
            # Use normal streaming
            stream = stream_cerebras([system_msg, user_msg], max_tokens=16384)
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
            
            # Apply updates using draft system
            if files_to_update:
                yield json.dumps({"status": "update", "message": f"✏️ Creating drafts for {len(files_to_update)} file(s)..."})
                
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
                    update_notification += "\n_Semua file di atas adalah LENGKAP 100% dan siap untuk di-commit._\n"
                    
                    yield update_notification
                    modified_ids = [f.id for f in updated_files]
                else:
                    modified_ids = []
                    yield "\n\n_⚠️ Catatan: Beberapa draft dibuat tapi tidak lengkap. Periksa draft untuk review manual._\n"
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
