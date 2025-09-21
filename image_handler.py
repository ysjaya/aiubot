# image_handler.py
import os
import io
import asyncio
import logging
import httpx

from pyrogram import Client
from pyrogram.types import Message
from pyrogram.enums import ChatAction

# --- Konfigurasi Hugging Face ---
HF_API_URL = "https://api-inference.huggingface.co/models/UnfilteredAI/NSFW-gen-v2"
HF_TOKEN = os.environ.get("HF_TOKEN")

# --- Negative Prompt Sesuai Permintaan Anda ---
NEGATIVE_PROMPT = "(worst quality, low quality, normal quality, blurry, fuzzy, pixelated), (extra limbs, extra fingers, malformed hands, missing fingers, extra digit, fused fingers, too many hands, bad hands, bad anatomy), (ugly, deformed, disfigured), (text, watermark, logo, signature), (cartoon, anime, painting, illustration, sketch, 3d render), (dark skin, black hair, ugly face), out of frame, out of focus"

async def generate_image_from_prompt(prompt: str) -> bytes | None:
    """
    Menghubungi Hugging Face Serverless API untuk menghasilkan gambar.
    Menerapkan mekanisme coba lagi (retry) jika model sedang dimuat.
    """
    if not HF_TOKEN:
        logging.error("IMAGE_HANDLER: HF_TOKEN environment variable tidak ditemukan!")
        return None

    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {
        "inputs": prompt,
        "parameters": {
            "negative_prompt": NEGATIVE_PROMPT,
            "width": 768,
            "height": 1024,
            "guidance_scale": 7.5
        },
        "options": {
            "use_cache": False,
            "wait_for_model": True # Menunggu model jika sedang loading
        }
    }

    async with httpx.AsyncClient() as client:
        for attempt in range(3): # Coba hingga 3 kali
            try:
                response = await client.post(HF_API_URL, headers=headers, json=payload, timeout=120)
                
                # Jika model sedang loading (503), tunggu dan coba lagi
                if response.status_code == 503:
                    wait_time = int(response.json().get("estimated_time", 20))
                    logging.warning(f"Model sedang dimuat, menunggu {wait_time} detik sebelum mencoba lagi...")
                    await asyncio.sleep(wait_time)
                    continue
                
                response.raise_for_status() # Akan error jika status code 4xx atau 5xx
                return response.content

            except httpx.RequestError as e:
                logging.error(f"IMAGE_HANDLER: Gagal menghubungi Hugging Face API. Percobaan ke-{attempt+1}: {e}")
                await asyncio.sleep(5) # Jeda singkat sebelum coba lagi
            except Exception as e:
                logging.error(f"IMAGE_HANDLER: Terjadi error tidak terduga: {e}", exc_info=True)
                return None
    
    logging.error("IMAGE_HANDLER: Gagal menghasilkan gambar setelah beberapa kali percobaan.")
    return None

def get_image_generation_handler():
    """Membuat dan mengembalikan fungsi handler untuk perintah .buat."""
    
    async def generate_image_command(client: Client, message: Message):
        """Handler untuk perintah .buat <prompt>."""
        try:
            prompt = message.text.split(" ", 1)[1].strip()
        except IndexError:
            await message.edit_text("❌ **Format Salah.**\nGunakan: `.buat <deskripsi gambar>`")
            return

        status_msg = await message.edit_text("⏳ `Sedang memproses permintaan gambar Anda...`")
        
        await client.send_chat_action(message.chat.id, ChatAction.UPLOAD_PHOTO)

        image_bytes = await generate_image_from_prompt(prompt)
        
        if image_bytes:
            photo = io.BytesIO(image_bytes)
            try:
                await message.reply_photo(
                    photo=photo,
                    caption=f"🖼️ **Prompt:**\n`{prompt}`"
                )
                await status_msg.delete()
            except Exception as e:
                await status_msg.edit_text(f"❌ **Gagal mengirim gambar:** `{e}`")
        else:
            await status_msg.edit_text("❌ **Gagal menghasilkan gambar dari AI.**\nModel mungkin sedang sibuk atau terjadi error. Coba lagi nanti.")

    return generate_image_command
