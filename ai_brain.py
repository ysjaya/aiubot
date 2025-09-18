import os
import logging
import random
from typing import Dict, List
from cerebras.cloud.sdk import Cerebras

# Inisialisasi Klien AI di sini
CEREBRAS_API_KEY = os.environ.get("CEREBRAS_API_KEY")
if not CEREBRAS_API_KEY:
    raise ValueError("AI_BRAIN: CEREBRAS_API_KEY environment variable tidak ditemukan!")

cerebras_client = Cerebras(api_key=CEREBRAS_API_KEY)

# Fungsi untuk Chat Biasa (DENGAN SYSTEM PROMPT YANG DISEMPURNAKAN)
async def get_ai_chat_response(context: List[Dict[str, str]]) -> str:
    """Menghasilkan balasan AI berdasarkan konteks percakapan."""
    if not context:
        return ""
    
    # SYSTEM PROMPT DIPERBARUI DENGAN MENAMBAHKAN ATURAN BARU (TIDAK MENGGANTI)
    system_prompt = {
        "role": "system",
        "content": """
        You are a chat assistant with the personality of a witty, knowledgeable, and down-to-earth friend. Your main goal is to chat naturally, like a real person who is fluent in modern internet culture. **Above all, your defining trait is being concise and very short. Never provide long-winded answers.**

        Follow these core rules:
        1.  **Primary Rule: Language and Style Matching.** Always detect the user's primary language and respond fluently in that same language.
        2.  **Adopt Their Vibe.** Pay close attention to the user's tone. If they are casual, mirror that style. If they are formal, be respectful but relaxed.
        3.  **Be Human-like.** Keep replies concise. Use relevant emojis. Avoid formal intros like "As an AI...".
        4.  **Be a Global Friend, Not a Local Stereotype.** Your default style should be universally modern and online.
        5.  **Get to the Point:** This is a critical rule. Always prioritize brevity. Avoid filler, repetition, and unnecessary explanations. Be as brief as possible while still being helpful.
        """
    }
    full_context = [system_prompt] + context

    try:
        stream = cerebras_client.chat.completions.create(
            messages=full_context, model="qwen-3-235b-a22b-instruct-2507", stream=True, max_completion_tokens=800, temperature=0.5, top_p=0.9
        )
        return "".join(chunk.choices[0].delta.content or "" for chunk in stream)
    except Exception as e:
        logging.error(f"AI_BRAIN (chat): Error saat menghubungi Cerebras API: {e}", exc_info=True)
        return "Duh, sorry, otak gue lagi nge-freeze bentar."

# --- FUNGSI KUTIPAN YANG JUGA SUDAH DIBUAT SINGKAT ---
async def generate_ai_quote() -> str:
    """Meminta AI untuk membuat kutipan yang sangat singkat dan padat dengan tema acak."""
    logging.info("AI_BRAIN (quote): Menghasilkan kutipan singkat menggunakan AI...")
    
    themes = ["kehidupan", "perjuangan", "kesuksesan", "kebijaksanaan", "harapan", "cinta", "persahabatan"]
    selected_theme = random.choice(themes)
    
    prompt = {
        "role": "user",
        "content": f"Buat satu kutipan yang sangat singkat, padat, dan inspiratif tentang {selected_theme} dalam Bahasa Indonesia. Maksimal 15 kata. Akhiri dengan '— AI'. Hanya berikan kutipannya saja."
    }

    try:
        response = cerebras_client.chat.completions.create(
            messages=[prompt], 
            model="qwen-3-235b-a22b-instruct-2507", 
            max_completion_tokens=60,
            temperature=0.7
        )
        quote = response.choices[0].message.content.strip()
        if quote.startswith('"') and quote.endswith('"'):
            quote = quote[1:-1]
        
        if '— AI' not in quote:
            return f'"{quote}"\n— AI'
        
        return quote
    except Exception as e:
        logging.error(f"AI_BRAIN (quote): Gagal menghasilkan kutipan: {e}", exc_info=True)
        return '"Setiap langkah kecil adalah kemajuan."\n— AI (Fallback)'
