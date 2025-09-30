# AI Code Assistant

## Overview

This is a full-stack AI coding assistant application built with FastAPI and React. It provides a Claude-style chat interface for AI-powered code assistance with file management, versioning, and GitHub integration. The system uses Cerebras and NVIDIA AI models for code generation and understanding, with SQLModel/PostgreSQL for data persistence.

## User Preferences

Preferred communication style: Simple, everyday language.

## Recent Changes (September 30, 2025)

### Replit Environment Setup (Latest - September 30, 2025)
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

## Recent Changes (September 30, 2025)

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