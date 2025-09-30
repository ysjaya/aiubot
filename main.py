from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.db.database import init_main_database
from app.api import routers, chat

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for startup and shutdown"""
    # Startup
    logger.info("🚀 Starting AI Code Assistant...")
    try:
        init_main_database()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("👋 Shutting down AI Code Assistant...")

# Create FastAPI app
app = FastAPI(
    title="AI Code Assistant",
    description="Claude-style AI coding assistant with file management and versioning",
    version="2.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(routers.router, prefix="/api", tags=["API"])
app.include_router(chat.router, prefix="/api", tags=["Chat"])

# Import GitHub routes if needed
try:
    from app.api import github_routes
    app.include_router(github_routes.router, prefix="/api", tags=["GitHub"])
    logger.info("✅ GitHub integration enabled")
except ImportError:
    logger.warning("⚠️ GitHub integration not available")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "AI Code Assistant API",
        "version": "2.0.0",
        "features": [
            "Project isolation with separate databases",
            "File versioning (Original → Modified → Latest)",
            "Intelligent file analysis and updates",
            "Claude-style attachment system",
            "Download and delete files",
            "Web search integration",
            "Streaming AI responses"
        ],
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
)
