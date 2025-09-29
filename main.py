from fastapi import FastAPI, WebSocket, Depends, Query, APIRouter
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import SQLModel
from dotenv import load_dotenv

from app.api.routers import router as api_router
from app.db.database import engine, get_session
from app.services import cerebras_chain, github_import, web_tools

load_dotenv()

app = FastAPI(title="Personal AI Assistant")

# Mount static files (CSS, JS)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# --- API Router untuk Tools ---
# Pindahkan semua endpoint tools ke sini agar konsisten di bawah /api
tools_router = APIRouter()

@tools_router.get("/github/files")
def github_files(repo: str):
    return github_import.list_files(repo)

@tools_router.get("/github/file")
def github_file(repo: str, file: str):
    return github_import.get_file_content(repo, file)

@tools_router.get("/websearch")
def websearch(q: str):
    return web_tools.search_web(q)

@tools_router.get("/scrape")
def scrape(url: str):
    return web_tools.scrape_url(url)

# Gabungkan semua router di bawah prefix /api
app.include_router(api_router, prefix="/api")
app.include_router(tools_router, prefix="/api")


@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)

# Endpoint untuk menyajikan Frontend (index.html)
@app.get("/")
async def read_index():
    return FileResponse('app/templates/index.html')


@app.websocket("/ws/ai")
async def ws_ai(ws: WebSocket, project_id: int = Query(...), conversation_id: int = Query(...)):
    await ws.accept()
    data = await ws.receive_json()
    messages = [{"role": "user", "content": data["msg"]}]
    
    with next(get_session()) as session:
        async for chunk in cerebras_chain.ai_chain_stream(messages, project_id, conversation_id, session):
            await ws.send_text(chunk)
