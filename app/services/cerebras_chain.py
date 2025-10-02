# app/services/cerebras_chain.py
import os
import json
import asyncio
import re
import logging
from typing import List, Dict, Optional, AsyncGenerator, Coroutine
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta

from cerebras.cloud.sdk import Cerebras
from openai import OpenAI
from sqlmodel import Session, select
from pydantic import BaseModel

from app.db import models
from app.db.database import get_session
from app.core.config import settings
from app.services import web_tools, code_validator
from app.services.code_validator import CodeCompletenessValidator

logger = logging.getLogger(__name__)

# ==================== ENUMS AND MODELS ====================

class TaskType(str, Enum):
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    ARCHITECTURE = "architecture"
    DEBUGGING = "debugging"
    DOCUMENTATION = "documentation"
    WEB_SEARCH = "web_search"
    GENERAL = "general"

class TaskPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"

@dataclass
class Task:
    """Represents a single AI task with metadata"""
    id: str
    type: TaskType
    priority: TaskPriority
    content: str
    context: Dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    status: TaskStatus = field(default=TaskStatus.PENDING)
    retry_count: int = 0
    max_retries: int = 3
    dependencies: List[str] = field(default_factory=list)
    result: Optional[Dict] = None

@dataclass
class WebSearchResult:
    """Enhanced web search result with metadata"""
    title: str
    snippet: str
    url: str
    domain: str
    relevance_score: float
    content_preview: str = ""
    search_timestamp: datetime = field(default_factory=datetime.utcnow)

@dataclass
class AIResponse:
    """Standardized AI response format"""
    content: str
    task_id: str
    model_used: str
    processing_time: float
    tokens_used: int
    confidence_score: float
    sources: List[WebSearchResult] = field(default_factory=list)
    related_tasks: List[Task] = field(default_factory=list)

# ==================== ENHANCED CLIENTS ====================

class AIClientManager:
    """Manages AI clients with failover and load balancing"""
    
    def __init__(self):
        self.cerebras_client = None
        self.nvidia_client = None
        self.active_clients = []
        self.init_clients()
    
    def init_clients(self):
        """Initialize AI clients with error handling"""
        # Initialize Cerebras client
        try:
            if settings.CEREBRAS_API_KEY:
                self.cerebras_client = Cerebras(api_key=settings.CEREBRAS_API_KEY)
                self.active_clients.append('cerebras')
                logger.info("✅ Cerebras client initialized")
            else:
                logger.warning("⚠️ CEREBRAS_API_KEY not configured")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Cerebras client: {e}")
        
        # Initialize NVIDIA client
        try:
            if settings.NVIDIA_API_KEY:
                self.nvidia_client = OpenAI(
                    base_url="https://integrate.api.nvidia.com/v1",
                    api_key=settings.NVIDIA_API_KEY
                )
                self.active_clients.append('nvidia')
                logger.info("✅ NVIDIA client initialized")
            else:
                logger.warning("⚠️ NVIDIA_API_KEY not configured")
        except Exception as e:
            logger.error(f"❌ Failed to initialize NVIDIA client: {e}")
        
        if not self.active_clients:
            logger.error("❌ No AI clients available! Check API keys.")
            raise RuntimeError("No AI clients available")
    
    async def call_cerebras(self, messages: List[Dict], model: str = "llama-4-maverick-17b-128e-instruct", 
                           max_tokens: int = 4096, temperature: float = 0.7) -> Optional[Dict]:
        """Call Cerebras API with error handling"""
        if not self.cerebras_client:
            return None
        
        try:
            response = await asyncio.to_thread(
                self.cerebras_client.chat.completions.create,
                messages=messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=False
            )
            
            return {
                "content": response.choices[0].message.content,
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            }
        except Exception as e:
            logger.error(f"Error calling Cerebras: {e}")
            return None
    
    async def call_nvidia(self, messages: List[Dict], model: str = "meta/llama-3.1-405b-instruct", 
                         max_tokens: int = 4096, temperature: float = 0.7) -> Optional[Dict]:
        """Call NVIDIA API with error handling"""
        if not self.nvidia_client:
            return None
        
        try:
            response = await asyncio.to_thread(
                self.nvidia_client.chat.completions.create,
                messages=messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=False
            )
            
            return {
                "content": response.choices[0].message.content,
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            }
        except Exception as e:
            logger.error(f"Error calling NVIDIA: {e}")
            return None
    
    async def call_best_available(self, messages: List[Dict], model_hint: str = "", 
                                 max_tokens: int = 4096, temperature: float = 0.7) -> Optional[Dict]:
        """Call the best available client with failover"""
        # Try Cerebras first
        if 'cerebras' in self.active_clients and ('cerebras' in model_hint.lower() or not model_hint):
            result = await self.call_cerebras(messages, "llama-4-maverick-17b-128e-instruct", max_tokens, temperature)
            if result:
                return result
        
        # Fall back to NVIDIA
        if 'nvidia' in self.active_clients:
            model = model_hint or "meta/llama-3.1-405b-instruct"
            result = await self.call_nvidia(messages, model, max_tokens, temperature)
            if result:
                return result
        
        # Last resort: Try Cerebras again with different model
        if 'cerebras' in self.active_clients:
            result = await self.call_cerebras(messages, "llama-3.1-70b", max_tokens, temperature)
            if result:
                return result
        
        logger.error("❌ All AI clients failed!")
        return None

# ==================== DEEP WEB SEARCH ====================

class DeepWebSearch:
    """Advanced web search with multiple strategies and deep analysis"""
    
    def __init__(self):
        self.max_results_per_query = 10
        self.max_search_depth = 3
        self.search_cache = {}
        self.cache_ttl = timedelta(minutes=30)
        self.session = None
    
    def _get_cache_key(self, query: str, search_type: str) -> str:
        """Generate cache key for query"""
        return f"{search_type}:{query.lower().strip()}"
    
    def _is_cache_valid(self, timestamp: datetime) -> bool:
        """Check if cache entry is still valid"""
        return datetime.utcnow() - timestamp < self.cache_ttl
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc
        except:
            return "unknown"
    
    async def _search_duckduckgo(self, query: str) -> List[WebSearchResult]:
        """Basic DuckDuckGo search"""
        try:
            results = web_tools.search_web(query, self.max_results_per_query)
            web_results = []
            
            for item in results.get("results", []):
                web_results.append(WebSearchResult(
                    title=item.get("title", ""),
                    snippet=item.get("snippet", ""),
                    url=item.get("url", ""),
                    domain=self._extract_domain(item.get("url", "")),
                    relevance_score=0.8,
                    content_preview=""
                ))
            
            return web_results
        except Exception as e:
            logger.error(f"Error in DuckDuckGo search: {e}")
            return []
    
    async def _search_serpapi(self, query: str) -> List[WebSearchResult]:
        """Search using SERP API for more comprehensive results"""
        if not hasattr(settings, 'SERPAPI_API_KEY') or not settings.SERPAPI_API_KEY:
            logger.debug("SERPAPI_API_KEY not configured, skipping SERP API search")
            return []
        
        try:
            import httpx
            
            params = {
                'engine': 'google',
                'q': query,
                'api_key': settings.SERPAPI_API_KEY,
                'num': self.max_results_per_query,
                'gl': 'us',
                'hl': 'en'
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get('https://serpapi.com/search', params=params)
                response.raise_for_status()
                data = response.json()
                
                results = []
                for item in data.get('organic_results', [])[:self.max_results_per_query]:
                    title = item.get('title', '')
                    snippet = item.get('snippet', '')
                    link = item.get('link', '')
                    
                    # Calculate relevance score based on position
                    position = item.get('position', 1)
                    relevance_score = max(0.5, 1.0 - (position * 0.1))
                    
                    results.append(WebSearchResult(
                        title=title,
                        snippet=snippet,
                        url=link,
                        domain=self._extract_domain(link),
                        relevance_score=relevance_score,
                        content_preview=""
                    ))
                
                return results
                
        except Exception as e:
            logger.error(f"Error in SERP API search: {e}")
            return []
    
    async def _search_bing(self, query: str) -> List[WebSearchResult]:
        """Search using Bing API"""
        if not hasattr(settings, 'BING_API_KEY') or not settings.BING_API_KEY:
            logger.debug("BING_API_KEY not configured, skipping Bing search")
            return []
        
        try:
            import httpx
            
            headers = {
                'Ocp-Apim-Subscription-Key': settings.BING_API_KEY
            }
            
            params = {
                'q': query,
                'count': self.max_results_per_query,
                'mkt': 'en-US'
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    'https://api.bing.microsoft.com/v7.0/search',
                    headers=headers,
                    params=params
                )
                response.raise_for_status()
                data = response.json()
                
                results = []
                for item in data.get('webPages', {}).get('value', [])[:self.max_results_per_query]:
                    title = item.get('name', '')
                    snippet = item.get('snippet', '')
                    url = item.get('url', '')
                    
                    results.append(WebSearchResult(
                        title=title,
                        snippet=snippet,
                        url=url,
                        domain=self._extract_domain(url),
                        relevance_score=0.7,
                        content_preview=""
                    ))
                
                return results
                
        except Exception as e:
            logger.error(f"Error in Bing search: {e}")
            return []
    
    async def _scrape_and_enhance(self, results: List[WebSearchResult]) -> List[WebSearchResult]:
        """Scrape content from top results and enhance with actual content"""
        if not results:
            return []
        
        # Sort by relevance and take top 5
        top_results = sorted(results, key=lambda x: x.relevance_score, reverse=True)[:5]
        enhanced_results = []
        
        try:
            import httpx
            
            async def scrape_single(result: WebSearchResult):
                try:
                    # Add delay to be respectful
                    await asyncio.sleep(1)
                    
                    content_data = web_tools.scrape_url(result.url)
                    content_text = content_data.get("text", "")
                    
                    if len(content_text) > 100:
                        # Extract more relevant content preview
                        preview = content_text[:500] + "..." if len(content_text) > 500 else content_text
                        
                        # Update relevance based on content match
                        query_words = self.current_query.lower().split()
                        content_lower = content_text.lower()
                        matches = sum(1 for word in query_words if word in content_lower)
                        enhancement_factor = min(1.5, 1.0 + (matches * 0.1))
                        
                        enhanced_result = WebSearchResult(
                            title=result.title,
                            snippet=result.snippet,
                            url=result.url,
                            domain=result.domain,
                            relevance_score=min(1.0, result.relevance_score * enhancement_factor),
                            content_preview=preview,
                            search_timestamp=result.search_timestamp
                        )
                        
                        return enhanced_result
                    else:
                        return result
                        
                except Exception as e:
                    logger.warning(f"Failed to scrape {result.url}: {e}")
                    return result
            
            # Scrape in parallel
            scrape_tasks = [scrape_single(result) for result in top_results]
            scraped_results = await asyncio.gather(*scrape_tasks, return_exceptions=True)
            
            for result in scraped_results:
                if isinstance(result, WebSearchResult):
                    enhanced_results.append(result)
                else:
                    logger.warning(f"Scraping task failed: {result}")
            
            # Add remaining results
            remaining_results = [r for r in results if r not in top_results]
            enhanced_results.extend(remaining_results)
            
            return enhanced_results
            
        except Exception as e:
            logger.error(f"Error in scrape enhancement: {e}")
            return results
    
    async def deep_search(self, query: str, depth: int = 2) -> List[WebSearchResult]:
        """Perform deep web search with multiple strategies"""
        self.current_query = query
        
        # Check cache first
        cache_key = self._get_cache_key(query, "deep_search")
        if cache_key in self.search_cache:
            cached_data = self.search_cache[cache_key]
            if self._is_cache_valid(cached_data['timestamp']):
                logger.info(f"Using cached results for query: {query}")
                return cached_data['results']
        
        logger.info(f"Performing deep web search: {query}")
        
        all_results = []
        
        # Strategy 1: Basic search
        basic_results = await self._search_duckduckgo(query)
        all_results.extend(basic_results)
        
        # Strategy 2: SERP API (if available)
        serp_results = await self._search_serpapi(query)
        all_results.extend(serp_results)
        
        # Strategy 3: Bing (if available)
        bing_results = await self._search_bing(query)
        all_results.extend(bing_results)
        
        # Remove duplicates
        seen_urls = set()
        unique_results = []
        for result in all_results:
            if result.url not in seen_urls:
                seen_urls.add(result.url)
                unique_results.append(result)
        
        # Enhance with scraping if depth > 1
        if depth > 1 and unique_results:
            enhanced_results = await self._scrape_and_enhance(unique_results)
            # Sort by relevance
            final_results = sorted(enhanced_results, key=lambda x: x.relevance_score, reverse=True)
        else:
            final_results = sorted(unique_results, key=lambda x: x.relevance_score, reverse=True)
        
        # Cache results
        self.search_cache[cache_key] = {
            'results': final_results,
            'timestamp': datetime.utcnow()
        }
        
        logger.info(f"Deep search completed: {len(final_results)} results for '{query}'")
        return final_results

# ==================== TASK HANDLERS ====================

class BaseTaskHandler:
    """Base class for task handlers"""
    
    def __init__(self, ai_client: AIClientManager, deep_search: DeepWebSearch):
        self.ai_client = ai_client
        self.deep_search = deep_search
        self.task_type = TaskType.GENERAL
    
    async def can_handle(self, task: Task) -> bool:
        """Check if this handler can process the task"""
        return task.type == self.task_type
    
    async def process(self, task: Task, session: Session) -> AIResponse:
        """Process the task and return response"""
        raise NotImplementedError

class CodeGenerationHandler(BaseTaskHandler):
    """Handles code generation tasks"""
    
    def __init__(self, ai_client: AIClientManager, deep_search: DeepWebSearch):
        super().__init__(ai_client, deep_search)
        self.task_type = TaskType.CODE_GENERATION
    
    async def _get_project_files(self, session: Session, conversation_id: int) -> str:
        """Get project files context"""
        try:
            attachments = session.exec(
                select(models.Attachment)
                .where(models.Attachment.conversation_id == conversation_id)
                .where(models.Attachment.status == models.FileStatus.LATEST)
            ).all()
            
            files_context = "PROJECT FILES:\n"
            for att in attachments:
                files_context += f"\n--- {att.filename} ---\n"
                if att.content and len(att.content) < 5000:  # Limit content size
                    files_context += att.content
                else:
                    files_context += "(Content too long to display)"
            
            return files_context
            
        except Exception as e:
            logger.error(f"Error getting project files: {e}")
            return "PROJECT FILES: Unable to retrieve"
    
    async def process(self, task: Task, session: Session) -> AIResponse:
        start_time = datetime.utcnow()
        
        # Get conversation context
        conversation_id = task.context.get('conversation_id', 0)
        unlimited_mode = task.context.get('unlimited', True)
        
        # Get project files
        files_context = await self._get_project_files(session, conversation_id)
        
        # Construct messages
        system_prompt = f"""{PROMPT_SYSTEM}

You are generating code based on the following project context:
{files_context}

Follow these steps for code generation:
1. Analyze requirements thoroughly
2. Consider architecture and dependencies
3. Write complete, production-ready code
4. Include necessary imports and error handling
5. Add comments for complex logic
6. Ensure code is 100% complete (no truncation)
7. Follow existing code style and patterns

Remember: USER EXPECTS 100% COMPLETE, READY-TO-USE CODE.
"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task.content}
        ]
        
        # Call AI with appropriate model
        model_hint = "cerebras" if unlimited_mode else ""
        ai_result = await self.ai_client.call_best_available(messages, model_hint, 4096, 0.7)
        
        if not ai_result:
            raise Exception("AI call failed")
        
        # Validate code completeness
        validation = CodeCompletenessValidator.validate_completeness(
            ai_result['content'], 
            "code.py"  # Default filename
        )
        
        # If code is incomplete, retry with specific instructions
        if not validation['is_complete'] and task.retry_count < task.max_retries:
            task.retry_count += 1
            task.status = TaskStatus.RETRYING
            
            retry_message = f"""The previous code was incomplete. Please provide the COMPLETE code without any truncation.

ISSUES DETECTED:
{chr(10).join(validation['issues'])}

WARNINGS:
{chr(10).join(validation['warnings'])}

Original request:
{task.content}

Provide the FULL, COMPLETE code with all parts implemented."""
            
            messages.append({"role": "assistant", "content": ai_result['content']})
            messages.append({"role": "user", "content": retry_message})
            
            ai_result = await self.ai_client.call_best_available(messages, model_hint, 4096, 0.7)
            
            if not ai_result:
                raise Exception("Retry AI call failed")
        
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        return AIResponse(
            content=ai_result['content'],
            task_id=task.id,
            model_used=ai_result['model'],
            processing_time=processing_time,
            tokens_used=ai_result['usage']['total_tokens'],
            confidence_score=0.9,
            sources=[]
        )

class WebSearchHandler(BaseTaskHandler):
    """Handles web search tasks"""
    
    def __init__(self, ai_client: AIClientManager, deep_search: DeepWebSearch):
        super().__init__(ai_client, deep_search)
        self.task_type = TaskType.WEB_SEARCH
    
    async def process(self, task: Task, session: Session) -> AIResponse:
        start_time = datetime.utcnow()
        
        # Perform deep search - FIX: Call the method, not the object
        search_results = await self.deep_search.deep_search(task.content, depth=2)
        
        # Format results for AI processing
        formatted_results = []
        for i, result in enumerate(search_results[:5]):  # Top 5 results
            formatted_results.append(f"""[{i+1}] {result.title}
URL: {result.url}
Relevance: {result.relevance_score:.2f}
Snippet: {result.snippet}
{'Content: ' + result.content_preview if result.content_preview else ''}""")
        
        results_text = "\n\n".join(formatted_results)
        
        # Ask AI to synthesize information
        system_prompt = """You are a research assistant that synthesizes information from multiple sources.
Analyze the search results and provide a comprehensive, well-organized answer.
Cite sources using [1], [2], etc. notation.
Focus on accuracy and relevance."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Based on these search results, answer the question:\n\n{task.content}\n\nSEARCH RESULTS:\n{results_text}"}
        ]
        
        ai_result = await self.ai_client.call_best_available(messages, "", 2048, 0.5)
        
        if not ai_result:
            raise Exception("AI call failed")
        
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        return AIResponse(
            content=ai_result['content'],
            task_id=task.id,
            model_used=ai_result['model'],
            processing_time=processing_time,
            tokens_used=ai_result['usage']['total_tokens'],
            confidence_score=0.8,
            sources=search_results[:5]
        )

class ArchitectureHandler(BaseTaskHandler):
    """Handles architecture design tasks"""
    
    def __init__(self, ai_client: AIClientManager, deep_search: DeepWebSearch):
        super().__init__(ai_client, deep_search)
        self.task_type = TaskType.ARCHITECTURE
    
    async def _get_tech_trends(self) -> str:
        """Get current technology trends via web search"""
        try:
            search_results = await self.deep_search("current best practices in software architecture 2025", depth=2)
            
            trends = "CURRENT TECHNOLOGY TRENDS:\n"
            for result in search_results[:3]:
                trends += f"- {result.title}: {result.snippet}\n"
            
            return trends
        except Exception as e:
            logger.warning(f"Could not get tech trends: {e}")
            return "CURRENT TECHNOLOGY TRENDS: Unable to retrieve"
    
    async def process(self, task: Task, session: Session) -> AIResponse:
        start_time = datetime.utcnow()
        
        # Get technology trends
        trends_context = await self._get_tech_trends()
        
        # Construct messages
        system_prompt = f"""{PROMPT_SYSTEM}

You are an expert software architect.
Consider current best practices and technology trends:
{trends_context}

When designing architecture:
1. Consider scalability and maintainability
2. Choose appropriate patterns and frameworks
3. Plan for security and performance
4. Document decisions and trade-offs
5. Provide clear implementation guidance

Focus on providing actionable, practical advice."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task.content}
        ]
        
        ai_result = await self.ai_client.call_best_available(messages, "cerebras", 3072, 0.8)
        
        if not ai_result:
            raise Exception("AI call failed")
        
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        return AIResponse(
            content=ai_result['content'],
            task_id=task.id,
            model_used=ai_result['model'],
            processing_time=processing_time,
            tokens_used=ai_result['usage']['total_tokens'],
            confidence_score=0.95,
            sources=[]
        )

class DebuggingHandler(BaseTaskHandler):
    """Handles debugging tasks"""
    
    def __init__(self, ai_client: AIClientManager, deep_search: DeepWebSearch):
        super().__init__(ai_client, deep_search)
        self.task_type = TaskType.DEBUGGING
    
    async def _get_error_context(self, session: Session, conversation_id: int) -> str:
        """Get error context from project"""
        try:
            # Get recent chats
            recent_chats = session.exec(
                select(models.Chat)
                .where(models.Chat.conversation_id == conversation_id)
                .order_by(models.Chat.created_at.desc())
                .limit(5)
            ).all()
            
            context = "RECENT CONVERSATION HISTORY:\n"
            for chat in reversed(recent_chats):
                context += f"User: {chat.user}\n"
                context += f"AI: {chat.ai_response}\n\n"
            
            # Get project files
            attachments = session.exec(
                select(models.Attachment)
                .where(models.Attachment.conversation_id == conversation_id)
                .where(models.Attachment.status == models.FileStatus.LATEST)
            ).all()
            
            context += "\nPROJECT FILES:\n"
            for att in attachments:
                if att.filename.endswith(('.py', '.js', '.ts', '.java', '.cpp')):
                    context += f"\n--- {att.filename} ---\n"
                    if att.content and len(att.content) < 3000:
                        context += att.content
            
            return context
            
        except Exception as e:
            logger.error(f"Error getting error context: {e}")
            return "ERROR CONTEXT: Unable to retrieve"
    
    async def process(self, task: Task, session: Session) -> AIResponse:
        start_time = datetime.utcnow()
        
        # Get conversation context
        conversation_id = task.context.get('conversation_id', 0)
        
        # Get error context
        error_context = await self._get_error_context(session, conversation_id)
        
        # Construct messages
        system_prompt = f"""{PROMPT_SYSTEM}

You are a debugging expert.
Use the following approach:
1. Reproduce the issue based on symptoms
2. Analyze error messages and stack traces
3. Check for common patterns and anti-patterns
4. Suggest systematic troubleshooting steps
5. Provide specific code fixes with explanations

Focus on root cause analysis, not just symptoms."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Debugging context:\n{error_context}\n\nProblem: {task.content}"}
        ]
        
        ai_result = await self.ai_client.call_best_available(messages, "cerebras", 3072, 0.6)
        
        if not ai_result:
            raise Exception("AI call failed")
        
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        return AIResponse(
            content=ai_result['content'],
            task_id=task.id,
            model_used=ai_result['model'],
            processing_time=processing_time,
            tokens_used=ai_result['usage']['total_tokens'],
            confidence_score=0.9,
            sources=[]
        )

class DocumentationHandler(BaseTaskHandler):
    """Handles documentation tasks"""
    
    def __init__(self, ai_client: AIClientManager, deep_search: DeepWebSearch):
        super().__init__(ai_client, deep_search)
        self.task_type = TaskType.DOCUMENTATION
    
    async def _get_code_samples(self, session: Session, conversation_id: int) -> str:
        """Get code samples for documentation"""
        try:
            attachments = session.exec(
                select(models.Attachment)
                .where(models.Attachment.conversation_id == conversation_id)
                .where(models.Attachment.status == models.FileStatus.LATEST)
            ).all()
            
            samples = "CODE SAMPLES:\n"
            for att in attachments[:3]:  # First 3 files
                if att.content and len(att.content) < 2000:
                    samples += f"\n--- {att.filename} ---\n"
                    lines = att.content.split('\n')
                    # Show first 20 lines
                    samples += '\n'.join(lines[:20])
                    if len(lines) > 20:
                        samples += "\n... (truncated)"
            
            return samples
            
        except Exception as e:
            logger.error(f"Error getting code samples: {e}")
            return "CODE SAMPLES: Unable to retrieve"
    
    async def process(self, task: Task, session: Session) -> AIResponse:
        start_time = datetime.utcnow()
        
        # Get conversation context
        conversation_id = task.context.get('conversation_id', 0)
        
        # Get code samples
        code_samples = await self._get_code_samples(session, conversation_id)
        
        # Construct messages
        system_prompt = f"""{PROMPT_SYSTEM}

You are a technical documentation expert.
Create clear, comprehensive documentation with:
1. Overview and purpose
2. Installation and setup
3. Usage examples
4. Configuration options
5. Troubleshooting
6. Best practices

Use markdown formatting for structure.
Include code samples where appropriate."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Code context:\n{code_samples}\n\nDocumentation request: {task.content}"}
        ]
        
        ai_result = await self.ai_client.call_best_available(messages, "", 3072, 0.7)
        
        if not ai_result:
            raise Exception("AI call failed")
        
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        return AIResponse(
            content=ai_result['content'],
            task_id=task.id,
            model_used=ai_result['model'],
            processing_time=processing_time,
            tokens_used=ai_result['usage']['total_tokens'],
            confidence_score=0.85,
            sources=[]
        )

class GeneralHandler(BaseTaskHandler):
    """Handles general tasks"""
    
    def __init__(self, ai_client: AIClientManager, deep_search: DeepWebSearch):
        super().__init__(ai_client, deep_search)
        self.task_type = TaskType.GENERAL
    
    async def process(self, task: Task, session: Session) -> AIResponse:
        start_time = datetime.utcnow()
        
        # Construct messages
        system_prompt = f"""{PROMPT_SYSTEM}

You are a general AI assistant.
Provide thoughtful, well-reasoned responses.
When appropriate, ask clarifying questions.
Break down complex problems into steps.
Consider multiple perspectives.
Provide actionable advice."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task.content}
        ]
        
        ai_result = await self.ai_client.call_best_available(messages, "", 2048, 0.7)
        
        if not ai_result:
            raise Exception("AI call failed")
        
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        return AIResponse(
            content=ai_result['content'],
            task_id=task.id,
            model_used=ai_result['model'],
            processing_time=processing_time,
            tokens_used=ai_result['usage']['total_tokens'],
            confidence_score=0.8,
            sources=[]
        )

# ==================== TASK ROUTER ====================

class TaskRouter:
    """Routes tasks to appropriate handlers"""
    
    def __init__(self):
        self.ai_client = AIClientManager()
        self.deep_search = DeepWebSearch()
        self.handlers = {}
        self._initialize_handlers()
    
    def _initialize_handlers(self):
        """Initialize all task handlers"""
        handlers = [
            CodeGenerationHandler(self.ai_client, self.deep_search),
            WebSearchHandler(self.ai_client, self.deep_search),
            ArchitectureHandler(self.ai_client, self.deep_search),
            DebuggingHandler(self.ai_client, self.deep_search),
            DocumentationHandler(self.ai_client, self.deep_search),
            GeneralHandler(self.ai_client, self.deep_search)
        ]
        
        for handler in handlers:
            self.handlers[handler.task_type] = handler
            logger.info(f"✅ Initialized handler for {handler.task_type}")
    
    async def _classify_task(self, task: Task) -> TaskType:
        """Classify task based on content"""
        content_lower = task.content.lower()
        
        # Keywords for code generation
        code_keywords = ['code', 'implement', 'function', 'class', 'variable', 'program', 'script', 'build', 'create']
        if any(kw in content_lower for kw in code_keywords):
            return TaskType.CODE_GENERATION
        
        # Keywords for web search
        search_keywords = ['search', 'find', 'lookup', 'what is', 'who is', 'when', 'where', 'how to', 'tutorial']
        if any(kw in content_lower for kw in search_keywords):
            return TaskType.WEB_SEARCH
        
        # Keywords for architecture
        arch_keywords = ['architecture', 'design', 'structure', 'framework', 'pattern', 'scalability', 'microservices']
        if any(kw in content_lower for kw in arch_keywords):
            return TaskType.ARCHITECTURE
        
        # Keywords for debugging
        debug_keywords = ['error', 'bug', 'fix', 'debug', 'crash', 'exception', 'problem', 'not working']
        if any(kw in content_lower for kw in debug_keywords):
            return TaskType.DEBUGGING
        
        # Keywords for documentation
        doc_keywords = ['document', 'documentation', 'explain', 'tutorial', 'guide', 'manual', 'how does it work']
        if any(kw in content_lower for kw in doc_keywords):
            return TaskType.DOCUMENTATION
        
        # Default to general
        return TaskType.GENERAL
    
    async def process_task(self, task: Task, session: Session) -> AIResponse:
        """Process a task by routing to appropriate handler"""
        try:
            # Classify task if not already classified
            if task.type == TaskType.GENERAL:
                task.type = await self._classify_task(task)
                logger.info(f"Classified task as: {task.type}")
            
            # Find appropriate handler
            handler = self.handlers.get(task.type)
            if not handler:
                logger.warning(f"No handler found for task type: {task.type}")
                handler = self.handlers[TaskType.GENERAL]
            
            # Process task
            task.status = TaskStatus.PROCESSING
            logger.info(f"Processing {task.type} task: {task.id}")
            
            response = await handler.process(task, session)
            task.status = TaskStatus.COMPLETED
            task.result = response.__dict__
            
            logger.info(f"Task completed: {task.id} ({task.type})")
            return response
            
        except Exception as e:
            logger.error(f"Error processing task {task.id}: {e}")
            task.status = TaskStatus.FAILED
            task.result = {"error": str(e)}
            
            # Check if we can retry
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.status = TaskStatus.RETRYING
                logger.info(f"Task {task.id} will be retried ({task.retry_count}/{task.max_retries})")
                raise
            
            # Final failure
            raise

# ==================== MAIN CHAINING FUNCTIONS ====================

# Global task router instance
_task_router = None

def get_task_router() -> TaskRouter:
    """Get or create task router instance"""
    global _task_router
    if _task_router is None:
        _task_router = TaskRouter()
    return _task_router

async def ai_chain_stream(
    messages: List[Dict],
    conversation_id: int,
    unlimited: bool = True
) -> AsyncGenerator[str, None]:
    """
    Main streaming AI chain with comprehensive error handling and task routing
    """
    logger.info(f"Starting AI chain stream for conversation {conversation_id}")
    
    try:
        # Extract the latest user message
        user_message = ""
        for msg in reversed(messages):
            if msg["role"] == "user":
                user_message = msg["content"]
                break
        
        if not user_message:
            error_data = {"status": "error", "message": "No user message found"}
            yield f"data: {json.dumps(error_data)}\n\n"
            return
        
        # Create a new task
        task_id = f"task_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}"
        task = Task(
            id=task_id,
            type=TaskType.GENERAL,
            priority=TaskPriority.MEDIUM,
            content=user_message,
            context={
                "conversation_id": conversation_id,
                "unlimited": unlimited,
                "messages": messages[:-1]  # Previous messages as context
            }
        )
        
        # Get database session
        with next(get_session()) as session:
            try:
                # Get task router
                router = get_task_router()
                
                # Process task
                response = await router.process_task(task, session)
                
                # Stream the response
                chunk_size = 50
                content = response.content
                
                for i in range(0, len(content), chunk_size):
                    chunk = content[i:i + chunk_size]
                    if chunk.strip():
                        yield f"data: {chunk}\n\n"
                        await asyncio.sleep(0.01)  # Small delay for smooth streaming
                
                # Send final status update
                final_data = {
                    "status": "done",
                    "task_id": task_id,
                    "model": response.model_used,
                    "processing_time": response.processing_time,
                    "tokens": response.tokens_used,
                    "confidence": response.confidence_score
                }
                
                if response.sources:
                    final_data["sources"] = [
                        {
                            "title": src.title,
                            "url": src.url,
                            "relevance": src.relevance_score
                        }
                        for src in response.sources
                    ]
                
                yield f"data: {json.dumps(final_data)}\n\n"
                
            except Exception as e:
                logger.error(f"Error in AI chain processing: {e}")
                
                # Try to recover with simpler approach
                if "rate limit" in str(e).lower() or "quota" in str(e).lower():
                    # Wait and retry
                    await asyncio.sleep(5)
                    try:
                        # Fallback to simple response
                        simple_response = "I'm experiencing high demand right now. Let me try to help you with a simpler response."
                        yield f"data: {simple_response}\n\n"
                        
                        final_data = {
                            "status": "done_recovered",
                            "message": "Responded with simplified answer due to high demand"
                        }
                        yield f"data: {json.dumps(final_data)}\n\n"
                        return
                    except:
                        pass
                
                # Final error response
                error_data = {
                    "status": "error",
                    "message": f"AI processing failed: {str(e)}",
                    "recovery_attempt": False
                }
                yield f"data: {json.dumps(error_data)}\n\n"
                
    except Exception as e:
        logger.error(f"Critical error in ai_chain_stream: {e}")
        error_data = {
            "status": "critical_error",
            "message": f"System error: {str(e)}"
        }
        yield f"data: {json.dumps(error_data)}\n\n"

async def generate_conversation_title(messages: List[Dict], conversation_id: int) -> str:
    """
    Generate a concise title for a conversation based on the messages
    """
    try:
        # Get the first user message
        first_user_message = ""
        for msg in messages:
            if msg["role"] == "user":
                first_user_message = msg["content"]
                break
        
        if not first_user_message:
            return "New Conversation"
        
        # Truncate if too long
        if len(first_user_message) > 200:
            first_user_message = first_user_message[:200] + "..."
        
        # Ask AI to generate a short title
        system_prompt = """Generate a short, descriptive title (3-6 words) for this conversation.
The title should capture the main topic or question.
Return ONLY the title, nothing else."""
        
        messages_for_title = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Generate a title for this conversation:\n\n{first_user_message}"}
        ]
        
        # Get AI client
        router = get_task_router()
        
        # Call AI with short response
        ai_result = await router.ai_client.call_best_available(
            messages_for_title, 
            "", 
            max_tokens=50, 
            temperature=0.7
        )
        
        if ai_result and ai_result['content']:
            title = ai_result['content'].strip()
            # Remove quotes if present
            title = title.strip('"\'')
            # Limit length
            if len(title) > 50:
                title = title[:47] + "..."
            return title
        
        # Fallback: Use first few words of user message
        words = first_user_message.split()[:5]
        return " ".join(words) + ("..." if len(words) == 5 else "")
        
    except Exception as e:
        logger.error(f"Error generating conversation title: {e}")
        return "New Conversation"

async def ai_chain_simple(
    messages: List[Dict],
    conversation_id: int,
    unlimited: bool = True
) -> str:
    """
    Simple AI chain that returns complete response (non-streaming)
    """
    logger.info(f"Starting simple AI chain for conversation {conversation_id}")
    
    try:
        # Extract the latest user message
        user_message = ""
        for msg in reversed(messages):
            if msg["role"] == "user":
                user_message = msg["content"]
                break
        
        if not user_message:
            return "Error: No user message found"
        
        # Create a new task
        task_id = f"task_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}"
        task = Task(
            id=task_id,
            type=TaskType.GENERAL,
            priority=TaskPriority.MEDIUM,
            content=user_message,
            context={
                "conversation_id": conversation_id,
                "unlimited": unlimited,
                "messages": messages[:-1]
            }
        )
        
        # Get database session
        with next(get_session()) as session:
            try:
                # Get task router
                router = get_task_router()
                
                # Process task
                response = await router.process_task(task, session)
                
                return response.content
                
            except Exception as e:
                logger.error(f"Error in simple AI chain: {e}")
                return f"Maaf, terjadi kesalahan saat memproses permintaan Anda: {str(e)}"
                
    except Exception as e:
        logger.error(f"Critical error in ai_chain_simple: {e}")
        return f"Maaf, sistem mengalami kesalahan internal: {str(e)}"

async def promote_draft_to_attachment(
    draft_id: int,
    conversation_id: int,
    session: Session
) -> Optional[models.Attachment]:
    """
    Promote a draft file to an attachment
    
    Args:
        draft_id: ID of the draft to promote
        conversation_id: ID of the conversation
        session: Database session
        
    Returns:
        The created attachment or None if failed
    """
    try:
        # Get the draft
        draft = session.get(models.Draft, draft_id)
        if not draft or draft.conversation_id != conversation_id:
            logger.error(f"Draft {draft_id} not found or doesn't belong to conversation {conversation_id}")
            return None
        
        # Check if attachment with same filename already exists
        existing = session.exec(
            select(models.Attachment)
            .where(models.Attachment.conversation_id == conversation_id)
            .where(models.Attachment.filename == draft.filename)
            .where(models.Attachment.status == models.FileStatus.LATEST)
        ).first()
        
        if existing:
            # Archive the old version
            existing.status = models.FileStatus.ARCHIVED
            session.add(existing)
        
        # Create new attachment from draft
        attachment = models.Attachment(
            conversation_id=conversation_id,
            filename=draft.filename,
            filepath=draft.filepath,
            content=draft.content,
            file_type=draft.file_type,
            file_size=draft.file_size,
            status=models.FileStatus.LATEST
        )
        
        session.add(attachment)
        
        # Delete the draft
        session.delete(draft)
        
        # Commit changes
        session.commit()
        session.refresh(attachment)
        
        logger.info(f"✅ Promoted draft {draft_id} to attachment {attachment.id}")
        return attachment
        
    except Exception as e:
        logger.error(f"Error promoting draft to attachment: {e}")
        session.rollback()
        return None

# ==================== TASK MANAGEMENT ====================

class TaskManager:
    """Manages background tasks and scheduling"""
    
    def __init__(self):
        self.active_tasks = {}
        self.completed_tasks = {}
        self.failed_tasks = {}
    
    async def schedule_task(self, task: Task) -> str:
        """Schedule a task for processing"""
        task_id = task.id
        self.active_tasks[task_id] = task
        
        # Process in background
        asyncio.create_task(self._process_task_async(task_id))
        
        return task_id
    
    async def _process_task_async(self, task_id: str):
        """Process task asynchronously"""
        task = self.active_tasks.get(task_id)
        if not task:
            return
        
        try:
            with next(get_session()) as session:
                router = get_task_router()
                response = await router.process_task(task, session)
                
                # Move to completed
                self.completed_tasks[task_id] = {
                    "task": task,
                    "response": response,
                    "completed_at": datetime.utcnow()
                }
                del self.active_tasks[task_id]
                
        except Exception as e:
            # Move to failed
            self.failed_tasks[task_id] = {
                "task": task,
                "error": str(e),
                "failed_at": datetime.utcnow()
            }
            del self.active_tasks[task_id]
    
    def get_task_status(self, task_id: str) -> Dict:
        """Get status of a task"""
        if task_id in self.active_tasks:
            return {
                "status": "active",
                "task": self.active_tasks[task_id]
            }
        elif task_id in self.completed_tasks:
            return {
                "status": "completed",
                "task": self.completed_tasks[task_id]["task"],
                "response": self.completed_tasks[task_id]["response"]
            }
        elif task_id in self.failed_tasks:
            return {
                "status": "failed",
                "task": self.failed_tasks[task_id]["task"],
                "error": self.failed_tasks[task_id]["error"]
            }
        else:
            return {"status": "not_found"}

# Global task manager
task_manager = TaskManager()

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

# Initialize logger
logger.info("AI Chain System initialized successfully")
