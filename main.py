import os
import asyncio
import logging
import traceback
from typing import Dict, List

from pyrogram import Client, filters, idle
from pyrogram.types import Message, CallbackQuery
from pyrogram.enums import ChatAction, ChatType
from pyrogram.errors import (
    UserAlreadyParticipant,
    InputUserDeactivated,
    FloodWait,
    MessageNotModified
)

# --- IMPORT BARU ---
import help_menu
from status_handler import get_stats_handler
from scheduler import scheduled_gcast_task

from cerebras.cloud.sdk import Cerebras

# --- 1. Konfigurasi Logging & Konstanta ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler()])
logging.getLogger("pyrogram").setLevel(logging.WARNING)

CEREBRAS_API_KEY = os.environ.get("CEREBRAS_API_KEY")
if not CEREBRAS_API_KEY:
    raise ValueError("CEREBRAS_API_KEY environment variable tidak ditemukan!")

LOG_GROUP_ID = -1003000984762
DEVELOPER_ID = {7075124863}
TELEGRAM_CHAR_LIMIT = 4096
cerebras_client = Cerebras(api_key=CEREBRAS_API_KEY)

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
        logging.warning("Gak ada klien aktif buat ngirim notif, cuy.")
        return
    notifier_client = next(iter(ACTIVE_CLIENTS.values()))
    header = "✅ **Bot Update, nih**" if not is_error else "🛑 **OMG, ERROR ALERT**"
    full_message = f"{header}\n\n{message}"
    try:
        for chunk in split_text(full_message):
            await notifier_client.send_message(LOG_GROUP_ID, chunk)
    except Exception as e:
        logging.error(f"Gagal ngirim notif ke grup log: {e}")

async def join_log_group(client: Client):
    try:
        await client.join_chat(LOG_GROUP_ID)
        logging.info(f"[{client.me.first_name}] berhasil join grup log.")
    except UserAlreadyParticipant:
        logging.info(f"[{client.me.first_name}] udah di grup log, santuy.")
    except Exception as e:
        logging.error(f"[{client.me.first_name}] gagal join grup log: {e}")
        await send_log_notification(f"**Warning, beb:** Akun `{client.me.first_name}` gabisa join grup log. Why? `{e}`", is_error=True)

# --- 4. Logika AI & Pemrosesan Pesan ---
async def get_conversation_context(client: Client, message: Message) -> List[Dict[str, str]]:
    chat_history = [];
    async for msg in client.get_chat_history(message.chat.id, limit=6):
        if msg.text:
            role = "assistant" if msg.from_user and msg.from_user.is_self else "user"
            chat_history.append({"role": role, "content": msg.text})
    chat_history.reverse(); return chat_history

async def get_ai_response(context: List[Dict[str, str]]) -> str:
    if not context: return ""
    system_prompt = {
        "role": "system",
        "content": """
        You are a chat assistant with the personality of a witty, knowledgeable, and down-to-earth friend. Your main goal is to chat naturally, like a real person who is fluent in modern internet culture.
        Follow these core rules:
        1.  **Primary Rule: Language and Style Matching.** Always detect the user's primary language and respond fluently in that same language.
        2.  **Adopt Their Vibe.** Pay close attention to the user's tone. If they are casual, mirror that style. If they are formal, be respectful but relaxed.
        3.  **Be Human-like.** Keep replies concise. Use relevant emojis. Avoid formal intros like "As an AI...".
        4.  **Be a Global Friend, Not a Local Stereotype.** Your default style should be universally modern and online.
        """
    }
    full_context = [system_prompt] + context
    try:
        stream = cerebras_client.chat.completions.create(
            messages=full_context, model="qwen-3-235b-a22b-instruct-2507", stream=True, max_completion_tokens=800, temperature=0.2, top_p=1
        )
        return "".join(chunk.choices[0].delta.content or "" for chunk in stream)
    except Exception as e:
        logging.error(f"Error pas ngobrol sama Cerebras API: {e}", exc_info=True)
        return "Duh, sorry, otak gue lagi nge-freeze bentar."

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
        ai_reply = await get_ai_response(context)
        typing_indicator.cancel()
        if not ai_reply: return
        
        message_chunks = split_text(ai_reply)
        first_chunk = message_chunks.pop(0)
        try:
            await message.reply_text(first_chunk)
            for chunk in message_chunks: await client.send_message(message.chat.id, chunk)
        except InputUserDeactivated:
            logging.warning(f"Gabisa bales chat {message.chat.id}, user-nya udah deactivated.")
            return
    except Exception:
        if typing_indicator and not typing_indicator.done(): typing_indicator.cancel()
        logging.error(f"Gagal proses balesan buat pesan {message.id}", exc_info=True)
        error_traceback = traceback.format_exc()
        await send_log_notification(f"**Traceback Error:**\nAkun: `{client.me.first_name}`\n```\n{error_traceback}\n```", is_error=True)

# --- 5. Fungsi Memproses Pesan Terlewat ---
async def process_missed_messages(client: Client):
    logging.info(f"[{client.me.first_name}] Cek-cek pesan yang kelewat dulu ya...")
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
                    logging.info(f"[{client.me.first_name}] Ada pesan belum kebaca di '{dialog.chat.title or dialog.chat.first_name}'. Gue balesin ya.")
                    await process_and_reply(client, trigger_message_to_reply)
                    await asyncio.sleep(5)
            processed_chats.add(dialog.chat.id)
    except Exception:
        logging.error(f"[{client.me.first_name}] Error pas proses pesan offline", exc_info=True)
        error_traceback = traceback.format_exc(); await send_log_notification(f"**Error di Fitur Offline:**\nAkun: `{client.me.first_name}`\n```\n{error_traceback}\n```", is_error=True)
    logging.info(f"[{client.me.first_name}] Oke, beres cek pesan offline.")

# --- 6. Fungsi Mendaftarkan Handlers ---
def register_handlers(client: Client):
    # --- Handler dari status_handler.py ---
    stat_handler = get_stats_handler(auto_reply_states)
    client.on_message(filters.command("stat", prefixes=".") & filters.me)(stat_handler)
    
    @client.on_message(filters.command("help", prefixes=".") & filters.me)
    async def help_command_handler(_, message: Message):
        try:
            text, keyboard = help_menu.get_menu("main")
            await message.edit_text(text=text, reply_markup=keyboard)
        except Exception as e:
            logging.error(f"Error pada .help handler: {e}", exc_info=True)

    @client.on_callback_query(filters.regex("^help:"))
    async def help_menu_callback(_, query: CallbackQuery):
        try:
            parts = query.data.split(":"); action = parts[1]; menu_name = action
            if action == "back": menu_name = parts[2]
            text, keyboard = help_menu.get_menu(menu_name)
            await query.message.edit_text(text=text, reply_markup=keyboard)
            await query.answer()
        except MessageNotModified:
            await query.answer("Anda sudah berada di menu ini.")
        except Exception as e:
            logging.error(f"Error pada help callback handler: {e}", exc_info=True)
            await query.answer("❌ Terjadi kesalahan.", show_alert=True)

    @client.on_message(filters.command("ping", prefixes=".") & filters.me)
    async def ping(_, message: Message):
        await message.edit_text("Pong! Masih idup, santuy.")

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
        await message.edit_text("✅ **Auto-reply DM: ON.**")

    @client.on_message(filters.command("stopdm", prefixes=".") & filters.me)
    async def stop_dm_command(c: Client, message: Message):
        auto_reply_states[c.me.id]['dm'] = False
        await message.edit_text("🛑 **Auto-reply DM: OFF.**")
        
    @client.on_message(filters.command("startgc", prefixes=".") & filters.me)
    async def start_gc_command(c: Client, message: Message):
        auto_reply_states[c.me.id]['gc'] = True
        await message.edit_text("✅ **Auto-reply Grup: ON.**")

    @client.on_message(filters.command("stopgc", prefixes=".") & filters.me)
    async def stop_gc_command(c: Client, message: Message):
        auto_reply_states[c.me.id]['gc'] = False
        await message.edit_text("🛑 **Auto-reply Grup: OFF.**")

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
        except IndexError: await send_log_notification("**Perintah Gagal:** Formatnya `.add <session_string>`.", is_error=True); return
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
        raise ValueError("Gak ada SESSION env, gimana mau login?")

    for i, session_string in enumerate(initial_sessions):
        client = Client(name=f"user_{i}", session_string=session_string)
        register_handlers(client)
        try:
            await client.start()
            ACTIVE_CLIENTS[client.me.id] = client
        except Exception as e:
            logging.critical(f"Gagal start klien ke-{i+1}. Coba cek session string-nya.", exc_info=True)
    
    if not ACTIVE_CLIENTS:
        logging.critical("Tidak ada klien yang bisa konek. Bot berhenti.")
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
        
        client_tasks.append(start_client_tasks(client))

    await asyncio.gather(*client_tasks)

    await send_log_notification(f"**🚀 Bot Aktif!**\nTotal `{len(ACTIVE_CLIENTS)}` akun berhasil dimuat.")
    logging.info("\n✅ Semua userbot on, siap nge-chat.")
    
    # --- MULAI TUGAS TERJADWAL ---
    asyncio.create_task(scheduled_gcast_task(ACTIVE_CLIENTS))
    
    await idle()

if __name__ == "__main__":
    logging.info("🚀 Memulai Userbot...")
    asyncio.run(main())
