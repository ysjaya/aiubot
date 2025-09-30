from fastapi import FastAPI, WebSocket, Depends, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel
from dotenv import load_dotenv
import json
import logging

from app.api.routers import router as api_router
from app.db.database import engine, get_session
from app.services import cerebras_chain

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI(
    title="AI Coding Assistant",
    version="3.0.0",
    description="Production-ready AI assistant with file versioning"
)

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

# API routes
app.include_router(api_router, prefix="/api")

@app.on_event("startup")
def on_startup():
    logger.info("🚀 Starting AI Assistant...")
    SQLModel.metadata.create_all(engine)
    logger.info("✅ Database ready")

@app.get("/")
async def read_index():
    return FileResponse('app/templates/index.html')

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "3.0.0"}

@app.websocket("/ws/ai")
async def ws_ai(
    ws: WebSocket, 
    project_id: int = Query(...), 
    conversation_id: int = Query(...)
):
    await ws.accept()
    logger.info(f"📡 WebSocket: project={project_id}, conv={conversation_id}")
    
    try:
        data = await ws.receive_json()
        
        if not data.get("msg"):
            await ws.send_text(json.dumps({"status": "error", "message": "Empty message"}))
            return
        
        messages = [{"role": "user", "content": data["msg"]}]
        
        with next(get_session()) as session:
            async for chunk in cerebras_chain.ai_chain_stream(messages, project_id, conversation_id, session):
                await ws.send_text(chunk)
            
    except Exception as e:
        logger.error(f"❌ WebSocket error: {e}", exc_info=True)
        try:
            await ws.send_text(json.dumps({"status": "error", "message": str(e)}))
        except:
            pass
    finally:
        logger.info("🔌 WebSocket closed")
