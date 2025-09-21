import os
import io
import asyncio
import logging
import httpx

from pyrogram import Client
from pyrogram.types import Message
from pyrogram.enums import ChatAction

# --- Konfigurasi Replicate API ---
REPLICATE_API_URL = "https://api.replicate.com/v1/predictions"
REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN")

# ID Versi Model "nastia" di Replicate
NASTIA_MODEL_VERSION = "e458336abfed6d3da9455e35f863779c2fc357d3f216581b2b3847ff6b023c12"

# --- Negative Prompt (dapat disesuaikan jika diperlukan) ---
NEGATIVE_PROMPT = "(worst quality, low quality, normal quality, blurry, fuzzy, pixelated), (extra limbs, extra fingers, malformed hands, missing fingers, extra digit, fused fingers, too many hands, bad hands, bad anatomy), (ugly, deformed, disfigured), (text, watermark, logo, signature), (cartoon, anime, painting, illustration, sketch, 3d render), (dark skin, black hair, ugly face), out of frame, out of focus"

async def generate_image_from_prompt(prompt: str, status_msg: Message) -> bytes | None:
    """
    Menghubungi Replicate API untuk menghasilkan gambar menggunakan model Nastia.
    Proses ini asinkron: memulai, menunggu, lalu mengambil hasil.
    """
    if not REPLICATE_API_TOKEN:
        logging.error("IMAGE_HANDLER: REPLICATE_API_TOKEN environment variable tidak ditemukan!")
        return None

    headers = {
        "Authorization": f"Bearer {REPLICATE_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Payload untuk memulai prediksi
    start_payload = {
        "version": NASTIA_MODEL_VERSION,
        "input": {
            "prompt": f"NASTIA, {prompt}", # Menambahkan trigger word 'NASTIA' untuk hasil lebih baik
            "negative_prompt": NEGATIVE_PROMPT,
            "aspect_ratio": "3:4" # Menggunakan rasio potret yang umum
        }
    }

    async with httpx.AsyncClient() as client:
        try:
            # --- Langkah 1: Kirim permintaan untuk memulai pembuatan gambar ---
            await status_msg.edit_text("⏳ `Memulai permintaan ke Replicate API...`")
            start_response = await client.post(REPLICATE_API_URL, headers=headers, json=start_payload, timeout=30)
            start_response.raise_for_status()
            start_data = start_response.json()
            
            status_url = start_data.get("urls", {}).get("get")
            if not status_url:
                logging.error(f"IMAGE_HANDLER: Respons API tidak valid dari Replicate: {start_data}")
                await status_msg.edit_text("❌ **Gagal memulai permintaan.** Respons API tidak valid.")
                return None

            await status_msg.edit_text("🎨 `Permintaan diterima! Menunggu AI menyelesaikan gambar...`")

            # --- Langkah 2: Tunggu hasil dengan memeriksa status (Polling) ---
            final_output_url = None
            for attempt in range(60): # Coba selama 2 menit (60 * 2 detik)
                await asyncio.sleep(2)
                status_check_response = await client.get(status_url, headers=headers, timeout=30)
                status_check_data = status_check_response.json()
                
                status = status_check_data.get('status')
                if status == 'succeeded':
                    # Hasilnya adalah sebuah list URL, ambil URL pertama
                    final_output_url = status_check_data.get('output', [None])[0]
                    break
                elif status == 'failed':
                    error_detail = status_check_data.get('error')
                    logging.error(f"IMAGE_HANDLER: Prediksi Replicate gagal: {error_detail}")
                    await status_msg.edit_text(f"❌ **Pembuatan gambar gagal.**\nError: `{error_detail}`")
                    return None
            
            if not final_output_url:
                logging.error("IMAGE_HANDLER: Waktu tunggu habis saat mengambil gambar dari Replicate.")
                await status_msg.edit_text("❌ **Gagal mengambil gambar.**\nWaktu tunggu habis. Coba lagi nanti.")
                return None

            # --- Langkah 3: Unduh gambar dari URL hasil ---
            await status_msg.edit_text("🖼️ `Gambar selesai! Mengunduh hasil...`")
            image_response = await client.get(final_output_url, timeout=60)
            image_response.raise_for_status()
            return image_response.content

        except httpx.RequestError as e:
            logging.error(f"IMAGE_HANDLER: Gagal menghubungi Replicate API: {e}")
            await status_msg.edit_text("❌ **Gagal terhubung ke layanan gambar.** Coba lagi nanti.")
            return None
        except Exception as e:
            logging.error(f"IMAGE_HANDLER: Terjadi error tidak terduga: {e}", exc_info=True)
            await status_msg.edit_text(f"❌ **Terjadi error tidak terduga:** `{e}`")
            return None

def get_image_generation_handler():
    """Membuat dan mengembalikan fungsi handler untuk perintah .buat."""
    
    async def generate_image_command(client: Client, message: Message):
        """Handler untuk perintah .buat <prompt>."""
        try:
            # --- FIX DI SINI ---
            prompt = message.text.split(" ", 1)[1].strip()
        except IndexError:
            await message.reply_text("❌ **Format Salah.**\nGunakan: `.buat <deskripsi gambar>`")
            # Menggunakan reply_text karena message mungkin sudah tidak bisa diedit jika formatnya salah
            return

        # Menggunakan reply untuk membuat pesan status baru, bukan mengedit pesan perintah
        status_msg = await message.reply_text("⏳ `Memulai proses dengan model Nastia...`")
        
        await client.send_chat_action(message.chat.id, ChatAction.UPLOAD_PHOTO)

        # Mengirim objek 'status_msg' agar bisa diedit selama proses polling
        image_bytes = await generate_image_from_prompt(prompt, status_msg)
        
        if image_bytes:
            photo = io.BytesIO(image_bytes)
            try:
                # Menggunakan prompt asli tanpa trigger word untuk caption
                await message.reply_photo(
                    photo=photo,
                    caption=f"🖼️ **Model:** Nastia\n**Prompt:**\n`{prompt}`"
                )
                await status_msg.delete()
            except Exception as e:
                await status_msg.edit_text(f"❌ **Gagal mengirim gambar:** `{e}`")
        # Pesan error sudah ditangani dan diedit di status_msg di dalam fungsi generate_image_from_prompt

    return generate_image_command
