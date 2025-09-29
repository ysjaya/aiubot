import os
import json
import asyncio
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
import trafilatura

from cerebras.cloud.sdk import Cerebras
from sqlmodel import Session, select

from app.db import models
from app.core.config import settings
from app.services import web_tools

# --- Inisialisasi Klien & Model ---
client = Cerebras(api_key=settings.CEREBRAS_API_KEY)
# Muat model embedding sekali untuk efisiensi
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

# --- Definisi Prompt untuk Setiap Tahap ---
PROMPT_OUTLINE = "Buat outline jawaban yang sangat terstruktur dan komprehensif untuk pertanyaan berikut. Sertakan bagian untuk analisis masalah, langkah-langkah solusi, contoh kode jika relevan, dan daftar referensi.\n\nPertanyaan: {QUESTION}"
PROMPT_RAG = "Anda adalah seorang penulis teknis ahli. Berdasarkan outline dan potongan informasi dari web di bawah ini, tulis draf jawaban yang lengkap dan mendalam dalam format Markdown Bahasa Indonesia. Pastikan untuk mengutip URL sumber jika memungkinkan.\n\nOUTLINE:\n{OUTLINE}\n\nSNIPPETS DARI WEB:\n{SNIPPETS}"
PROMPT_CODE = "Berdasarkan langkah-langkah dalam outline ini, tulis kode {LANGUAGE} yang bersih, efisien, dan memiliki komentar yang jelas untuk mengimplementasikan solusi yang didiskusikan.\n\nOUTLINE RELEVAN:\n{STEP}"
PROMPT_CRITIQUE = "Anda adalah seorang editor teknis senior. Tinjau draf jawaban berikut. Berikan kritik yang membangun dan perbaiki langsung di dalam teks. Fokus pada: kelengkapan, kejelasan bahasa, akurasi teknis, dan typo. Berikan hanya versi revisi final dari teks tersebut, tanpa komentar tambahan.\n\n DRAF AWAL:\n{DRAFT}"
PROMPT_FINALIZE = "Anda adalah AI Aggregator. Gabungkan teks final yang sudah dipoles dengan blok kode yang relevan menjadi satu dokumen Markdown yang kohesif. Susun dengan baik menggunakan judul, sub-judul, danakhiri dengan daftar referensi dari URL yang ada. Jika tidak ada kode, cukup format teksnya saja.\n\nTEKS YANG SUDAH DIPOLES:\n{DRAFT}\n\nBLOK KODE:\n{CODE}"


# --- Fungsi Helper ---
async def call_cerebras(messages, model, **kwargs):
    """Fungsi pembantu non-streaming."""
    try:
        response = await asyncio.to_thread(
            client.chat.completions.create, messages=messages, model=model, **kwargs
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error memanggil model {model}: {e}")
        return f"Error: Tidak bisa mendapatkan respons dari model {model}."

def stream_cerebras(messages, model, **kwargs):
    """Fungsi pembantu streaming."""
    return client.chat.completions.create(
        messages=messages, model=model, stream=True, **kwargs
    )

async def setup_rag_retriever(query: str):
    """
    Tahap 1: Scraper & RAG. Mengambil URL, membersihkan teks,
    membuat embedding, dan membangun vector store FAISS in-memory.
    """
    print("TAHAP 1: Memulai Scraper & Persiapan RAG")
    # Ambil 5-8 URL
    search_results = web_tools.search_web(query, num_results=8)
    urls = [res['url'] for res in search_results.get("results", [])]
    if not urls:
        print("-> Tidak ada URL yang ditemukan.")
        return None

    print(f"-> Ditemukan {len(urls)} URL.")
    
    # Scrape dan bersihkan teks
    docs = []
    for url in urls:
        downloaded = trafilatura.fetch_url(url)
        text = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
        if text:
            docs.append({"text": text, "source": url})
    
    if not docs:
        print("-> Gagal mengambil konten dari URL.")
        return None
        
    print(f"-> Berhasil mengambil konten dari {len(docs)} URL.")

    # Buat embedding
    texts = [doc["text"] for doc in docs]
    embeddings = embedding_model.encode(texts, convert_to_tensor=False)
    
    # Bangun vector store FAISS
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(np.array(embeddings).astype('float32'))
    
    print("-> Vector store FAISS berhasil dibuat.")
    return {"index": index, "docs": docs}


async def ai_chain_stream(messages, project_id, conv_id, session: Session):
    """Logika AI Chain 7 Tahap yang Baru."""
    user_query = messages[-1]['content']
    
    try:
        # TAHAP 1: Scraper & RAG
        yield json.dumps({"status": "update", "message": "1/7 Menyiapkan RAG..."})
        rag_data = await setup_rag_retriever(user_query)
        if not rag_data:
            # Fallback jika RAG gagal
            yield json.dumps({"status": "error", "message": "Gagal mengambil data dari web. Mencoba menjawab tanpa RAG."})
            rag_data = {"index": None, "docs": []}

        # TAHAP 2: Thinking (Outline)
        yield json.dumps({"status": "update", "message": "2/7 Membuat outline..."})
        outline_prompt = PROMPT_OUTLINE.format(QUESTION=user_query)
        outline = await call_cerebras([{"role": "user", "content": outline_prompt}], "qwen-3-235b-a22b-thinking-2507")
        print(f"-> Outline dibuat:\n{outline}")

        # TAHAP 3: Retrieval-Augmented Generation
        yield json.dumps({"status": "update", "message": "3/7 Mengambil data & membuat draf..."})
        retrieved_snippets = "Tidak ada informasi tambahan dari web."
        if rag_data["index"] is not None:
            # Query outline ke vector store
            query_embedding = embedding_model.encode([outline], convert_to_tensor=False)
            _, I = rag_data["index"].search(np.array(query_embedding).astype('float32'), k=3)
            retrieved_docs = [rag_data["docs"][i] for i in I[0]]
            retrieved_snippets = "\n\n---\n\n".join([f"Source: {doc['source']}\n\n{doc['text'][:1500]}" for doc in retrieved_docs])
        
        rag_prompt = PROMPT_RAG.format(OUTLINE=outline, SNIPPETS=retrieved_snippets)
        draft_answer = await call_cerebras([{"role": "user", "content": rag_prompt}], "gpt-oss-120b")
        print("-> Draf jawaban RAG dibuat.")

        # TAHAP 4: Code Generation (Opsional)
        generated_code = ""
        if "kode" in outline.lower() or "code" in outline.lower():
            yield json.dumps({"status": "update", "message": "4/7 Membuat kode..."})
            code_prompt = PROMPT_CODE.format(LANGUAGE="Python/JavaScript", STEP=outline)
            generated_code = await call_cerebras([{"role": "user", "content": code_prompt}], "qwen-3-coder-480b")
            print("-> Kode dibuat.")

        # TAHAP 5: Self-Critique & Refinement
        yield json.dumps({"status": "update", "message": "5/7 Melakukan self-critique..."})
        critique_prompt = PROMPT_CRITIQUE.format(DRAFT=draft_answer)
        refined_answer = await call_cerebras([{"role": "user", "content": critique_prompt}], "llama-3.3-70b-instruct")
        print("-> Draf telah disempurnakan.")
        # Catatan: Loop Quality-Control (Tahap 7) disederhanakan menjadi satu kali proses critique
        # untuk stabilitas dan latensi yang dapat diprediksi.

        # TAHAP 6: Aggregator / Finalizer
        yield json.dumps({"status": "update", "message": "6/7 Menyusun jawaban final..."})
        finalize_prompt = PROMPT_FINALIZE.format(DRAFT=refined_answer, CODE=generated_code)
        
        final_stream = stream_cerebras([{"role": "user", "content": finalize_prompt}], "llama-4-maverick")
        full_response = ""
        for chunk in final_stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_response += content
                yield content

    except Exception as e:
        print(f"Terjadi error pada AI chain: {e}")
        yield json.dumps({"status": "error", "message": f"Terjadi kesalahan sistem: {e}"})

    # Selesai & Simpan ke DB
    yield json.dumps({"status": "done"})

    if user_query and full_response:
        db_chat = models.Chat(
            conversation_id=conv_id, user="user", message=user_query, ai_response=full_response
        )
        session.add(db_chat)
        session.commit()
