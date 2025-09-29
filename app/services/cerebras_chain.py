import os
import json
import asyncio
from cerebras.cloud.sdk import Cerebras  # <-- BARIS INI TELAH DIPERBARUI
from sqlmodel import Session, select

from app.db import models
from app.core.config import settings
from app.services import web_tools

# Inisialisasi Klien Cerebras
client = Cerebras(api_key=settings.CEREBRAS_API_KEY)

# --- Helper Functions ---

async def call_cerebras(messages, model, **kwargs):
    """Fungsi pembantu untuk memanggil AI dan mendapatkan respons lengkap (non-streaming)."""
    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            messages=messages,
            model=model,
            **kwargs
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error calling model {model}: {e}")
        return f"Error: Could not get a response from model {model}."

def stream_cerebras(messages, model, **kwargs):
    """Fungsi pembantu untuk streaming respons."""
    return client.chat.completions.create(
        messages=messages, model=model, stream=True, **kwargs
    )

# --- Logika Utama AI Agent ---

async def ai_chain_stream(messages, project_id, conv_id, session: Session):
    """Fungsi utama AI Agent dengan 7 tahap."""
    
    # --- Persiapan Konteks Awal ---
    user_query = messages[-1]['content']
    files = session.exec(select(models.File).where(models.File.project_id == project_id)).all()
    project_context = "\n".join([f"Path: {f.path}\nContent:\n{f.content}" for f in files])
    chats = session.exec(select(models.Chat).where(models.Chat.conversation_id == conv_id)).all()
    history = "\n".join([f"User: {c.message}\nAI: {c.ai_response}" for c in chats])
    
    full_context_for_db = f"--- PROJECT FILES ---\n{project_context}\n\n--- CHAT HISTORY ---\n{history}"

    try:
        # --- TAHAP 1: Analisis Intent & Perencanaan Awal (Qwen-Thinking) ---
        yield json.dumps({"status": "update", "message": "1/7 Menganalisis permintaan..."})
        plan_prompt = f"""Analyze the user's query: "{user_query}"
        Based on the query and chat history, decide the user's intent and if a web search is necessary.
        Respond ONLY with a JSON object with keys: "intent" (string), "requires_web" (boolean), "plan_summary" (string).
        
        Chat History:
        {history}"""
        
        initial_plan_json_str = await call_cerebras([{"role": "user", "content": plan_prompt}], "qwen-3-235b-a22b-thinking-2507", temperature=0.1)
        
        try:
            initial_plan = json.loads(initial_plan_json_str)
            requires_web = initial_plan.get("requires_web", False)
        except json.JSONDecodeError:
            requires_web = "code" in user_query.lower() or "error" in user_query.lower() # Fallback

        # --- TAHAP 2 & 3: Pembuatan Kueri & Eksekusi Web Scraper ---
        web_context = ""
        if requires_web:
            yield json.dumps({"status": "update", "message": "2/7 Membuat kueri pencarian..."})
            query_gen_prompt = f"Based on the user's query '{user_query}', generate up to 2 concise and effective search engine queries. Respond with each query on a new line, and nothing else."
            search_queries_str = await call_cerebras([{"role": "user", "content": query_gen_prompt}], "gpt-oss-120b", temperature=0.3)
            search_queries = [q for q in search_queries_str.split('\n') if q]
            
            yield json.dumps({"status": "update", "message": "3/7 Mencari di web..."})
            scraped_texts = []
            for query in search_queries:
                search_results = web_tools.search_web(query)
                if search_results and search_results.get("results"):
                    top_url = search_results["results"][0]['url']
                    scraped_content = web_tools.scrape_url(top_url)
                    scraped_texts.append(f"Source for '{query}':\n{scraped_content['text']}")
            web_context = "\n\n".join(scraped_texts)

        # --- TAHAP 4: Sintesis Konteks & Rencana Detail (Qwen-Thinking) ---
        yield json.dumps({"status": "update", "message": "4/7 Menyusun rencana detail..."})
        detailed_plan_prompt = f"""Synthesize all available information and create a step-by-step plan to comprehensively answer the user's query.
        
        USER QUERY: {user_query}
        PROJECT CONTEXT:\n{project_context}
        CHAT HISTORY:\n{history}
        WEB SEARCH RESULTS:\n{web_context}
        
        Respond with a numbered list outlining the plan. Determine if code generation is needed.
        """
        detailed_plan = await call_cerebras([{"role": "user", "content": detailed_plan_prompt}], "qwen-3-235b-a22b-thinking-2507", temperature=0.4)

        # --- TAHAP 5: Pembuatan Teks Penjelasan (Qwen-Instruct) ---
        yield json.dumps({"status": "update", "message": "5/7 Menulis penjelasan..."})
        instruct_prompt = f"""Based on this execution plan, write the explanatory text for the user. Do NOT write any code, but mark where code should be inserted with [CODE_BLOCK].
        
        PLAN:
        {detailed_plan}
        
        CONTEXT:
        USER QUERY: {user_query}
        PROJECT CONTEXT:\n{project_context}
        WEB SEARCH RESULTS:\n{web_context}
        """
        instructional_text = await call_cerebras([{"role": "user", "content": instruct_prompt}], "qwen-3-235b-a22b-instruct-2507", temperature=0.6)

        # --- TAHAP 6: Pembuatan Kode (Qwen-Coder) ---
        generated_code = ""
        if "code" in detailed_plan.lower() or "kode" in detailed_plan.lower():
            yield json.dumps({"status": "update", "message": "6/7 Membuat kode..."})
            coder_prompt = f"""Based on the following plan and context, generate the necessary code. Format it in a single Markdown code block.
            
            PLAN:
            {detailed_plan}

            CONTEXT:
            USER QUERY: {user_query}
            PROJECT CONTEXT:\n{project_context}
            WEB SEARCH RESULTS:\n{web_context}
            """
            generated_code = await call_cerebras([{"role": "user", "content": coder_prompt}], "qwen-3-coder-480b", temperature=0.5)

        # --- TAHAP 7: Perakitan & Pemolesan Akhir (GPT) - Streaming ---
        yield json.dumps({"status": "update", "message": "7/7 Merakit jawaban akhir..."})
        final_assembly_prompt = f"""Assemble the final response for the user.
        Combine the instructional text and the code block into a single, cohesive, well-formatted Markdown response.
        Replace the [CODE_BLOCK] placeholder in the text with the actual code.
        
        INSTRUCTIONAL TEXT:
        {instructional_text}
        
        CODE BLOCK:
        {generated_code}
        """
        
        final_stream = stream_cerebras([{"role": "user", "content": final_assembly_prompt}], "gpt-oss-120b", temperature=0.7)
        
        full_response = ""
        for chunk in final_stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_response += content
                yield content

    except Exception as e:
        full_response = f"An unexpected error occurred in the AI chain: {e}"
        yield full_response

    # --- Selesai & Simpan ke DB ---
    yield json.dumps({"status": "done"})

    if user_query and full_response:
        db_chat = models.Chat(
            conversation_id=conv_id,
            user="user",
            message=user_query,
            ai_response=full_response
        )
        session.add(db_chat)
        session.commit()
