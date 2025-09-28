import os
from dotenv import load_dotenv
load_dotenv()

# Impor FileResponse untuk menyajikan file
from fastapi import FastAPI, WebSocket, Depends, Query
from fastapi.responses import FileResponse 
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session
from db import get_session, init_db
from cerebras_chain import ai_chain_stream
from github_import import list_files, get_file_content
from web_tools import search_web, scrape_url
from api import router as api_router

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(api_router)

# === TAMBAHKAN DUA ENDPOINT DI BAWAH INI ===

# 1. Endpoint untuk menyajikan index.html di path root ("/")
@app.get("/")
async def read_index():
    return FileResponse('index.html')

# 2. Endpoint untuk menyajikan style.css
@app.get("/style.css")
async def read_css():
    return FileResponse('style.css')
    
# ============================================

@app.on_event("startup")
def on_startup():
    init_db()

@app.websocket("/ws/ai")
async def ws_ai(ws: WebSocket, project_id: int = Query(...), conversation_id: int = Query(...)):
    await ws.accept()
    data = await ws.receive_json()
    messages = [
        {"role": "user", "content": data["msg"]}
    ]
    with next(get_session()) as session:
        async for chunk in ai_chain_stream(messages, project_id, conversation_id, session):
            await ws.send_text(chunk)

@app.get("/github/files")
def github_files(repo: str):
    return list_files(repo)

@app.get("/github/file")
def github_file(repo: str, file: str):
    return get_file_content(repo, file)

@app.get("/websearch")
def websearch(q: str):
    return search_web(q)

@app.get("/scrape")
def scrape(url: str):
    return scrape_url(url)
