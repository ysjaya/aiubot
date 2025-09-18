import os
import asyncio
import logging
import traceback
from typing import Dict, List

from pyrogram import Client, filters, idle
from pyrogram.types import Message
from pyrogram.enums import ChatAction, ChatType
from pyrogram.errors import (
    UserAlreadyParticipant,
    InputUserDeactivated,
    FloodWait,
)

# Impor dari file-file modul kita
from help_menu import HELP_TEXT
from status_handler import get_stats_handler
from scheduler import scheduled_gcast_task, get_random_quote, broadcast_to_groups
import ai_brain

# --- 1. Konfigurasi Logging & Konstanta ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler()])
logging.getLogger("pyrogram").setLevel(logging.WARNING)

LOG_GROUP_ID = -1003000984762 
DEVELOPER_ID = {7075124863}
TELEGRAM_CHAR_LIMIT = 4096

# --- 2. State Management (Global) ---
auto_reply_states: Dict[int, Dict[str, bool]] = {}
ACTIVE_CLIENTS: Dict[int, Client] = {}

# --- 3. Utilitas & Notifikasi ---
def split_text(text: str) -> List[str]:
    if len(text) <= TELEGRAM_CHAR_LIMIT: return [text]
    chunks = []
    while len(text) > 0:
        if len(text) <= TELEGRAM_CHAR_LIMIT: chunks.append(text); break
        chunk = text[:TELEGRAM_CHAR_LIMIT]
        split_pos = chunk.rfind('\n') if '\n' in chunk else chunk.rfind(' ')
        if split_pos == -1: split_pos = TELEGRAM_CHAR_LIMIT
        chunks.append(text[:split_pos]); text = text[split_pos:].lstrip()
    return chunks

async def send_log_notification(message: str, is_error: bool = False):
    if not ACTIVE_CLIENTS:
        logging.warning("Tidak ada klien aktif untuk mengirim notifikasi.")
        return
    notifier_client = next(iter(ACTIVE_CLIENTS.values()))
    header = "✅ **Bot Update**" if not is_error else "🛑 **Bot Error**"
    full_message = f"{header}\n\n{message}"
    try:
        for chunk in split_text(full_message):
            await notifier_client.send_message(LOG_GROUP_ID, chunk)
    except Exception as e:
        logging.error(f"Gagal mengirim notifikasi ke grup log: {e}")

async def join_log_group(client: Client):
    try:
        await client.join_chat(LOG_GROUP_ID)
        logging.info(f"[{client.me.first_name}] berhasil bergabung ke grup log.")
    except UserAlreadyParticipant:
        logging.info(f"[{client.me.first_name}] sudah ada di grup log.")
    except Exception as e:
        logging.error(f"[{client.me.first_name}] gagal bergabung ke grup log: {e}")
        await send_log_notification(f"**Peringatan:** Akun `{client.me.first_name}` gagal bergabung ke grup log. Error: `{e}`", is_error=True)

# --- 4. Logika Pemrosesan Pesan ---
async def get_conversation_context(client: Client, message: Message) -> List[Dict[str, str]]:
    chat_history = [];
    async for msg in client.get_chat_history(message.chat.id, limit=6):
        if msg.text:
            role = "assistant" if msg.from_user and msg.from_user.is_self else "user"
            chat_history.append({"role": role, "content": msg.text})
    chat_history.reverse(); return chat_history

async def typing_task(client, chat_id):
    while True:
        try:
            await client.send_chat_action(chat_id, action=ChatAction.TYPING)
            await asyncio.sleep(5)
        except (asyncio.CancelledError, Exception):
            break

async def process_and_reply(client: Client, message: Message):
    if not message.text: return
    typing_indicator = None
    try:
        typing_indicator = asyncio.create_task(typing_task(client, message.chat.id))
        context = await get_conversation_context(client, message)
        ai_reply = await ai_brain.get_ai_chat_response(context)
        typing_indicator.cancel()
        if not ai_reply: return
        
        message_chunks = split_text(ai_reply)
        first_chunk = message_chunks.pop(0)
        try:
            await message.reply_text(first_chunk)
            for chunk in message_chunks: await client.send_message(message.chat.id, chunk)
        except InputUserDeactivated:
            logging.warning(f"Gagal membalas pesan di {message.chat.id}, pengguna nonaktif.")
            return
    except Exception:
        if typing_indicator and not typing_indicator.done(): typing_indicator.cancel()
        logging.error(f"Gagal memproses balasan untuk pesan {message.id}", exc_info=True)
        error_traceback = traceback.format_exc()
        await send_log_notification(f"**Traceback Error:**\nAkun: `{client.me.first_name}`\n```\n{error_traceback}\n```", is_error=True)

# --- 5. Fungsi Memproses Pesan Terlewat ---
async def process_missed_messages(client: Client):
    logging.info(f"[{client.me.first_name}] Memeriksa pesan terlewat...")
    processed_chats = set()
    try:
        async for dialog in client.get_dialogs():
            if dialog.chat.id in processed_chats or dialog.chat.type not in [ChatType.PRIVATE, ChatType.SUPERGROUP, ChatType.GROUP]: continue
            last_message_from_us, trigger_message_to_reply = None, None
            async for msg in client.get_chat_history(dialog.chat.id, limit=20):
                if msg.from_user and msg.from_user.is_self: last_message_from_us = msg; break
                is_private_trigger = (dialog.chat.type == ChatType.PRIVATE and not (msg.from_user and msg.from_user.is_self) and not (msg.from_user and msg.from_user.is_bot) and (msg.from_user and msg.from_user.id not in DEVELOPER_ID))
                is_group_trigger = (dialog.chat.type in [ChatType.SUPERGROUP, ChatType.GROUP] and (msg.mentioned or (msg.reply_to_message and msg.reply_to_message.from_user and msg.reply_to_message.from_user.is_self)))
                if is_private_trigger or is_group_trigger: trigger_message_to_reply = msg
            
            if trigger_message_to_reply and (last_message_from_us is None or last_message_from_us.id < trigger_message_to_reply.id):
                states = auto_reply_states.get(client.me.id, {})
                if (dialog.chat.type == ChatType.PRIVATE and states.get('dm', True)) or \
                   (dialog.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP] and states.get('gc', True)):
                    logging.info(f"[{client.me.first_name}] Menemukan pesan belum dibaca di '{dialog.chat.title or dialog.chat.first_name}'. Membalas...")
                    await process_and_reply(client, trigger_message_to_reply)
                    await asyncio.sleep(5)
            processed_chats.add(dialog.chat.id)
    except Exception:
        logging.error(f"[{client.me.first_name}] Error saat memproses pesan offline", exc_info=True)
        error_traceback = traceback.format_exc(); await send_log_notification(f"**Error di Fitur Offline:**\nAkun: `{client.me.first_name}`\n```\n{error_traceback}\n```", is_error=True)
    logging.info(f"[{client.me.first_name}] Selesai memeriksa pesan offline.")

# --- 6. Fungsi Pendaftaran Handlers ---
def register_handlers(client: Client):
    stat_handler = get_stats_handler(auto_reply_states)
    client.on_message(filters.command("stat", prefixes=".") & filters.me)(stat_handler)
    
    @client.on_message(filters.command("help", prefixes=".") & filters.me)
    async def help_command_handler(_, message: Message):
        try:
            await message.edit_text(text=HELP_TEXT, disable_web_page_preview=True)
        except Exception as e:
            logging.error(f"Error pada .help handler: {e}", exc_info=True)

    @client.on_message(filters.command("ping", prefixes=".") & filters.me)
    async def ping(_, message: Message):
        await message.edit_text("Pong!")

    @client.on_message(filters.command("id", prefixes=".") & filters.me)
    async def id_command(c: Client, message: Message):
        text = f"👤 **ID Anda:** `{c.me.id}`\n"
        if message.chat.type != ChatType.PRIVATE:
            text += f"💬 **ID Chat Ini:** `{message.chat.id}`\n"
        if message.reply_to_message:
            user = message.reply_to_message.from_user
            text += f"\n👤 **Info Target Reply:**\n- **Nama:** {user.first_name}\n- **ID:** `{user.id}`"
        await message.edit_text(text)
        
    @client.on_message(filters.command("startdm", prefixes=".") & filters.me)
    async def start_dm_command(c: Client, message: Message):
        auto_reply_states[c.me.id]['dm'] = True
        await message.edit_text("✅ **Auto-reply DM: ON**")

    @client.on_message(filters.command("stopdm", prefixes=".") & filters.me)
    async def stop_dm_command(c: Client, message: Message):
        auto_reply_states[c.me.id]['dm'] = False
        await message.edit_text("🛑 **Auto-reply DM: OFF**")
        
    @client.on_message(filters.command("startgc", prefixes=".") & filters.me)
    async def start_gc_command(c: Client, message: Message):
        auto_reply_states[c.me.id]['gc'] = True
        await message.edit_text("✅ **Auto-reply Grup: ON**")

    @client.on_message(filters.command("stopgc", prefixes=".") & filters.me)
    async def stop_gc_command(c: Client, message: Message):
        auto_reply_states[c.me.id]['gc'] = False
        await message.edit_text("🛑 **Auto-reply Grup: OFF**")

    @client.on_message(filters.private & ~filters.me & ~filters.bot & ~filters.user(list(DEVELOPER_ID)))
    async def private_reply_handler(c: Client, message: Message):
        if not auto_reply_states.get(c.me.id, {}).get('dm', True): return
        await process_and_reply(c, message)
    
    is_mentioned_or_reply = (filters.mentioned | filters.reply)
    @client.on_message(filters.group & is_mentioned_or_reply & ~filters.me)
    async def group_reply_handler(c: Client, message: Message):
        if not auto_reply_states.get(c.me.id, {}).get('gc', True): return
        if isinstance(message.reply_to_message, Message) and not (message.reply_to_message.from_user and message.reply_to_message.from_user.is_self): return
        await process_and_reply(c, message)

    @client.on_message(filters.command("add", prefixes=".") & filters.user(list(DEVELOPER_ID)))
    async def add_user_command(c: Client, message: Message):
        await message.delete();
        try: new_session_string = message.text.split(" ", 1)[1].strip()
        except IndexError: await send_log_notification("**Perintah Gagal:** Format `.add <session_string>`.", is_error=True); return
        response_msg = await c.send_message(LOG_GROUP_ID, f"Memproses user baru...")
        try:
            new_client = Client(name=f"user_{len(ACTIVE_CLIENTS)}", session_string=new_session_string)
            await new_client.start()
            me = new_client.me
            ACTIVE_CLIENTS[me.id] = new_client
            auto_reply_states[me.id] = {'dm': True, 'gc': True}
            register_handlers(new_client)
            await join_log_group(new_client)
            asyncio.create_task(process_missed_messages(new_client))
            success_message = f"**User baru berhasil ditambahkan!**\n\n**Nama:** {me.first_name}\n**ID:** `{me.id}`"
            await response_msg.edit_text(success_message)
            logging.info(f"Berhasil menambahkan user baru: {me.first_name}")
        except Exception as e:
            logging.error(f"Gagal menambahkan user baru: {e}", exc_info=True)
            await response_msg.edit_text(f"**Gagal menambahkan user baru.**\n\n**Error:**\n`{e}`")

    @client.on_message(filters.command("quotes", prefixes=".") & filters.user(list(DEVELOPER_ID)))
    async def quotes_gcast_command(c: Client, message: Message):
        try:
            await message.edit_text("🚀 **Memulai G-Cast Kutipan Acak...**")
            quote = await get_random_quote()
            if not quote:
                await message.edit_text("❌ **Gagal mengambil kutipan.** Coba lagi nanti.")
                return
            formatted_quote = f"✨ **Kutipan Acak** ✨\n\n{quote}"
            await message.edit_text(f"✅ **Kutipan Ditemukan!** Mengirim ke semua grup...")
            count = await broadcast_to_groups(c, formatted_quote)
            final_text = f"✅ **G-Cast Kutipan Acak Selesai!** Terkirim ke **{count}** grup."
            await message.edit_text(final_text)
            await send_log_notification(f"📣 **Manual G-Cast Kutipan Selesai!**\nAkun `{c.me.first_name}` telah mengirim kutipan acak.")
        except Exception as e:
            logging.error(f"Error pada perintah .quotes: {e}", exc_info=True)
            await message.edit_text(f"❌ Terjadi kesalahan pada perintah .quotes:\n`{e}`")

    @client.on_message(filters.command("gcast", prefixes=".") & filters.user(list(DEVELOPER_ID)))
    async def gcast_command(c: Client, message: Message):
        try: text_to_send = message.text.split(" ", 1)[1]
        except IndexError: await message.edit_text("Format: `.gcast <pesan>`"); return
        await message.delete(); count = 0
        async for dialog in c.get_dialogs():
            if dialog.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                try: await c.send_message(dialog.chat.id, text_to_send); count += 1; await asyncio.sleep(1)
                except Exception: continue
        await send_log_notification(f"📣 **GCast Selesai!**\nAkun `{c.me.first_name}` mengirim ke `{count}` grup.")

    @client.on_message(filters.command("gucast", prefixes=".") & filters.user(list(DEVELOPER_ID)))
    async def gucast_command(c: Client, message: Message):
        try: text_to_send = message.text.split(" ", 1)[1]
        except IndexError: await message.edit_text("Format: `.gucast <pesan>`"); return
        await message.delete(); count = 0
        async for dialog in c.get_dialogs():
            if dialog.chat.type == ChatType.PRIVATE:
                try: await c.send_message(dialog.chat.id, text_to_send); count += 1; await asyncio.sleep(1)
                except Exception: continue
        await send_log_notification(f"📣 **GUCast Selesai!**\nAkun `{c.me.first_name}` mengirim ke `{count}` user.")

# --- 7. Logika Utama ---
async def main():
    initial_sessions = []
    i = 1
    while True:
        key = f"SESSION{i if i > 1 else ''}"
        session_str = os.environ.get(key)
        if session_str:
            initial_sessions.append(session_str)
            i += 1
        else:
            break
    if not initial_sessions:
        raise ValueError("Tidak ada variabel SESSION di lingkungan.")

    for i, session_string in enumerate(initial_sessions):
        client = Client(name=f"user_{i}", session_string=session_string)
        register_handlers(client)
        try:
            await client.start()
            ACTIVE_CLIENTS[client.me.id] = client
        except Exception as e:
            logging.critical(f"Gagal memulai klien ke-{i+1}. Periksa session string.", exc_info=True)
    
    if not ACTIVE_CLIENTS:
        logging.critical("Tidak ada klien yang berhasil terhubung. Bot berhenti.")
        return

    client_tasks = []
    for client in ACTIVE_CLIENTS.values():
        me = client.me
        if me.id not in auto_reply_states:
            auto_reply_states[me.id] = {'dm': True, 'gc': True}
        
        logging.info(f"✅ Klien {me.first_name} (@{me.username}) terhubung.")
        
        async def start_client_tasks(c):
            await asyncio.sleep(3)
            await join_log_group(c)
            await asyncio.sleep(2)
            startup_message = f"**Akun Terhubung:** {c.me.first_name} (@{c.me.username})"
            await send_log_notification(startup_message)
            asyncio.create_task(process_missed_messages(c))
        
        client_tasks.append(start_client_tasks(c))

    await asyncio.gather(*client_tasks)

    await send_log_notification(f"**🚀 Bot Aktif!**\nTotal `{len(ACTIVE_CLIENTS)}` akun berhasil dimuat.")
    logging.info("\n✅ Semua userbot aktif dan siap membalas.")
    
    asyncio.create_task(scheduled_gcast_task(ACTIVE_CLIENTS))
    
    await idle()

if __name__ == "__main__":
    logging.info("🚀 Memulai Userbot...")
    asyncio.run(main())
