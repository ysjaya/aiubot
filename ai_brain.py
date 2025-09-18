import os
import logging
import random # <-- Tambahkan import ini
from typing import Dict, List
from cerebras.cloud.sdk import Cerebras

# Inisialisasi Klien AI di sini
CEREBRAS_API_KEY = os.environ.get("CEREBRAS_API_KEY")
if not CEREBRAS_API_KEY:
    raise ValueError("AI_BRAIN: CEREBRAS_API_KEY environment variable tidak ditemukan!")

cerebras_client = Cerebras(api_key=CEREBRAS_API_KEY)

# Fungsi untuk Chat Biasa
async def get_ai_chat_response(context: List[Dict[str, str]]) -> str:
    """Menghasilkan balasan AI berdasarkan konteks percakapan."""
    if not context:
        return ""
    
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
            messages=full_context, model="qwen-3-235b-a22b-instruct-2507", stream=True, max_completion_tokens=800, temperature=0.5, top_p=0.9
        )
        return "".join(chunk.choices[0].delta.content or "" for chunk in stream)
    except Exception as e:
        logging.error(f"AI_BRAIN (chat): Error saat menghubungi Cerebras API: {e}", exc_info=True)
        return "Duh, sorry, otak gue lagi nge-freeze bentar."

# --- FUNGSI KUTIPAN DIPERBARUI DENGAN TEMA ACAK ---
async def generate_ai_quote() -> str:
    """Meminta AI untuk membuat kutipan inspiratif sebagai fallback dengan tema acak."""
    logging.info("AI_BRAIN (quote): Menghasilkan kutipan menggunakan AI...")
    
    # Daftar tema untuk membuat prompt lebih bervariasi
    themes = ["kehidupan", "perjuangan", "kesuksesan", "kebijaksanaan", "harapan", "cinta", "persahabatan"]
    selected_theme = random.choice(themes)
    
    prompt = {
        "role": "user",
        "content": f"Create a short, insightful, and original quote about {selected_theme}. The quote should be in Indonesian. End it with '— AI' as the author. Just provide the quote, nothing else."
    }

    try:
        response = cerebras_client.chat.completions.create(
            messages=[prompt], model="qwen-3-235b-a22b-instruct-2507", max_completion_tokens=1000, temperature=0.85
        )
        quote = response.choices[0].message.content.strip()
        if '"' in quote:
            quote = quote.replace('"', '')
        return quote
    except Exception as e:
        logging.error(f"AI_BRAIN (quote): Gagal menghasilkan kutipan: {e}", exc_info=True)
        return '"Kesempatan terbaik seringkali tersembunyi di dalam kesulitan terbesar."\n\n— AI (Fallback)'
