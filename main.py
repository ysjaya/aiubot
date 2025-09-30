from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.db.database import init_db # <-- UBAH INI
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
    logger.info("🚀 Starting AI Code Assistant...")
    try:
        init_db() # <-- UBAH INI
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        raise
    
    yield
    
    logger.info("👋 Shutting down AI Code Assistant...")

# Create FastAPI app
app = FastAPI(
    title="AI Code Assistant",
    description="Claude-style AI coding assistant with file management and versioning",
    version="2.0.0",
    lifespan=lifespan
)

# CORS configuration
import os
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
try:
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    logger.info("✅ Static files mounted")
except Exception as e:
    logger.warning(f"⚠️ Could not mount static files: {e}")

# Mount frontend build for production (if exists)
import os
if os.path.exists("frontend/dist"):
    try:
        app.mount("/assets", StaticFiles(directory="frontend/dist/assets"), name="assets")
        logger.info("✅ Frontend assets mounted")
    except Exception as e:
        logger.warning(f"⚠️ Could not mount frontend assets: {e}")

# Templates
try:
    templates = Jinja2Templates(directory="app/templates")
    logger.info("✅ Templates loaded")
except Exception as e:
    logger.warning(f"⚠️ Could not load templates: {e}")
    templates = None

# Include routers
app.include_router(routers.router, prefix="/api", tags=["API"])
app.include_router(chat.router, prefix="/api", tags=["Chat"])

# Import GitHub routes if needed
try:
    from app.api import github_routes, auth
    app.include_router(github_routes.router, prefix="/api/github", tags=["GitHub"])
    app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
    logger.info("✅ GitHub integration enabled")
except ImportError as e:
    logger.warning(f"⚠️ GitHub integration not available: {e}")

# Import Draft routes
try:
    from app.api import draft_routes
    app.include_router(draft_routes.router, prefix="/api", tags=["Drafts"])
    logger.info("✅ Draft management enabled")
except ImportError as e:
    logger.warning(f"⚠️ Draft management not available: {e}")

@app.get("/")
async def root(request: Request):
    """Root endpoint - serve frontend or return info"""
    import os
    from fastapi.responses import FileResponse
    
    # In production, serve React build
    if os.path.exists("frontend/dist/index.html"):
        try:
            return FileResponse("frontend/dist/index.html")
        except Exception as e:
            logger.error(f"Frontend error: {e}")
    
    # Fallback to template
    if templates:
        try:
            return templates.TemplateResponse("index.html", {"request": request})
        except Exception as e:
            logger.error(f"Template error: {e}")
    
    return {
        "message": "AI Code Assistant API",
        "version": "2.0.0",
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "version": "2.0.0"}

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
    import os
    
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
