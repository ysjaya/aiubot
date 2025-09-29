import os
import json
import asyncio
from cerebras.cloud.sdk import Cerebras
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
    """Fungsi utama AI Agent dengan pencarian web otomatis."""
    
    # --- Persiapan Konteks Awal ---
    user_query = messages[-1]['content']
    files = session.exec(select(models.File).where(models.File.project_id == project_id)).all()
    project_context = "\n".join([f"Path: {f.path}\nContent:\n{f.content}" for f in files])
    chats = session.exec(select(models.Chat).where(models.Chat.conversation_id == conv_id)).all()
    history = "\n".join([f"User: {c.message}\nAI: {c.ai_response}" for c in chats])
    
    full_context_for_db = f"--- PROJECT FILES ---\n{project_context}\n\n--- CHAT HISTORY ---\n{history}"

    try:
        # TAHAP 1: Analisis Intent & Kebutuhan Pencarian Web
        yield json.dumps({"status": "update", "message": "1/6 Menganalisis permintaan..."})
        
        analysis_prompt = f"""Analyze the user's query: "{user_query}"
        Based on the query, chat history, and project files, determine if a web search is required to provide a comprehensive and up-to-date answer. The query may involve recent technologies, libraries, or specific error messages that are not in the context.

        Respond ONLY with a JSON object with one key: "requires_web_search" (boolean).

        - Set to true if the query asks for current events, definitions of new tech, external library documentation, or solutions to programming errors.
        - Set to false if the query is about the existing code in the project files or general knowledge.

        Chat History:
        {history}
        Project Files Context:
        {project_context[:2000]}"""

        analysis_json_str = await call_cerebras([{"role": "user", "content": analysis_prompt}], "qwen-3-235b-a22b-thinking-2507", temperature=0.0)
        
        try:
            analysis_result = json.loads(analysis_json_str)
            requires_web = analysis_result.get("requires_web_search", False)
        except (json.JSONDecodeError, AttributeError):
            requires_web = False # Fallback jika JSON tidak valid

        # TAHAP 2: (KONDISIONAL) Eksekusi Pencarian Web
        web_context = ""
        current_step = 2
        if requires_web:
            yield json.dumps({"status": "update", "message": "2/6 Melakukan pencarian web otomatis..."})
            query_gen_prompt = f"Based on the user's query '{user_query}', generate up to 2 concise and effective search engine queries. Respond with each query on a new line, and nothing else."
            search_queries_str = await call_cerebras([{"role": "user", "content": query_gen_prompt}], "gpt-oss-120b", temperature=0.3)
            search_queries = [q for q in search_queries_str.split('\n') if q]
            
            scraped_texts = []
            for query in search_queries[:2]: # Batasi 2 kueri
                search_results = web_tools.search_web(query)
                if search_results and search_results.get("results"):
                    top_url = search_results["results"][0]['url']
                    scraped_content = web_tools.scrape_url(top_url)
                    scraped_texts.append(f"Source for '{query}':\n{scraped_content['text']}")
            web_context = "\n\n".join(scraped_texts)
            current_step += 1

        # TAHAP 3: Sintesis Konteks & Rencana Detail
        yield json.dumps({"status": "update", "message": f"{current_step}/6 Menyusun rencana detail..."})
        detailed_plan_prompt = f"""Synthesize all available information and create a step-by-step plan to comprehensively answer the user's query.
        
        USER QUERY: {user_query}
        PROJECT CONTEXT:\n{project_context}
        CHAT HISTORY:\n{history}
        WEB SEARCH RESULTS:\n{web_context if web_context else 'No web search was performed.'}
        
        Respond with a numbered list outlining the plan. Determine if code generation is needed.
        """
        detailed_plan = await call_cerebras([{"role": "user", "content": detailed_plan_prompt}], "qwen-3-235b-a22b-thinking-2507", temperature=0.4)
        current_step += 1

        # TAHAP 4: Pembuatan Teks Penjelasan
        yield json.dumps({"status": "update", "message": f"{current_step}/6 Menulis penjelasan..."})
        instruct_prompt = f"""Based on this execution plan, write the explanatory text for the user. Do NOT write any code, but mark where code should be inserted with [CODE_BLOCK].
        
        PLAN:
        {detailed_plan}
        
        CONTEXT:
        USER QUERY: {user_query}
        PROJECT CONTEXT:\n{project_context}
        WEB SEARCH RESULTS:\n{web_context}
        """
        instructional_text = await call_cerebras([{"role": "user", "content": instruct_prompt}], "qwen-3-235b-a22b-instruct-2507", temperature=0.6)
        current_step += 1

        # TAHAP 5: Pembuatan Kode
        generated_code = ""
        if "code" in detailed_plan.lower() or "kode" in detailed_plan.lower() or "[CODE_BLOCK]" in instructional_text:
            yield json.dumps({"status": "update", "message": f"{current_step}/6 Membuat kode..."})
            coder_prompt = f"""Based on the following plan and context, generate the necessary code. Format it in a single Markdown code block.
            
            PLAN:
            {detailed_plan}

            CONTEXT:
            USER QUERY: {user_query}
            PROJECT CONTEXT:\n{project_context}
            WEB SEARCH RESULTS:\n{web_context}
            """
            generated_code = await call_cerebras([{"role": "user", "content": coder_prompt}], "qwen-3-coder-480b", temperature=0.5)
            current_step += 1
        else:
             current_step += 1 # Loncat ke langkah terakhir jika tidak ada kode

        # TAHAP 6: Perakitan & Pemolesan Akhir
        yield json.dumps({"status": "update", "message": f"{current_step}/6 Merakit jawaban akhir..."})
        final_assembly_prompt = f"""Assemble the final response for the user.
        Combine the instructional text and the code block into a single, cohesive, well-formatted Markdown response.
        Replace the [CODE_BLOCK] placeholder in the text with the actual code. If there's no code, just present the instructional text.
        
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
        yield json.dumps({"status": "error", "message": full_response})

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
