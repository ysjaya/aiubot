import os
import asyncio
from typing import Dict, List, Union

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ChatAction
from cerebras.cloud.sdk import Cerebras

# --- 1. Konfigurasi dan Konstanta ---
CEREBRAS_API_KEY = os.environ.get("CEREBRAS_API_KEY")
SESSION_STRINGS_ENV = os.environ.get("SESSION_STRINGS")

if not CEREBRAS_API_KEY or not SESSION_STRINGS_ENV:
    raise ValueError("Pastikan CEREBRAS_API_KEY dan SESSION_STRINGS sudah diatur di environment variables!")

SESSION_STRINGS = [s.strip() for s in SESSION_STRINGS_ENV.split(',') if s.strip()]
if not SESSION_STRINGS:
    raise ValueError("SESSION_STRINGS tidak boleh kosong!")

# Tambahkan ID yang tidak akan pernah dibalas otomatis
DEVELOPER_ID = {7075124863}

cerebras_client = Cerebras(api_key=CEREBRAS_API_KEY)

# --- 2. State Management ---
auto_reply_states: Dict[int, bool] = {}

# --- 3. Utilitas Pemecah Pesan (Sama seperti sebelumnya) ---
TELEGRAM_CHAR_LIMIT = 4096
def split_text(text: str) -> List[str]:
    if len(text) <= TELEGRAM_CHAR_LIMIT: return [text]
    chunks = []
    while len(text) > 0:
        if len(text) <= TELEGRAM_CHAR_LIMIT:
            chunks.append(text)
            break
        chunk = text[:TELEGRAM_CHAR_LIMIT]
        split_pos = chunk.rfind('\n') if '\n' in chunk else chunk.rfind(' ')
        if split_pos == -1: split_pos = TELEGRAM_CHAR_LIMIT
        chunks.append(text[:split_pos])
        text = text[split_pos:].lstrip()
    return chunks

# --- 4. Logika Konteks Percakapan (Fitur Baru) ---
async def get_conversation_context(client: Client, message: Message, history_limit: int = 6) -> List[Dict[str, str]]:
    """
    Mengambil riwayat chat, memformatnya menjadi konteks untuk AI.
    Membaca hingga `history_limit` pesan terakhir.
    """
    chat_history = []
    # Mengambil beberapa pesan terakhir dari riwayat chat
    async for msg in client.get_chat_history(message.chat.id, limit=history_limit):
        # Hanya proses pesan teks
        if msg.text:
            role = "assistant" if msg.from_user.is_self else "user"
            chat_history.append({"role": role, "content": msg.text})

    # Riwayat pesan datang dalam urutan terbalik (terbaru dulu), jadi kita balikkan
    # agar urutannya kronologis (terlama dulu)
    chat_history.reverse()
    return chat_history


# --- 5. Fungsi Logika AI (Diperbarui untuk Menerima Konteks) ---
async def get_ai_response(context: List[Dict[str, str]]) -> str:
    """Menghubungi Cerebras AI dengan konteks percakapan."""
    # Pastikan ada konteks sebelum mengirim
    if not context:
        return ""
    try:
        stream = cerebras_client.chat.completions.create(
            # ===== Mengirim seluruh konteks percakapan =====
            messages=context,
            # ===============================================
            model="qwen-3-235b-a22b-thinking-2507",
            stream=True,
            max_completion_tokens=1000,
            temperature=0.7,
            top_p=0.8
        )
        response_content = "".join(chunk.choices[0].delta.content or "" for chunk in stream)
        return response_content or "Maaf, saya tidak bisa merespons saat ini."
    except Exception as e:
        print(f"Error saat menghubungi Cerebras API: {e}")
        return "Terjadi kesalahan pada sistem AI."

# --- 6. Fungsi untuk Mendaftarkan Handlers ---
def register_handlers(client: Client):
    """Mendaftarkan semua event handler ke sebuah instance client."""

    @client.on_message(filters.command("ping", prefixes="/") & filters.me)
    async def ping_command(_, message: Message):
        await message.edit_text("Pong!")

    @client.on_message(filters.command("start", prefixes="/") & filters.me)
    async def start_command(c: Client, message: Message):
        auto_reply_states[c.me.id] = True
        await message.edit_text(f"✅ **Balas otomatis untuk `{c.me.first_name}` diaktifkan.**")

    @client.on_message(filters.command("stop", prefixes="/") & filters.me)
    async def stop_command(c: Client, message: Message):
        auto_reply_states[c.me.id] = False
        await message.edit_text(f"🛑 **Balas otomatis untuk `{c.me.first_name}` dinonaktifkan.**")

    # Handler untuk DM (Private Message)
    @client.on_message(filters.private & ~filters.me & ~filters.user(list(DEVELOPER_ID)))
    async def private_reply_handler(c: Client, message: Message):
        if not auto_reply_states.get(c.me.id, True) or not message.text: return
        try:
            async with c.send_chat_action(message.chat.id, action=ChatAction.TYPING):
                context = await get_conversation_context(c, message)
                ai_reply = await get_ai_response(context)
                if not ai_reply: return
                message_chunks = split_text(ai_reply)
                await message.reply_text(message_chunks[0])
                if len(message_chunks) > 1:
                    for chunk in message_chunks[1:]: await c.send_message(message.chat.id, chunk)
        except Exception as e: print(f"Gagal membalas di DM: {e}")

    # Handler untuk Grup
    # Trigger: (disebut/mention ATAU membalas pesan kita) DAN bukan dari kita sendiri
    is_mentioned_or_reply = (filters.mentioned | filters.reply)
    @client.on_message(filters.group & is_mentioned_or_reply & ~filters.me)
    async def group_reply_handler(c: Client, message: Message):
        # Pastikan mention atau reply ditujukan ke akun kita, bukan ke orang lain
        if isinstance(message.reply_to_message, Message) and not message.reply_to_message.from_user.is_self:
             return # Jika reply tapi bukan ke pesan kita, abaikan
        
        if not auto_reply_states.get(c.me.id, True) or not message.text: return
        try:
            async with c.send_chat_action(message.chat.id, action=ChatAction.TYPING):
                context = await get_conversation_context(c, message)
                ai_reply = await get_ai_response(context)
                if not ai_reply: return
                message_chunks = split_text(ai_reply)
                # Di grup, selalu balas ke pesan yang mentrigger agar tidak spam
                await message.reply_text(message_chunks[0])
                if len(message_chunks) > 1:
                    for chunk in message_chunks[1:]: await message.reply_text(chunk)
        except Exception as e: print(f"Gagal membalas di grup: {e}")


# --- 7. Logika Utama untuk Menjalankan Semua Klien ---
async def main():
    clients = []
    for i, session_string in enumerate(SESSION_STRINGS):
        client = Client(name=f"user_{i}", session_string=session_string)
        register_handlers(client)
        clients.append(client)
    
    await asyncio.gather(*(client.start() for client in clients))
    
    for client in clients:
        if client.is_connected:
            me = client.me
            if me.id not in auto_reply_states: auto_reply_states[me.id] = True
            print(f"✅ Klien untuk {me.first_name} (@{me.username}) berhasil terhubung.")

    print("\nSemua userbot aktif dan siap menerima perintah.")
    await asyncio.Event().wait()

if __name__ == "__main__":
    print("🚀 Memulai Bot Multi-User Cerdas...")
    asyncio.run(main())
