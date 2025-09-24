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
                    # Hapus kutipan lama jika set terlalu besar
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
                    # Jeda acak untuk menghindari pembatasan API
                    await asyncio.sleep(random.uniform(1, 3))
                except Exception:
                    # Lanjutkan jika gagal mengirim ke satu grup
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
                # --- FOOTER PROMOSI DITAMBAHKAN DI SINI ---
                promo_footer = (
                    "Free Rp Multi-Character Chatbot or make Your own character @imgplaybot\n\n"
                    "Free Ai Chatbot With many capabilities such as: helping you with your assignments, chatting as friends, creating codes and so on, try @elievebot for free."
                )
                
                # Menggabungkan header, kutipan, dan footer promosi
                # Ini memastikan format 2x enter setelah nama penulis dan 1x enter antar baris promo
                formatted_message = f"✨ **Quotes News** ✨\n\n{quote}\n\n{promo_footer}"
                
                await broadcast_to_groups(primary_client, formatted_message)
            
            logging.info("Gcast kutipan selesai. Menunggu 1 jam untuk siklus berikutnya.")
            await asyncio.sleep(3600) # Diubah dari 10 menit ke 1 jam

        except asyncio.CancelledError:
            logging.info("Tugas gcast terjadwal dihentikan.")
            break
        except Exception as e:
            logging.error(f"Error dalam loop gcast terjadwal: {e}", exc_info=True)
            await asyncio.sleep(300) # Tunggu 5 menit sebelum mencoba lagi jika ada error
    
