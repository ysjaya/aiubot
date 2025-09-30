from fastapi import FastAPI, WebSocket, Depends, Query, APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel
from dotenv import load_dotenv
import json
import logging

from app.api.routers import router as api_router
from app.api.auth import router as auth_router 
from app.db.database import engine, get_session
from app.services import cerebras_chain, web_tools

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI(
    title="Personal AI Assistant",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Sesuaikan dengan domain production Anda
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files dengan cache control
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Tools router
tools_router = APIRouter()

@tools_router.get("/websearch")
def websearch(q: str):
    """Web search endpoint"""
    try:
        return web_tools.search_web(q)
    except Exception as e:
        logger.error(f"Web search error: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

@tools_router.get("/scrape")
def scrape(url: str):
    """URL scraping endpoint"""
    try:
        return web_tools.scrape_url(url)
    except Exception as e:
        logger.error(f"Scraping error: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

# Include routers
app.include_router(api_router, prefix="/api", tags=["API"])
app.include_router(tools_router, prefix="/api/tools", tags=["Tools"]) 
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])

@app.on_event("startup")
async def on_startup():
    """Initialize application on startup"""
    logger.info("🚀 Application starting...")
    logger.info("📊 Creating database metadata...")
    try:
        SQLModel.metadata.create_all(engine)
        logger.info("✅ Database metadata created successfully")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise
    logger.info("✅ Startup completed")

@app.on_event("shutdown")
async def on_shutdown():
    """Cleanup on shutdown"""
    logger.info("👋 Application shutting down...")

@app.get("/")
async def read_index(request: Request):
    """Serve main page with no-cache headers"""
    response = FileResponse('app/templates/index.html')
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "2.0.0"
    }

@app.websocket("/ws/ai")
async def ws_ai(
    ws: WebSocket, 
    project_id: int = Query(...), 
    conversation_id: int = Query(...)
):
    """WebSocket endpoint for AI chat"""
    await ws.accept()
    logger.info(f"🔌 WebSocket connected: project={project_id}, conversation={conversation_id}")
    
    try:
        data = await ws.receive_json()
        logger.info(f"📨 Received: {data.get('msg', '')[:50]}...")
        
        if not data.get("msg"):
            await ws.send_text(json.dumps({
                "status": "error", 
                "message": "Empty message received"
            }))
            return
        
        messages = [{"role": "user", "content": data["msg"]}]
        
        with next(get_session()) as session:
            logger.info("🤖 Starting AI chain stream...")
            async for chunk in cerebras_chain.ai_chain_stream(
                messages, 
                project_id, 
                conversation_id, 
                session
            ):
                await ws.send_text(chunk)
            logger.info("✅ AI chain stream completed")
            
    except Exception as e:
        logger.error(f"❌ WebSocket error: {e}", exc_info=True)
        error_message = {
            "status": "error", 
            "message": f"Server error: {str(e)}"
        }
        try:
            await ws.send_text(json.dumps(error_message))
        except:
            pass
    finally:
        logger.info("🔌 WebSocket connection closed")
        await ws.close()

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Custom 404 handler"""
    return JSONResponse(
        status_code=404,
        content={"error": "Resource not found"}
    )

@app.exception_handler(500)
async def server_error_handler(request: Request, exc):
    """Custom 500 handler"""
    logger.error(f"Internal server error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
)
