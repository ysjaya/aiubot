import os
import asyncio
import logging
import traceback
from typing import Dict, List

from pyrogram import Client, filters, idle
from pyrogram.types import Message, CallbackQuery
from pyrogram.enums import ChatAction, ChatType
from pyrogram.errors import UserAlreadyParticipant

# Mengimpor menu dari file help_menu.py
import help_menu

from cerebras.cloud.sdk import Cerebras

# --- 1. Konfigurasi Logging & Konstanta ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)

CEREBRAS_API_KEY = os.environ.get("CEREBRAS_API_KEY")
if not CEREBRAS_API_KEY:
    raise ValueError("CEREBRAS_API_KEY environment variable tidak ditemukan!")

LOG_GROUP_ID = -1003000984762
DEVELOPER_ID = {7075124863}
TELEGRAM_CHAR_LIMIT = 4096
cerebras_client = Cerebras(api_key=CEREBRAS_API_KEY)

# --- 2. State Management (Global) ---
auto_reply_states: Dict[int, bool] = {}
ACTIVE_CLIENTS: Dict[int, Client] = {}

# --- 3. Utilitas & Notifikasi ---
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

async def send_log_notification(message: str, is_error: bool = False):
    if not ACTIVE_CLIENTS:
        logging.warning("Tidak ada klien aktif untuk mengirim notifikasi log.")
        return
    notifier_client = next(iter(ACTIVE_CLIENTS.values()))
    header = "✅ **Notifikasi Bot**" if not is_error else "🛑 **ERROR PADA BOT**"
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
        logging.info(f"[{client.me.first_name}] sudah menjadi anggota grup log.")
    except Exception as e:
        logging.error(f"[{client.me.first_name}] gagal bergabung ke grup log: {e}")
        await send_log_notification(f"**Peringatan:** Akun `{client.me.first_name}` gagal bergabung ke grup log. Error: `{e}`", is_error=True)

# --- 4. Logika AI & Pemrosesan Pesan ---
async def get_conversation_context(client: Client, message: Message) -> List[Dict[str, str]]:
    chat_history = []
    async for msg in client.get_chat_history(message.chat.id, limit=6):
        if msg.text:
            role = "assistant" if msg.from_user and msg.from_user.is_self else "user"
            chat_history.append({"role": role, "content": msg.text})
    chat_history.reverse()
    return chat_history

async def get_ai_response(context: List[Dict[str, str]]) -> str:
    if not context: return ""
    system_prompt = {
        "role": "system",
        "content": "You are a helpful assistant. Always detect the language of the user's message and respond in the exact same language. For example, if the user writes in Indonesian, you must reply in Indonesian."
    }
    full_context = [system_prompt] + context
    try:
        stream = cerebras_client.chat.completions.create(
            messages=full_context,
            model="qwen-3-235b-a22b-instruct-2507",
            stream=True,
            max_completion_tokens=200,
            temperature=0.7,
            top_p=0.8
        )
        return "".join(chunk.choices[0].delta.content or "" for chunk in stream)
    except Exception as e:
        logging.error(f"Error saat menghubungi Cerebras API: {e}", exc_info=True)
        return "Terjadi kesalahan pada sistem AI."

async def typing_task(client, chat_id):
    while True:
        try:
            await client.send_chat_action(chat_id, action=ChatAction.TYPING)
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            break
        except Exception:
            break

async def process_and_reply(client: Client, message: Message):
    if not auto_reply_states.get(client.me.id, True) or not message.text: return
    typing_indicator = None
    try:
        typing_indicator = asyncio.create_task(typing_task(client, message.chat.id))
        context = await get_conversation_context(client, message)
        ai_reply = await get_ai_response(context)
        typing_indicator.cancel()
        if not ai_reply: return
        message_chunks = split_text(ai_reply)
        first_chunk = message_chunks.pop(0)
        await message.reply_text(first_chunk)
        for chunk in message_chunks:
            await client.send_message(message.chat.id, chunk)
    except Exception:
        if typing_indicator and not typing_indicator.done():
            typing_indicator.cancel()
        logging.error(f"Gagal memproses balasan untuk pesan {message.id}", exc_info=True)
        error_traceback = traceback.format_exc()
        await send_log_notification(f"**Traceback Error:**\nAkun: `{client.me.first_name}`\n```\n{error_traceback}\n```", is_error=True)

# --- 5. Fungsi Memproses Pesan Terlewat ---
async def process_missed_messages(client: Client):
    logging.info(f"[{client.me.first_name}] Memeriksa pesan yang terlewat...")
    processed_chats = set()
    try:
        async for dialog in client.get_dialogs():
            if dialog.chat.id in processed_chats or dialog.chat.type not in [ChatType.PRIVATE, ChatType.SUPERGROUP, ChatType.GROUP]: continue
            last_message_from_us, trigger_message_to_reply = None, None
            async for msg in client.get_chat_history(dialog.chat.id, limit=20):
                if msg.from_user and msg.from_user.is_self:
                    last_message_from_us = msg; break
                is_private_trigger = (dialog.chat.type == ChatType.PRIVATE and not (msg.from_user and msg.from_user.is_self) and not (msg.from_user and msg.from_user.is_bot) and (msg.from_user and msg.from_user.id not in DEVELOPER_ID))
                is_group_trigger = (dialog.chat.type in [ChatType.SUPERGROUP, ChatType.GROUP] and (msg.mentioned or (msg.reply_to_message and msg.reply_to_message.from_user and msg.reply_to_message.from_user.is_self)))
                if is_private_trigger or is_group_trigger:
                    trigger_message_to_reply = msg
            if trigger_message_to_reply and (last_message_from_us is None or last_message_from_us.id < trigger_message_to_reply.id):
                logging.info(f"[{client.me.first_name}] Menemukan pesan belum terbalas di '{dialog.chat.title or dialog.chat.first_name}'. Membalas...")
                await process_and_reply(client, trigger_message_to_reply)
                await asyncio.sleep(5)
            processed_chats.add(dialog.chat.id)
    except Exception:
        logging.error(f"[{client.me.first_name}] Error kritis saat memproses pesan offline", exc_info=True)
        error_traceback = traceback.format_exc()
        await send_log_notification(f"**Traceback Error di Fitur Offline:**\nAkun: `{client.me.first_name}`\n```\n{error_traceback}\n```", is_error=True)
    logging.info(f"[{client.me.first_name}] Selesai memeriksa pesan yang terlewat.")

# --- 6. Fungsi Mendaftarkan Handlers ---
def register_handlers(client: Client):
    @client.on_message(filters.command("help", prefixes=".") & filters.me)
    async def help_command_handler(_, message: Message):
        await message.edit_text(text=help_menu.main_menu_text, reply_markup=help_menu.main_menu_keyboard)

    @client.on_callback_query(filters.regex("^help_"))
    async def help_menu_callback(_, query: CallbackQuery):
        data = query.data
        if data == "help_main":
            await query.message.edit_text(text=help_menu.main_menu_text, reply_markup=help_menu.main_menu_keyboard)
        elif data == "help_utility":
            await query.message.edit_text(text=help_menu.utility_menu_text, reply_markup=help_menu.back_button_keyboard)
        elif data == "help_control":
            await query.message.edit_text(text=help_menu.control_menu_text, reply_markup=help_menu.back_button_keyboard)
        elif data == "help_developer":
            await query.message.edit_text(text=help_menu.developer_menu_text, reply_markup=help_menu.back_button_keyboard)
        await query.answer()

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
            text += f"\n👤 **Info Pengguna Dibalas:**\n- **Nama:** {user.first_name}\n- **ID:** `{user.id}`"
        await message.edit_text(text)

    @client.on_message(filters.command("start", prefixes=".") & filters.me)
    async def start(c: Client, message: Message):
        auto_reply_states[c.me.id] = True
        await message.edit_text(f"✅ **Balas otomatis diaktifkan.**")

    @client.on_message(filters.command("stop", prefixes=".") & filters.me)
    async def stop(c: Client, message: Message):
        auto_reply_states[c.me.id] = False
        await message.edit_text(f"🛑 **Balas otomatis dinonaktifkan.**")

    @client.on_message(filters.private & ~filters.me & ~filters.bot & ~filters.user(list(DEVELOPER_ID)))
    async def private_reply_handler(c: Client, message: Message):
        await process_and_reply(c, message)

    is_mentioned_or_reply = (filters.mentioned | filters.reply)
    @client.on_message(filters.group & is_mentioned_or_reply & ~filters.me)
    async def group_reply_handler(c: Client, message: Message):
        if isinstance(message.reply_to_message, Message) and not (message.reply_to_message.from_user and message.reply_to_message.from_user.is_self):
            return
        await process_and_reply(c, message)

    @client.on_message(filters.command("add", prefixes=".") & filters.user(list(DEVELOPER_ID)))
    async def add_user_command(c: Client, message: Message):
        await message.delete()
        try:
            new_session_string = message.text.split(" ", 1)[1].strip()
        except IndexError:
            await send_log_notification("**Perintah Gagal:** Format `.add <session_string>` salah.", is_error=True)
            return
        response_msg = await c.send_message(LOG_GROUP_ID, f"Mencoba menambahkan pengguna baru...")
        try:
            new_client = Client(name=f"user_{len(ACTIVE_CLIENTS)}", session_string=new_session_string)
            await new_client.start()
            me = new_client.me
            ACTIVE_CLIENTS[me.id] = new_client
            auto_reply_states[me.id] = True
            register_handlers(new_client)
            await join_log_group(new_client)
            asyncio.create_task(process_missed_messages(new_client))
            success_message = f"**Pengguna Baru Berhasil Ditambahkan**\n\n**Akun:** {me.first_name}\n**Username:** @{me.username}\n**ID:** `{me.id}`"
            await response_msg.edit_text(success_message)
            logging.info(f"Berhasil menambahkan pengguna baru: {me.first_name}")
        except Exception as e:
            logging.error(f"Gagal menambahkan pengguna baru: {e}", exc_info=True)
            error_message = f"**Gagal Menambahkan Pengguna Baru**\n\n**Error:**\n`{e}`\n\nPastikan session string valid dan tidak sedang digunakan."
            await response_msg.edit_text(error_message)

    @client.on_message(filters.command("gcast", prefixes=".") & filters.user(list(DEVELOPER_ID)))
    async def gcast_command(c: Client, message: Message):
        try:
            text_to_send = message.text.split(" ", 1)[1]
        except IndexError:
            await message.edit_text("Format salah. Gunakan `.gcast <pesan>`")
            return
        await message.delete()
        count = 0
        async for dialog in c.get_dialogs():
            if dialog.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                try:
                    await c.send_message(dialog.chat.id, text_to_send)
                    count += 1
                    await asyncio.sleep(1)
                except Exception:
                    continue
        await send_log_notification(f"📣 **GCast Selesai**\nAkun `{c.me.first_name}` telah mengirim pesan ke `{count}` grup.")

    @client.on_message(filters.command("gucast", prefixes=".") & filters.user(list(DEVELOPER_ID)))
    async def gucast_command(c: Client, message: Message):
        try:
            text_to_send = message.text.split(" ", 1)[1]
        except IndexError:
            await message.edit_text("Format salah. Gunakan `.gucast <pesan>`")
            return
        await message.delete()
        count = 0
        async for dialog in c.get_dialogs():
            if dialog.chat.type == ChatType.PRIVATE:
                try:
                    await c.send_message(dialog.chat.id, text_to_send)
                    count += 1
                    await asyncio.sleep(1)
                except Exception:
                    continue
        await send_log_notification(f"📣 **GUCast Selesai**\nAkun `{c.me.first_name}` telah mengirim pesan ke `{count}` pengguna.")

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
        raise ValueError("Tidak ada SESSION environment variable yang ditemukan!")

    for i, session_string in enumerate(initial_sessions):
        client = Client(name=f"user_{i}", session_string=session_string)
        register_handlers(client)
        try:
            await client.start()
            ACTIVE_CLIENTS[client.me.id] = client
        except Exception as e:
            logging.critical(f"Gagal memulai klien awal ke-{i+1}. Periksa session string.", exc_info=True)

    if not ACTIVE_CLIENTS:
        logging.critical("Tidak ada klien yang berhasil terhubung. Bot berhenti.")
        return

    for client in ACTIVE_CLIENTS.values():
        me = client.me
        if me.id not in auto_reply_states:
            auto_reply_states[me.id] = True
        logging.info(f"✅ Klien untuk {me.first_name} (@{me.username}) berhasil terhubung.")
        
        await asyncio.sleep(3)
        await join_log_group(client)
        await asyncio.sleep(2)
        
        startup_message = f"**Akun Terhubung:** {me.first_name} (@{me.username})"
        await send_log_notification(startup_message)
        
        asyncio.create_task(process_missed_messages(client))

    await send_log_notification(f"**Sistem Bot Online.**\nTotal `{len(ACTIVE_CLIENTS)}` akun berhasil dimuat.")
    logging.info("\n✅ Semua userbot aktif dan siap menerima pesan baru.")
    await idle()

if __name__ == "__main__":
    logging.info("🚀 Memulai Bot Multi-User Cerdas (Platform V5)...")
    asyncio.run(main())
