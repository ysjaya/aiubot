import os
import json
import asyncio
import trafilatura

# Impor kedua pustaka klien
from cerebras.cloud.sdk import Cerebras
from openai import OpenAI
from sqlmodel import Session, select

from app.db import models
from app.core.config import settings
from app.services import web_tools

# --- Inisialisasi KEDUA Klien ---
cerebras_client = Cerebras(api_key=settings.CEREBRAS_API_KEY)
nvidia_client = OpenAI(
  base_url = "https://integrate.api.nvidia.com/v1",
  api_key = settings.NVIDIA_API_KEY
)

# --- Definisi Prompt untuk Setiap Tahap ---
PROMPT_OUTLINE = "Buat outline jawaban yang sangat terstruktur dan komprehensif untuk pertanyaan berikut. Sertakan bagian untuk analisis masalah, langkah-langkah solusi, contoh kode jika relevan, dan daftar referensi.\n\nPertanyaan: {QUESTION}"
PROMPT_RAG_NVIDIA = "Berdasarkan potongan informasi dari web di bawah ini, berikan jawaban yang komprehensif untuk pertanyaan pengguna. Jawab dalam Bahasa Indonesia format Markdown.\n\nPPERTANYAAN PENGGUNA:\n{QUESTION}\n\nSNIPPETS DARI WEB:\n{SNIPPETS}"
PROMPT_CODE = "Berdasarkan langkah-langkah dalam outline ini, tulis kode {LANGUAGE} yang bersih, efisien, dan memiliki komentar yang jelas untuk mengimplementasikan solusi yang didiskusikan.\n\nOUTLINE RELEVAN:\n{STEP}"
PROMPT_CRITIQUE = "Anda adalah seorang editor teknis senior. Tinjau draf jawaban berikut. Berikan kritik yang membangun dan perbaiki langsung di dalam teks. Fokus pada: kelengkapan, kejelasan bahasa, akurasi teknis, dan typo. Berikan hanya versi revisi final dari teks tersebut, tanpa komentar tambahan.\n\n DRAF AWAL:\n{DRAFT}"
PROMPT_FINALIZE = "Anda adalah AI Aggregator. Gabungkan teks final yang sudah dipoles dengan blok kode yang relevan menjadi satu dokumen Markdown yang kohesif. Susun dengan baik menggunakan judul, sub-judul, danakhiri dengan daftar referensi dari URL yang ada. Jika tidak ada kode, cukup format teksnya saja.\n\nTEKS YANG SUDAH DIPOLES:\n{DRAFT}\n\nBLOK KODE:\n{CODE}"


# --- Fungsi Helper (Dibuat spesifik per klien) ---
async def call_cerebras(messages, model, **kwargs):
    """Fungsi pembantu non-streaming untuk Cerebras."""
    try:
        response = await asyncio.to_thread(
            cerebras_client.chat.completions.create, messages=messages, model=model, **kwargs
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"[CEREBRAS LOG] Error memanggil model {model}: {e}")
        return f"Error pada model Cerebras {model}."

async def call_nvidia(messages, model, **kwargs):
    """Fungsi pembantu non-streaming untuk NVIDIA."""
    try:
        completion = await asyncio.to_thread(
            nvidia_client.chat.completions.create, model=model, messages=messages, **kwargs
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"[NVIDIA LOG] Error memanggil model {model}: {e}")
        return f"Error pada model NVIDIA {model}."

def stream_cerebras(messages, model, **kwargs):
    """Fungsi pembantu streaming untuk Cerebras."""
    return cerebras_client.chat.completions.create(
        messages=messages, model=model, stream=True, **kwargs
    )

async def retrieve_web_context(query: str):
    """
    Tahap 1 yang disederhanakan: Hanya mencari dan mengikis teks mentah dari web.
    """
    print("\n--- [AI CHAIN LOG] TAHAP 1: Memulai Scraper Web ---")
    search_results = web_tools.search_web(query, num_results=5)
    urls = [res['url'] for res in search_results.get("results", [])]
    if not urls:
        print("[AI CHAIN LOG] -> Tidak ada URL yang ditemukan.")
        return ""

    print(f"[AI CHAIN LOG] -> Ditemukan {len(urls)} URL.")
    
    all_text = []
    for url in urls:
        try:
            content = web_tools.scrape_url(url)
            if content and content['text']:
                all_text.append(f"Source: {url}\n\n{content['text']}")
        except Exception as e:
            print(f"[AI CHAIN LOG] -> Gagal scrape URL {url}: {e}")
    
    print(f"[AI CHAIN LOG] -> Berhasil mengambil konten dari {len(all_text)} URL.")
    return "\n\n---\n\n".join(all_text)


async def ai_chain_stream(messages, project_id, conv_id, session: Session):
    """Logika AI Chain Hibrida (Cerebras + NVIDIA)."""
    user_query = messages[-1]['content']
    print(f"\n[AI CHAIN LOG] Menerima query baru: {user_query}")
    
    try:
        # TAHAP 1: Scraper Web (tanpa embedding)
        yield json.dumps({"status": "update", "message": "1/7 Mengambil info web..."})
        web_snippets = await retrieve_web_context(user_query)

        # TAHAP 2: Thinking (Outline) - MENGGUNAKAN CEREBRAS
        yield json.dumps({"status": "update", "message": "2/7 Membuat outline (Cerebras)..."})
        print("[AI CHAIN LOG] TAHAP 2: Membuat outline...")
        outline_prompt = PROMPT_OUTLINE.format(QUESTION=user_query)
        outline = await call_cerebras([{"role": "user", "content": outline_prompt}], "qwen-3-235b-a22b-thinking-2507")
        print(f"[AI CHAIN LOG] -> Outline dibuat:\n{outline[:200]}...")

        # TAHAP 3: Retrieval-Augmented Generation - MENGGUNAKAN NVIDIA
        yield json.dumps({"status": "update", "message": "3/7 Membuat draf (NVIDIA)..."})
        print("[AI CHAIN LOG] TAHAP 3: Membuat draf RAG...")
        rag_prompt = PROMPT_RAG_NVIDIA.format(QUESTION=user_query, SNIPPETS=web_snippets)
        draft_answer = await call_nvidia([{"role": "user", "content": rag_prompt}], "nvidia/nemotron-mini-4b-instruct")
        print("[AI CHAIN LOG] -> Draf jawaban RAG dibuat.")

        # TAHAP 4: Code Generation (Opsional) - MENGGUNAKAN CEREBRAS
        generated_code = ""
        if "kode" in outline.lower() or "code" in outline.lower():
            yield json.dumps({"status": "update", "message": "4/7 Membuat kode (Cerebras)..."})
            print("[AI CHAIN LOG] TAHAP 4: Membuat kode...")
            code_prompt = PROMPT_CODE.format(LANGUAGE="Python/JavaScript", STEP=outline)
            generated_code = await call_cerebras([{"role": "user", "content": code_prompt}], "qwen-3-coder-480b")
            print("[AI CHAIN LOG] -> Kode dibuat.")
        else:
            print("[AI CHAIN LOG] TAHAP 4: Pembuatan kode dilewati.")


        # TAHAP 5: Self-Critique & Refinement - MENGGUNAKAN CEREBRAS
        yield json.dumps({"status": "update", "message": "5/7 Melakukan self-critique (Cerebras)..."})
        print("[AI CHAIN LOG] TAHAP 5: Melakukan self-critique...")
        critique_prompt = PROMPT_CRITIQUE.format(DRAFT=draft_answer)
        # [PERUBAHAN] Menggunakan model qwen-instruct sesuai permintaan
        refined_answer = await call_cerebras([{"role": "user", "content": critique_prompt}], "qwen-3-235b-a22b-instruct-2507")
        print("[AI CHAIN LOG] -> Draf telah disempurnakan.")

        # TAHAP 6: Aggregator / Finalizer - MENGGUNAKAN CEREBRAS
        yield json.dumps({"status": "update", "message": "6/7 Menyusun jawaban final (Cerebras)..."})
        print("[AI CHAIN LOG] TAHAP 6: Menyusun jawaban final...")
        finalize_prompt = PROMPT_FINALIZE.format(DRAFT=refined_answer, CODE=generated_code)
        
        # [PERUBAHAN] Menggunakan model llama-4-maverick sesuai permintaan
        final_stream = stream_cerebras([{"role": "user", "content": finalize_prompt}], "llama-4-maverick-17b-128e-instruct")
        
        full_response = ""
        for chunk in final_stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_response += content
                yield content

    except Exception as e:
        print(f"[AI CHAIN LOG] !!! Terjadi error pada AI chain: {e} !!!")
        yield json.dumps({"status": "error", "message": f"Terjadi kesalahan sistem: {e}"})
        return

    # Selesai & Simpan ke DB
    yield json.dumps({"status": "done"})
    print("[AI CHAIN LOG] Proses selesai, menyimpan ke DB.")

    if user_query and full_response:
        db_chat = models.Chat(
            conversation_id=conv_id, user="user", message=user_query, ai_response=full_response
        )
        session.add(db_chat)
        session.commit()
