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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI(title="Personal AI Assistant", version="2.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Tools router
tools_router = APIRouter()

@tools_router.get("/websearch")
def websearch(q: str):
    try:
        return web_tools.search_web(q)
    except Exception as e:
        logger.error(f"Web search error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@tools_router.get("/scrape")
def scrape(url: str):
    try:
        return web_tools.scrape_url(url)
    except Exception as e:
        logger.error(f"Scraping error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

app.include_router(api_router, prefix="/api")
app.include_router(tools_router, prefix="/api/tools") 
app.include_router(auth_router, prefix="/api/auth")

@app.on_event("startup")
def on_startup():
    logger.info("Starting application...")
    SQLModel.metadata.create_all(engine)
    logger.info("Database ready")

@app.get("/")
async def read_index():
    response = FileResponse('app/templates/index.html')
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "2.0.0"}

@app.websocket("/ws/ai")
async def ws_ai(ws: WebSocket, project_id: int = Query(...), conversation_id: int = Query(...)):
    await ws.accept()
    logger.info(f"WebSocket connected: project={project_id}, conv={conversation_id}")
    
    try:
        data = await ws.receive_json()
        logger.info(f"Received: {data.get('msg', '')[:50]}...")
        
        if not data.get("msg"):
            await ws.send_text(json.dumps({"status": "error", "message": "Empty message"}))
            return
        
        messages = [{"role": "user", "content": data["msg"]}]
        
        with next(get_session()) as session:
            logger.info("Starting AI chain stream...")
            async for chunk in cerebras_chain.ai_chain_stream(messages, project_id, conversation_id, session):
                await ws.send_text(chunk)
            logger.info("AI chain completed")
            
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        try:
            await ws.send_text(json.dumps({"status": "error", "message": f"Server error: {str(e)}"}))
        except:
            pass
    finally:
        logger.info("WebSocket closed")
