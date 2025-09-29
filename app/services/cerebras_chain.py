import os
from cerebras_cloud_sdk import Cerebras # Pastikan nama import ini benar sesuai library Anda
from sqlmodel import Session, select
from app.db import models # Menggunakan path import yang benar

# Menggunakan settings dari config.py
from app.core.config import settings

client = Cerebras(api_key=settings.CEREBRAS_API_KEY)

def stream_cerebras(messages, model, **kwargs):
    return client.chat.completions.create(
        messages=messages, model=model, stream=True, **kwargs
    )

async def ai_chain_stream(messages, project_id, conv_id, session: Session):
    # Context = semua file terbaru project
    files = session.exec(select(models.File).where(models.File.project_id == project_id)).all()
    project_context = "\n".join([f"[{f.path}]:\n{f.content}" for f in files]) if files else ""
    
    # Chat history (tanpa batas 10)
    chats = session.exec(select(models.Chat).where(models.Chat.conversation_id == conv_id)).all()
    # PERUBAHAN: Menghapus slice '[-10:]' untuk memuat seluruh riwayat
    history = "\n".join([f"User: {c.message}\nAI: {c.ai_response}" for c in chats]) if chats else ""
    
    # Instruksi sistem untuk AI agar menggunakan Markdown untuk kode
    system_prompt = (
        "You are an expert programmer and AI assistant. "
        "Always format code snippets using Markdown code fences (```language\ncode\n```). "
        "Use the following project files and chat history as context.\n\n"
        f"--- PROJECT FILES ---\n{project_context}\n\n"
        f"--- CHAT HISTORY ---\n{history}"
    )
    
    messages = [{"role": "system", "content": system_prompt}] + messages

    # ... (Sisa dari logika chain Anda, akan kita ubah drastis di Tahap 3)
    # Untuk sekarang, kita biarkan seperti ini
    final_input = messages
    response_stream = stream_cerebras(final_input, "gpt-oss-120b", max_completion_tokens=65536, temperature=0.7)
    
    full_response = ""
    for chunk in response_stream:
        if chunk.choices[0].delta.content:
            content = chunk.choices[0].delta.content
            full_response += content
            yield content
            
    # Simpan chat ke database setelah selesai streaming
    if messages and full_response:
        user_message = messages[-1]['content']
        db_chat = models.Chat(
            conversation_id=conv_id,
            user="user", 
            message=user_message,
            ai_response=full_response
        )
        session.add(db_chat)
        session.commit()
