import asyncio
import random
import logging
import httpx
from pyrogram import Client
from pyrogram.enums import ChatType

# Variabel global untuk menyimpan kutipan yang sudah digunakan agar tidak berulang
USED_QUOTES = set()

async def get_random_quote() -> str:
    """Mengambil kutipan acak dari API publik dan memastikan tidak berulang."""
    global USED_QUOTES
    # API gratis tanpa kunci otentikasi
    api_url = "https://api.quotable.io/random"
    
    async with httpx.AsyncClient() as client:
        for _ in range(5): # Coba hingga 5 kali untuk mendapatkan kutipan unik
            try:
                response = await client.get(api_url, timeout=10)
                response.raise_for_status()
                data = response.json()
                quote = f"\"{data['content']}\"\n\n— {data['author']}"
                
                # Jika kutipan belum pernah digunakan, kembalikan
                if data['_id'] not in USED_QUOTES:
                    USED_QUOTES.add(data['_id'])
                    # Jaga agar set tidak terlalu besar, simpan 500 kutipan terakhir
                    if len(USED_QUOTES) > 500:
                        USED_QUOTES.pop()
                    return quote
            except httpx.RequestError as e:
                logging.error(f"Gagal mengambil kutipan: {e}")
                await asyncio.sleep(5)
            except Exception as e:
                logging.error(f"Error pada get_random_quote: {e}")
                return None
    
    logging.warning("Tidak bisa mendapatkan kutipan unik setelah beberapa kali percobaan.")
    return None

async def broadcast_to_groups(client: Client, text: str):
    """Menyiarkan teks ke semua grup yang diikuti oleh klien."""
    count = 0
    try:
        async for dialog in client.get_dialogs():
            if dialog.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                try:
                    await client.send_message(dialog.chat.id, text)
                    count += 1
                    await asyncio.sleep(random.uniform(1, 3)) # Jeda acak agar tidak spam
                except Exception:
                    continue # Lanjut ke grup lain jika gagal
        logging.info(f"[{client.me.first_name}] Berhasil gcast kutipan ke {count} grup.")
    except Exception as e:
        logging.error(f"Error besar saat gcast terjadwal: {e}", exc_info=True)

async def scheduled_gcast_task(active_clients: dict):
    """Tugas utama yang berjalan di latar belakang."""
    logging.info("🚀 Penjadwal Gcast Kutipan Acak diaktifkan.")
    # Tunggu sebentar saat startup agar bot siap sepenuhnya
    await asyncio.sleep(30)
    
    if not active_clients:
        logging.warning("Tidak ada klien aktif untuk penjadwal gcast.")
        return

    # Pilih klien utama (pertama) untuk melakukan gcast
    primary_client = next(iter(active_clients.values()))
    
    while True:
        try:
            logging.info("Mempersiapkan gcast kutipan terjadwal...")
            quote = await get_random_quote()
            
            if quote:
                # Tambahkan header
                formatted_quote = f"✨ **Kutipan Inspiratif Hari Ini** ✨\n\n{quote}"
                await broadcast_to_groups(primary_client, formatted_quote)
            
            # Tunggu 1/2 jam sebelum pengiriman berikutnya
            logging.info("Gcast kutipan selesai. Menunggu 1 jam untuk siklus berikutnya.")
            await asyncio.sleep(1800)

        except asyncio.CancelledError:
            logging.info("Tugas gcast terjadwal dihentikan.")
            break
        except Exception as e:
            logging.error(f"Error dalam loop gcast terjadwal: {e}", exc_info=True)
            # Jika terjadi error, tunggu 5 menit sebelum mencoba lagi
            await asyncio.sleep(300)
