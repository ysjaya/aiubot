# AI Code Assistant

## Overview

This project is a full-stack AI coding assistant built with FastAPI and React, providing a chat interface for AI-powered code assistance. It includes file management, versioning, and GitHub integration. The system leverages Cerebras and NVIDIA AI models for code generation and understanding, with SQLModel/PostgreSQL for data persistence. The project's vision is to streamline the development workflow by offering an intelligent assistant that handles code generation, manages file changes, and integrates seamlessly with version control systems, thereby boosting developer productivity and accelerating project delivery.

## Recent Changes

**Date: October 1, 2025**
- **Replit Environment Setup**: Configured project to run in Replit environment
  - Installed Python 3.11 and Node.js 20
  - Installed all Python dependencies from requirements.txt
  - Installed frontend dependencies (npm install)
  - Created PostgreSQL database for development
- **Database Schema Migration**: Fixed schema incompatibility between old and new code
  - Added migration functions in `app/db/database.py`:
    - `fix_conversation_table_columns()`: Removes `project_id` column, adds `updated_at` column
    - `fix_attachment_table_columns()`: Adds `file_path` column if missing
    - `fix_chat_table_columns()`: Adds `context_file_ids` and `files_modified` columns
    - `fix_draftversion_table_columns()`: Removes `project_id` column from draftversion table
  - Prevents multiple production errors:
    - "null value in column project_id violates not-null constraint" (conversation & draftversion)
    - "column conversation.updated_at does not exist"
    - "column file_path of relation attachment does not exist"
  - All migrations run automatically on app startup
- **Workflow Configuration**: Setup development workflow
  - Backend runs on localhost:8000
  - Frontend runs on 0.0.0.0:5000 with Vite dev server
  - Frontend proxies API requests to backend
  - Single workflow starts both backend and frontend
- **Deployment Configuration**: Setup autoscale deployment
  - Build step: `cd frontend && npm run build`
  - Run command: uvicorn serving FastAPI with built React frontend on port 5000
  - Deployment type: autoscale (stateless web application)

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture

**Technology Stack:**
- React 18 with Vite
- Vanilla JavaScript for UI state management
- Server-Sent Events (SSE) and WebSockets for real-time AI streaming responses
- Mobile-first responsive design with PWA capabilities

**Key Design Decisions:**
- **Component-free architecture**: Uses vanilla JavaScript modules for simpler state management and mobile performance.
- **Real-time streaming**: Implements both HTTP SSE and WebSocket protocols for streaming AI responses.
- **PWA support**: Service worker and manifest for offline-capable mobile app experience.
- **Mobile optimization**: Custom CSS with safe area insets, touch-friendly controls, and dynamic viewport handling.

### Backend Architecture

**Framework & Patterns:**
- FastAPI with async/await
- SQLModel ORM for type-safe database operations
- Alembic for database migrations
- Modular service layer separating business logic from API routes

**Core Components:**
1. **API Layer** (`app/api/`): REST endpoints for conversations, chats, files, and GitHub integration.
2. **Service Layer** (`app/services/`): Business logic for AI chain processing, GitHub import, web tools, and conversation auto-naming.
3. **Database Layer** (`app/db/`): SQLModel models and database session management.
4. **Core Config** (`app/core/`): Centralized settings using Pydantic.

**Key Design Decisions:**
- **Single database architecture**: Migrated from per-project databases to a single database for simplicity.
- **Streaming AI responses**: Uses async generators to stream AI completions chunk-by-chunk.
- **Cascade deletions**: Foreign keys configured with CASCADE DELETE for referential integrity.
- **Lifecycle management**: FastAPI lifespan events for database initialization and cleanup.

### Data Models

**Core Entities:**
1. **Conversation**: Main entity for organizing chats (standalone, no project hierarchy).
2. **Chat**: Individual messages with user input and AI responses.
3. **Attachment**: Files imported from GitHub or uploaded.
4. **DraftVersion**: Captures AI-generated file revisions with metadata and completeness scores.

**Relationships:**
- One-to-many: Conversation → Chats
- One-to-many: Conversation → Attachments
- One-to-many: Conversation → DraftVersions
- All relationships use SQLAlchemy cascade deletes.

### Authentication & Authorization

**GitHub OAuth Integration:**
- Primary: Replit connector for GitHub integration.
- Fallback: Traditional OAuth flow with JWT tokens.
- Token caching with expiry checking.

**Security Considerations:**
- Auto-generated `SECRET_KEY` for development, explicit key for production.
- CORS middleware with configurable allowed origins.
- GitHub token stored in localStorage (client-side) or environment variables (server-side).

### Feature Specifications

- **Complete Code Generation Enforcement**: AI generates 100% complete code, preventing truncation with a 10-rule system in AI prompts. Increased token limits (16384 per chunk, unlimited mode up to 100K tokens).
- **Draft/Staging System**: AI-modified files undergo a draft workflow before committing to GitHub, using `DraftVersion` table.
- **Automatic Completeness Validation**: Runs on every draft creation; drafts with `completeness_score >= 0.95` auto-promote to `Attachment` with `LATEST` status.
- **Enhanced GitHub Commit Workflow**: Only `LATEST` status files can be committed, with improved token fallback and pre-commit validation.
- **Code Validator**: Detects incomplete functions, truncation markers, checks file structure, and validates minimum code length.
- **GitHub Import**: Replaced file upload with GitHub repository import, supporting multiple files from any branch.
- **AI Auto-Naming**: Conversations are automatically named by AI based on the first message topic for better organization.
- **Conversation-Only Model**: Removed project hierarchy - conversations are now standalone entities with direct file and chat associations.
- **Deployment Configuration**: Autoscale deployment, build step for frontend, and `uvicorn` serving FastAPI with built React frontend on port 5000.

## External Dependencies

### AI/LLM Services
- **Cerebras Cloud SDK**: Primary AI model.
- **NVIDIA AI (via OpenAI SDK)**: Alternative AI provider.

### Database
- **PostgreSQL**: Primary data store via SQLModel/SQLAlchemy.

### GitHub Integration
- **PyGithub**: GitHub API client.
- **OAuth2**: Authentication for GitHub.
- **Replit Connector**: Simplified GitHub integration for Replit.

### Third-Party Services
- **DuckDuckGo**: Web search functionality (scraping-based).
- **BeautifulSoup4**: HTML parsing for web scraping.

### Frontend Libraries
- **React Markdown**: Markdown rendering.
- **React Syntax Highlighter**: Code syntax highlighting.
- **Highlight.js**: Additional syntax highlighting.