from fastapi import FastAPI, WebSocket, Depends, Query, APIRouter
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import SQLModel
from dotenv import load_dotenv
import json

from app.api.routers import router as api_router
from app.api.auth import router as auth_router 
from app.db.database import engine, get_session
from app.services import cerebras_chain, github_import, web_tools

load_dotenv()

app = FastAPI(title="Personal AI Assistant")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

tools_router = APIRouter()

@tools_router.get("/websearch")
def websearch(q: str):
    return web_tools.search_web(q)

@tools_router.get("/scrape")
def scrape(url: str):
    return web_tools.scrape_url(url)

app.include_router(api_router, prefix="/api")
app.include_router(tools_router, prefix="/api") 
app.include_router(auth_router, prefix="/api/auth")

@app.on_event("startup")
def on_startup():
    print("[MAIN LOG] Aplikasi mulai berjalan...")
    print("[MAIN LOG] Membuat metadata database...")
    SQLModel.metadata.create_all(engine)
    print("[MAIN LOG] Metadata database dibuat.")
    # cerebras_chain.load_embedding_model() # Dihapus karena tidak ada lagi embedding lokal
    print("[MAIN LOG] Event startup selesai.")

@app.get("/")
async def read_index():
    return FileResponse('app/templates/index.html')

@app.websocket("/ws/ai")
async def ws_ai(ws: WebSocket, project_id: int = Query(...), conversation_id: int = Query(...)):
    await ws.accept()
    print(f"\n[MAIN LOG] WebSocket connection accepted for project:{project_id}, conv:{conversation_id}")
    try:
        data = await ws.receive_json()
        print(f"[MAIN LOG] Received message from client: {data}")
        messages = [{"role": "user", "content": data["msg"]}]
        
        with next(get_session()) as session:
            print("[MAIN LOG] Starting AI chain stream...")
            async for chunk in cerebras_chain.ai_chain_stream(messages, project_id, conversation_id, session):
                await ws.send_text(chunk)
            print("[MAIN LOG] AI chain stream finished.")
    except Exception as e:
        print(f"[MAIN LOG] !!! ERROR in WebSocket endpoint: {e} !!!")
        await ws.send_text(json.dumps({"status": "error", "message": f"Server error: {e}"}))
    finally:
        print("[MAIN LOG] WebSocket connection closed.")
