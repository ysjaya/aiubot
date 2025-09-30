# AI Code Assistant

## Overview

This is a full-stack AI coding assistant application built with FastAPI and React. It provides a Claude-style chat interface for AI-powered code assistance with file management, versioning, and GitHub integration. The system uses Cerebras and NVIDIA AI models for code generation and understanding, with SQLModel/PostgreSQL for data persistence.

## User Preferences

Preferred communication style: Simple, everyday language.

## Recent Changes (September 30, 2025)

### Draft/Versioning System & Code Completeness Validation (Latest - September 30, 2025)
- **Complete Code Generation Enforcement**: AI now generates 100% complete code without truncation
  - Added 10-rule system in AI prompts to prevent code truncation (no "...", no placeholders, no stubs)
  - Increased token limits: 16384 per chunk with unlimited mode supporting auto-continuation up to 100K tokens
  - Code completeness validator analyzes generated code for common truncation patterns
  
- **Draft/Staging System**: AI-modified files go through draft workflow before committing to GitHub
  - `DraftVersion` table captures every AI-generated file revision with metadata
  - Automatic completeness validation runs on every draft creation
  - Drafts with completeness_score >= 0.95 auto-promote to Attachment with LATEST status
  - Incomplete drafts stay in PENDING status for manual review and approval
  - Database migration 007 adds draft_versions table with proper indexes

- **Enhanced GitHub Commit Workflow**:
  - Only files with LATEST status can be committed to GitHub (prevents corrupted commits)
  - Improved token fallback: provided_token → env GITHUB_TOKEN → settings.GITHUB_TOKEN
  - Pre-commit validation ensures no empty or truncated files reach GitHub
  - Clear error messages when no LATEST files available for commit
  - Comprehensive logging shows file count, char count, and commit status

- **New API Endpoints for Draft Management**:
  - `GET /api/drafts` - List all drafts for a conversation (with completeness scores)
  - `GET /api/draft/{id}` - Get full content of specific draft (100% complete code)
  - `POST /api/draft/{id}/approve` - Manually approve incomplete draft
  - `POST /api/draft/{id}/reject` - Reject draft
  - `POST /api/draft/{id}/promote` - Promote approved draft to LATEST Attachment
  - `GET /api/drafts/pending` - List pending drafts awaiting review

- **Code Validator Features**:
  - Detects incomplete functions (missing implementations, TODO comments)
  - Identifies truncation markers ("...", "rest of code", etc.)
  - Checks for proper file structure (imports, classes, functions)
  - Validates minimum code length and complexity
  - Returns completeness_score (0-1) with detailed issue list

- **AI Chain Improvements**:
  - `intelligent_file_update()` function uses draft system with validation
  - Auto-detection of code blocks that should update files
  - Streaming with unlimited mode supports multi-continuation for long files
  - Full response saved to Chat table with context tracking
  - Modified files tracked in files_modified JSON field

### Fresh GitHub Clone - Replit Environment Setup (September 30, 2025)
- **GitHub Import Complete**: Fresh clone from GitHub successfully configured for Replit environment
  - Python 3.11 and Node.js 20 toolchains installed
  - All Python dependencies installed from requirements.txt (FastAPI, SQLModel, Cerebras SDK, etc.)
  - All npm dependencies installed in frontend (React, Vite, React Markdown, etc.)
  - PostgreSQL database created and initialized with Replit's built-in database
  - Database tables auto-created on startup with proper schema

- **Development Workflow Setup**:
  - "Dev Server" workflow configured and running successfully
  - Backend: uvicorn on localhost:8000 with auto-reload
  - Frontend: Vite dev server on 0.0.0.0:5000 (proxy-enabled for Replit)
  - Vite properly configured with allowedHosts: true for Replit iframe proxy
  - API and WebSocket proxy configured for seamless backend communication
  
- **Deployment Configuration**:
  - Autoscale deployment target configured
  - Build step: npm install && npm run build in frontend directory
  - Run step: uvicorn serving FastAPI with built React frontend
  - Production serves from frontend/dist with fallback to templates
  
- **Verified Working**:
  - Frontend loads correctly with AI Code Assistant interface
  - Backend health endpoint responding (version 2.0.0)
  - Database initialization successful with all tables created
  - GitHub integration module loaded
  - All three main features visible: Project Management, AI Chat, File Versioning

### GitHub Re-Import and Model Update (Previous - September 30, 2025)
- **GitHub Import Complete**: Fresh clone from GitHub successfully configured for Replit
  - Python 3.11 and Node.js 20 toolchains verified and running
  - All Python and npm dependencies installed successfully
  - PostgreSQL database connected via existing Supabase configuration
  - Frontend built for production and tested

- **AI Model Update**: Updated Cerebras AI models
  - Changed from "llama3.1-70b" to "qwen-3-235b-a22b-instruct-2507"
  - Updated both streaming and non-streaming API calls
  - Model configured for 4096 max tokens with 0.7 temperature

- **Deployment Configuration Fix (Port 8080)**: 
  - Fixed UI inconsistency between Replit and Kinsta deployments
  - **Root cause**: frontend/dist not built in Kinsta (missing build step in Dockerfile)
  - **Solution**: Updated Dockerfile to build frontend during Docker build stage
  - Production server now uses port 8080 as default (configurable via PORT env)
  - Server binds to 0.0.0.0:8080 for both development and production
  - Dockerfile installs Node.js 20, builds React frontend, and copies dist to production image

- **Development Workflow**:
  - "Dev Server" workflow configured and running successfully
  - Backend on localhost:8000, frontend on 0.0.0.0:5000
  - Vite proxy properly configured for API and WebSocket connections
  - All features tested and verified working: UI loads, database connects, services initialize

### Replit Environment Setup (Previous - September 30, 2025)
- **Development Configuration**: Successfully configured for Replit environment
  - Python 3.11 and Node.js 20 toolchains installed
  - PostgreSQL database created and initialized
  - All dependencies installed (Python and npm packages)
  - Frontend configured on port 5000 with proper host settings (0.0.0.0, allowedHosts: true)
  - Backend running on localhost:8000
  - Fixed case-sensitive import issue (App.jsx → app.jsx)
  - Fixed API connection issue: Changed API_URL from localhost to relative path for Replit proxy compatibility

- **Workflow Setup**: 
  - Single "Dev Server" workflow running both backend and frontend
  - Backend starts first on port 8000
  - Frontend starts on port 5000 and proxies API calls to backend
  - Automatic database migration on startup
  - All features tested and working: Project management, AI chat, file versioning

- **Deployment Configuration**:
  - Autoscale deployment target configured
  - Build step: Installs and builds frontend
  - Run step: Serves production app with FastAPI + built React frontend
  - Production serves from frontend/dist with fallback to vanilla templates

- **Bug Fixes Applied**:
  - Fixed frontend API connection by using relative URLs instead of absolute localhost URLs
  - Configured Vite proxy to work correctly with Replit environment
  - Updated .env file to use empty API_URL for same-origin requests
  - Backend properly serves both development and production frontend builds

### GitHub Integration & UI Improvements
- **GitHub Import**: Replaced file upload functionality with GitHub repository import
  - Integrated Replit GitHub connector for secure OAuth (with fallback to traditional auth)
  - Added modal UI for repository selection and file browsing
  - Supports importing multiple files from any repository branch
  
- **Auto-Create Workflow**: Implemented automatic project and conversation creation
  - Users can start chatting immediately without manual setup
  - Auto-creates "New Project" and "Chat" when user sends first message without selection
  - Streamlined onboarding experience for new users

- **Mobile-First Design**: Enhanced mobile responsiveness
  - Flexible scrolling on all pages with proper viewport handling
  - Touch-friendly controls and improved modal interactions
  - Import button replaces upload functionality in UI

- **Production Readiness**: 
  - Port configuration: Development uses port 5000 (Replit), production defaults to port 8080 (Kinsta)
  - SECRET_KEY security: Auto-generates in Replit, requires explicit key in production
  - CORS configuration: Environment-controlled via ALLOWED_ORIGINS (defaults to "*" for dev)
  - Dockerfile configured for Kinsta deployment on port 8080

## System Architecture

### Frontend Architecture

**Technology Stack:**
- React 18 with Vite for fast development and optimized production builds
- Vanilla JavaScript for UI state management (no heavy frameworks)
- Server-Sent Events (SSE) and WebSockets for real-time AI streaming responses
- Mobile-first responsive design with PWA capabilities

**Key Design Decisions:**
- **Component-free architecture**: Uses vanilla JavaScript modules instead of React components for simpler state management and better mobile performance
- **Real-time streaming**: Implements both HTTP SSE and WebSocket protocols for streaming AI responses, allowing fallback options
- **PWA support**: Service worker and manifest for offline-capable mobile app experience
- **Mobile optimization**: Custom CSS with safe area insets, touch-friendly controls, and dynamic viewport handling

### Backend Architecture

**Framework & Patterns:**
- FastAPI with async/await for high-performance API endpoints
- SQLModel ORM for type-safe database operations (built on SQLAlchemy)
- Alembic for database migrations
- Modular service layer separating business logic from API routes

**Core Components:**
1. **API Layer** (`app/api/`): REST endpoints for projects, conversations, files, and GitHub integration
2. **Service Layer** (`app/services/`): Business logic for AI chain processing, GitHub import, and web tools
3. **Database Layer** (`app/db/`): SQLModel models and database session management
4. **Core Config** (`app/core/`): Centralized settings using Pydantic for environment variable management

**Key Design Decisions:**
- **Single database architecture**: Originally designed for isolated per-project databases, migrated to single database for simplicity (migration artifacts remain in codebase)
- **Streaming AI responses**: Uses async generators to stream AI completions chunk-by-chunk for better UX
- **Cascade deletions**: Foreign keys configured with CASCADE DELETE to maintain referential integrity
- **Lifecycle management**: FastAPI lifespan events for proper database initialization and cleanup

### Data Models

**Core Entities:**
1. **Project**: Top-level container for organizing work
2. **Conversation**: Chat threads within a project
3. **Chat**: Individual messages with user input and AI responses
4. **Attachment**: Files imported from GitHub or uploaded, linked to conversations

**Relationships:**
- One-to-many: Project → Conversations → Chats
- One-to-many: Conversation → Attachments
- All relationships use SQLAlchemy cascade deletes for data consistency

**Database Schema Evolution:**
- Migration system tracks schema changes (database_name column removed, chat context tracking added, attachment import metadata added)
- Columns for file context tracking (`context_file_ids`, `files_modified`) enable AI to reference specific files

### Authentication & Authorization

**GitHub OAuth Integration:**
- Primary: Replit connector for seamless GitHub integration in Replit environment
- Fallback: Traditional OAuth flow with JWT tokens for standalone deployments
- Token caching with expiry checking to minimize API calls

**Security Considerations:**
- Auto-generated SECRET_KEY for development (Replit), required explicit key for production
- CORS middleware with configurable allowed origins
- GitHub token stored in localStorage (client-side) or environment variables (server-side)

## External Dependencies

### AI/LLM Services
- **Cerebras Cloud SDK**: Primary AI model for code generation and chat responses
- **NVIDIA AI (via OpenAI SDK)**: Alternative AI provider using OpenAI-compatible API
- Models configured via environment variables (`CEREBRAS_API_KEY`, `NVIDIA_API_KEY`)

### Database
- **PostgreSQL**: Primary data store via SQLModel/SQLAlchemy
- Connection pooling configured (pool_size=5, max_overflow=10)
- Database URL configured via `DATABASE_URL` environment variable

### GitHub Integration
- **PyGithub**: GitHub API client for repository access and file import
- **OAuth2**: Authentication flow for GitHub user authorization
- **Replit Connector**: Simplified GitHub integration for Replit hosting environment

### Third-Party Services
- **DuckDuckGo**: Web search functionality (scraping-based, no API key required)
- **BeautifulSoup4**: HTML parsing for web scraping and content extraction

### Development Tools
- **Alembic**: Database migration management
- **Vite**: Frontend build tool and dev server with HMR
- **uvicorn**: ASGI server for FastAPI with auto-reload in development

### Frontend Libraries
- **React Markdown**: Markdown rendering for AI responses
- **React Syntax Highlighter**: Code syntax highlighting in chat
- **Highlight.js**: Additional syntax highlighting support

### Configuration Management
- **python-dotenv**: Environment variable loading from `.env` file
- **Pydantic Settings**: Type-safe configuration with validation
- All sensitive credentials managed through environment variables (never committed to repository)