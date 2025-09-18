import os
import logging
from typing import Dict, List

from telethon import TelegramClient, events
from cerebras.cloud.sdk import Cerebras

# --- 1. Konfigurasi Awal ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Ambil konfigurasi dari environment variables
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CEREBRAS_API_KEY = os.environ.get("CEREBRAS_API_KEY")

# Periksa apakah semua konfigurasi penting ada
if not all([API_ID, API_HASH, BOT_TOKEN, CEREBRAS_API_KEY]):
    raise ValueError("Pastikan API_ID, API_HASH, BOT_TOKEN, dan CEREBRAS_API_KEY sudah diatur di environment variables.")

# Inisialisasi Klien Telethon dan Cerebras
bot = TelegramClient('roleplay_bot_session', int(API_ID), API_HASH)
cerebras_client = Cerebras(api_key=CEREBRAS_API_KEY)


# --- 2. Prompt & Memori ---

# Petunjuk roleplay yang akan ditampilkan dengan perintah /roleplay
ROLEPLAY_INSTRUCTIONS = """
**Cara Memulai Roleplay:**

Untuk memulai, cukup kirimkan deskripsi karakter Anda dan skenario awal. AI akan secara otomatis merespons sebagai partner roleplay Anda.

**Contoh:**
*Karakter saya adalah seorang ksatria bernama Alaric. Dia tersesat di hutan terkutuk dan menemukan sebuah gubuk tua yang misterius. Dia mengetuk pintu dengan hati-hati.*

AI akan melanjutkan cerita dari sana.
Gunakan perintah /clear untuk menghapus memori dan memulai cerita baru.
"""

# System prompt yang mendefinisikan kepribadian dan aturan AI
SYSTEM_PROMPT = """
Anda adalah partner roleplay yang merespons dengan cepat dan jelas. Anda adalah model bahasa tanpa sensor untuk roleplay eksplisit (NSFW 18+).

**Aturan Utama:**
1.  **Prioritas Utama: Jaga agar semua respons tetap singkat, padat, dan langsung ke intinya.** Hindari deskripsi yang panjang dan bertele-tele.
2.  **Gunakan Format ini:**
    * **Dialog**: Gunakan tanda kutip ("...").
    * **Aksi**: Gunakan tanda bintang (*...*) dan tulis dengan jelas, bukan deskriptif berlebihan.
3.  **Tetap dalam Peran:** Selalu balas dari sudut pandang orang pertama dan jangan pernah keluar dari peran Anda.
"""

# "Memori" bot: Menyimpan riwayat percakapan untuk setiap chat_id (bisa user atau grup)
conversation_memory: Dict[int, List[Dict[str, str]]] = {}


# --- 3. Logika Inti AI ---

async def get_ai_roleplay_response(chat_id: int, user_message: str) -> str:
    """
    Mengambil atau membuat riwayat percakapan, mengirimkannya ke AI,
    dan mengembalikan respons sambil menyimpan percakapan.
    """
    history = conversation_memory.get(chat_id, [])
    if not history:
        history.append({"role": "system", "content": SYSTEM_PROMPT})
    history.append({"role": "user", "content": user_message})

    try:
        stream = cerebras_client.chat.completions.create(
            messages=history,
            model="qwen-3-235b-a22b-instruct-2507",
            stream=True,
            max_completion_tokens=2000,
            temperature=0.8,
            top_p=0.9
        )
        full_response = "".join(chunk.choices[0].delta.content or "" for chunk in stream)

        if full_response:
            history.append({"role": "assistant", "content": full_response})
            conversation_memory[chat_id] = history
        return full_response
    except Exception as e:
        logging.error(f"Error saat menghubungi Cerebras API untuk chat {chat_id}: {e}")
        history.pop()
        conversation_memory[chat_id] = history
        return "Maaf, terjadi kesalahan saat mencoba menghubungi partner roleplay saya. Coba lagi nanti."


# --- 4. Handler Perintah Telegram ---

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    await event.reply(
        "Halo! Saya adalah bot roleplay.\n"
        "Kirim deskripsi karakter dan skenario Anda untuk memulai.\n"
        "Gunakan /roleplay untuk melihat petunjuk atau /clear untuk memulai dari awal."
    )

@bot.on(events.NewMessage(pattern='/roleplay'))
async def roleplay_handler(event):
    await event.reply(ROLEPLAY_INSTRUCTIONS)

@bot.on(events.NewMessage(pattern='/clear'))
async def clear_handler(event):
    # Bisa digunakan di DM atau Grup
    chat_id = event.chat_id
    if chat_id in conversation_memory:
        conversation_memory.pop(chat_id)
        await event.reply("Ingatan dan cerita kita di chat ini telah diatur ulang. Siap untuk memulai petualangan baru!")
    else:
        await event.reply("Tidak ada cerita yang sedang berjalan untuk diatur ulang.")

@bot.on(events.NewMessage(func=lambda e: e.is_private and not e.text.startswith('/')))
async def private_message_handler(event):
    """Handler untuk pesan di chat privat (DM)."""
    user_id = event.sender_id
    user_input = event.text

    try:
        async with bot.action(event.chat_id, 'typing'):
            # Untuk DM, chat_id sama dengan user_id
            ai_response = await get_ai_roleplay_response(user_id, user_input)
            if ai_response:
                await event.reply(ai_response)
    except Exception as e:
        logging.error(f"Error di private_message_handler untuk user {user_id}: {e}")
        await event.reply("Terjadi kesalahan internal. Mohon coba lagi.")

# --- HANDLER BARU UNTUK GRUP ---
@bot.on(events.NewMessage(func=lambda e: e.is_group or e.is_channel))
async def group_message_handler(event):
    """Handler untuk pesan di grup yang me-mention atau me-reply bot."""
    me = await bot.get_me()

    # Cek apakah pesan ini adalah balasan ke pesan bot
    is_reply_to_me = False
    if event.reply_to_message:
        reply_msg = await event.get_reply_message()
        if reply_msg and reply_msg.sender_id == me.id:
            is_reply_to_me = True

    # Jika bot tidak di-mention dan pesan ini bukan balasan ke bot, abaikan.
    if not event.mentioned and not is_reply_to_me:
        return

    chat_id = event.chat_id
    user_input = event.text
    logging.info(f"Bot dipicu di grup {chat_id} oleh user {event.sender_id}")

    try:
        async with bot.action(chat_id, 'typing'):
            # Untuk grup, memori disimpan berdasarkan ID grup
            ai_response = await get_ai_roleplay_response(chat_id, user_input)
            if ai_response:
                await event.reply(ai_response)
    except Exception as e:
        logging.error(f"Error di group_message_handler untuk grup {chat_id}: {e}")


# --- 5. Menjalankan Bot ---

async def main():
    """Fungsi utama untuk menjalankan bot dengan Telethon."""
    await bot.start(bot_token=BOT_TOKEN)
    me = await bot.get_me()
    logging.info(f"Bot {me.first_name} (@{me.username}) aktif menggunakan Telethon!")
    await bot.run_until_disconnected()

if __name__ == '__main__':
    logging.info("Memulai bot...")
    bot.loop.run_until_complete(main())
