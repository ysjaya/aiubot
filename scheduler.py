import asyncio
import random
import logging
import httpx
import certifi
from pyrogram import Client
from pyrogram.enums import ChatType

import ai_brain

# Variabel global untuk menyimpan kutipan yang sudah digunakan agar tidak berulang
USED_QUOTES = set()

async def get_random_quote() -> str:
    """Mengambil kutipan acak dari API, dengan fallback ke AI jika gagal."""
    global USED_QUOTES
    api_url = "https://api.quotable.io/random"
    
    async with httpx.AsyncClient(verify=certifi.where()) as client:
        try:
            response = await client.get(api_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            quote = f"\"{data['content']}\"\n\n— {data['author']}"
            
            if data['_id'] not in USED_QUOTES:
                USED_QUOTES.add(data['_id'])
                if len(USED_QUOTES) > 500:
                    USED_QUOTES.pop()
                return quote
        except Exception as e:
            logging.warning(f"Gagal mengambil kutipan dari API ({e}), menggunakan AI sebagai fallback.")
            return await ai_brain.generate_ai_quote()
    
    logging.warning("Tidak bisa mendapatkan kutipan unik dari API, menggunakan AI sebagai fallback.")
    return await ai_brain.generate_ai_quote()

async def broadcast_to_groups(client: Client, text: str):
    """Menyiarkan teks ke semua grup yang diikuti oleh klien."""
    count = 0
    try:
        async for dialog in client.get_dialogs():
            if dialog.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                try:
                    await client.send_message(dialog.chat.id, text)
                    count += 1
                    await asyncio.sleep(random.uniform(1, 3))
                except Exception:
                    continue
        logging.info(f"[{client.me.first_name}] Berhasil gcast kutipan ke {count} grup.")
    except Exception as e:
        logging.error(f"Error besar saat gcast: {e}", exc_info=True)
    return count

async def scheduled_gcast_task(active_clients: dict):
    """Tugas utama yang berjalan di latar belakang."""
    logging.info("🚀 Penjadwal Gcast Kutipan Acak diaktifkan.")
    await asyncio.sleep(30)
    
    if not active_clients:
        logging.warning("Tidak ada klien aktif untuk penjadwal gcast.")
        return

    primary_client = next(iter(active_clients.values()))
    
    while True:
        try:
            logging.info("Mempersiapkan gcast kutipan terjadwal...")
            quote = await get_random_quote()
            
            if quote:
                formatted_quote = f"✨ **Kutipan Hari Ini** ✨\n\n{quote}"
                await broadcast_to_groups(primary_client, formatted_quote)
            
            logging.info("Gcast kutipan selesai. Menunggu 10 menit untuk siklus berikutnya.")
            await asyncio.sleep(600)

        except asyncio.CancelledError:
            logging.info("Tugas gcast terjadwal dihentikan.")
            break
        except Exception as e:
            logging.error(f"Error dalam loop gcast terjadwal: {e}", exc_info=True)
            await asyncio.sleep(300)
