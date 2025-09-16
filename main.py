import os
import asyncio
from typing import Dict, List, Union

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ChatAction
from cerebras.cloud.sdk import Cerebras

# --- 1. Konfigurasi dan Konstanta ---
CEREBRAS_API_KEY = os.environ.get("CEREBRAS_API_KEY")

if not CEREBRAS_API_KEY:
    raise ValueError("CEREBRAS_API_KEY environment variable tidak ditemukan!")

# Logika untuk membaca SESSION, SESSION2, SESSION3, dst.
SESSION_STRINGS = []
i = 1
while True:
    key = f"SESSION{i if i > 1 else ''}"
    session_str = os.environ.get(key)
    if session_str:
        SESSION_STRINGS.append(session_str)
        i += 1
    else:
        break

if not SESSION_STRINGS:
    raise ValueError("Tidak ada SESSION environment variable yang ditemukan! (Contoh: SESSION, SESSION2, ...)")

# Konstanta
DEVELOPER_ID = {7075124863}
TELEGRAM_CHAR_LIMIT = 4096

cerebras_client = Cerebras(api_key=CEREBRAS_API_KEY)

# --- 2. State Management ---
auto_reply_states: Dict[int, bool] = {}

# --- 3. Utilitas & Logika AI ---
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

async def get_conversation_context(client: Client, message: Message, history_limit: int = 6) -> List[Dict[str, str]]:
    chat_history = []
    async for msg in client.get_chat_history(message.chat.id, limit=history_limit):
        if msg.text:
            role = "assistant" if msg.from_user and msg.from_user.is_self else "user"
            chat_history.append({"role": role, "content": msg.text})
    chat_history.reverse()
    return chat_history

async def get_ai_response(context: List[Dict[str, str]]) -> str:
    if not context: return ""
    try:
        stream = cerebras_client.chat.completions.create(
            messages=context, model="qwen-3-235b-a22b-thinking-2507",
            stream=True, max_completion_tokens=1000, temperature=0.7, top_p=0.8
        )
        return "".join(chunk.choices[0].delta.content or "" for chunk in stream) or "Maaf, saya tidak bisa merespons saat ini."
    except Exception as e:
        print(f"Error saat menghubungi Cerebras API: {e}")
        return "Terjadi kesalahan pada sistem AI."

# --- 4. Logika Pemrosesan Pesan (Live dan Offline) ---
async def process_and_reply(client: Client, message: Message):
    """Fungsi inti yang menangani logika balasan untuk pesan live dan offline."""
    if not auto_reply_states.get(client.me.id, True) or not message.text: return
    try:
        async with client.send_chat_action(message.chat.id, action=ChatAction.TYPING):
            context = await get_conversation_context(client, message)
            ai_reply = await get_ai_response(context)
            if not ai_reply: return
            message_chunks = split_text(ai_reply)
            
            # Balas pesan pertama, kirim sisa sebagai pesan biasa
            first_chunk = message_chunks.pop(0)
            await message.reply_text(first_chunk)
            
            for chunk in message_chunks:
                await client.send_message(message.chat.id, chunk)
    except Exception as e:
        print(f"Gagal memproses balasan untuk pesan {message.id} di chat {message.chat.id}: {e}")

# --- 5. Fungsi untuk Memproses Pesan yang Terlewat (Saat Startup) ---
async def process_missed_messages(client: Client):
    """Memindai dan membalas pesan yang belum terbalas saat bot offline."""
    print(f"[{client.me.first_name}] Memeriksa pesan yang terlewat...")
    processed_chats = set()
    try:
        async for dialog in client.get_dialogs():
            # Hanya proses DM dan Grup, hindari duplikasi
            if dialog.chat.id in processed_chats or dialog.chat.type not in ["private", "supergroup", "group"]:
                continue
            
            last_message_from_us = None
            trigger_message_to_reply = None
            
            async for msg in client.get_chat_history(dialog.chat.id, limit=20):
                if msg.from_user and msg.from_user.is_self:
                    last_message_from_us = msg
                    break # Ditemukan pesan terakhir dari kita, berhenti memindai lebih jauh
                
                # Cek apakah pesan ini adalah trigger yang valid
                is_private_trigger = (dialog.chat.type == "private" and not msg.from_user.is_self and msg.from_user.id not in DEVELOPER_ID)
                is_group_trigger = (dialog.chat.type in ["supergroup", "group"] and (msg.mentioned or (msg.reply_to_message and msg.reply_to_message.from_user and msg.reply_to_message.from_user.is_self)))
                
                if is_private_trigger or is_group_trigger:
                    trigger_message_to_reply = msg # Simpan sebagai kandidat untuk dibalas

            # Jika ada kandidat pesan dan tidak ada balasan dari kita setelahnya, balas!
            if trigger_message_to_reply and (last_message_from_us is None or last_message_from_us.id < trigger_message_to_reply.id):
                print(f"[{client.me.first_name}] Menemukan pesan belum terbalas di '{dialog.chat.title or dialog.chat.first_name}'. Membalas...")
                await process_and_reply(client, trigger_message_to_reply)
                await asyncio.sleep(5) # Jeda untuk menghindari rate limit

            processed_chats.add(dialog.chat.id)
    except Exception as e:
        print(f"[{client.me.first_name}] Error saat memproses pesan offline: {e}")
    print(f"[{client.me.first_name}] Selesai memeriksa pesan yang terlewat.")

# --- 6. Fungsi untuk Mendaftarkan Handlers Pesan Live ---
def register_handlers(client: Client):
    @client.on_message(filters.command("ping", prefixes="/") & filters.me)
    async def ping(_, message: Message): await message.edit_text("Pong!")
    @client.on_message(filters.command("start", prefixes="/") & filters.me)
    async def start(c: Client, message: Message):
        auto_reply_states[c.me.id] = True
        await message.edit_text(f"✅ **Balas otomatis untuk `{c.me.first_name}` diaktifkan.**")
    @client.on_message(filters.command("stop", prefixes="/") & filters.me)
    async def stop(c: Client, message: Message):
        auto_reply_states[c.me.id] = False
        await message.edit_text(f"🛑 **Balas otomatis untuk `{c.me.first_name}` dinonaktifkan.**")

    # Handler untuk DM (Private Message) Live
    @client.on_message(filters.private & ~filters.me & ~filters.user(list(DEVELOPER_ID)))
    async def private_reply_handler(c: Client, message: Message):
        await process_and_reply(c, message)

    # Handler untuk Grup Live
    is_mentioned_or_reply = (filters.mentioned | filters.reply)
    @client.on_message(filters.group & is_mentioned_or_reply & ~filters.me)
    async def group_reply_handler(c: Client, message: Message):
        if isinstance(message.reply_to_message, Message) and not message.reply_to_message.from_user.is_self: return
        await process_and_reply(c, message)

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

    # Jalankan pemrosesan pesan offline untuk semua klien secara bersamaan
    await asyncio.gather(*(process_missed_messages(client) for client in clients))

    print("\n✅ Semua userbot aktif dan siap menerima pesan baru.")
    await asyncio.Event().wait()

if __name__ == "__main__":
    print("🚀 Memulai Bot Multi-User Cerdas (Versi Produksi)...")
    asyncio.run(main())
