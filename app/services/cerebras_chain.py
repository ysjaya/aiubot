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
    """Fungsi utama AI Agent dengan pencarian web otomatis dan logging."""
    print("\n--- [AI CHAIN DEBUG] ---")
    user_query = messages[-1]['content']
    print(f"Query: {user_query}")
    
    # --- Persiapan Konteks Awal ---
    files = session.exec(select(models.File).where(models.File.project_id == project_id)).all()
    project_context = "\n".join([f"Path: {f.path}\nContent:\n{f.content}" for f in files])
    chats = session.exec(select(models.Chat).where(models.Chat.conversation_id == conv_id)).all()
    history = "\n".join([f"User: {c.message}\nAI: {c.ai_response}" for c in chats])
    
    try:
        current_step = 1
        # TAHAP 1
        print(f"STEP {current_step}: Analyzing intent...")
        yield json.dumps({"status": "update", "message": f"{current_step}/6 Menganalisis permintaan..."})
        analysis_prompt = f"""Analyze the user's query: "{user_query}"
        Based on the query, chat history, and project files, determine if a web search is required to provide a comprehensive and up-to-date answer. The query may involve recent technologies, libraries, or specific error messages that are not in the context.
        Respond ONLY with a JSON object with one key: "requires_web_search" (boolean).
        - Set to true if the query asks for current events, definitions of new tech, external library documentation, or solutions to programming errors.
        - Set to false if the query is about the existing code in the project files or general knowledge.
        Chat History: {history}
        Project Files Context: {project_context[:1500]}"""
        analysis_json_str = await call_cerebras([{"role": "user", "content": analysis_prompt}], "qwen-3-235b-a22b-thinking-2507", temperature=0.0)
        print(f"-> Analysis result: {analysis_json_str}")
        current_step += 1
        
        try:
            analysis_result = json.loads(analysis_json_str)
            requires_web = analysis_result.get("requires_web_search", False)
        except (json.JSONDecodeError, AttributeError):
            requires_web = False

        # TAHAP 2 (KONDISIONAL)
        web_context = ""
        if requires_web:
            print(f"STEP {current_step}: Performing automatic web search...")
            yield json.dumps({"status": "update", "message": f"{current_step}/6 Melakukan pencarian web otomatis..."})
            query_gen_prompt = f"Based on the user's query '{user_query}', generate up to 2 concise and effective search engine queries. Respond with each query on a new line, and nothing else."
            search_queries_str = await call_cerebras([{"role": "user", "content": query_gen_prompt}], "gpt-oss-120b", temperature=0.3)
            search_queries = [q for q in search_queries_str.split('\n') if q]
            print(f"-> Generated search queries: {search_queries}")
            
            scraped_texts = []
            for query in search_queries[:2]:
                search_results = web_tools.search_web(query)
                if search_results and search_results.get("results"):
                    top_url = search_results["results"][0]['url']
                    scraped_content = web_tools.scrape_url(top_url)
                    scraped_texts.append(f"Source for '{query}':\n{scraped_content['text']}")
            web_context = "\n\n".join(scraped_texts)
            print(f"-> Web context found: {len(web_context)} characters")
        else:
            print(f"STEP {current_step}: Web search not required.")
        current_step += 1
        
        # TAHAP 3
        print(f"STEP {current_step}: Synthesizing detailed plan...")
        yield json.dumps({"status": "update", "message": f"{current_step}/6 Menyusun rencana detail..."})
        detailed_plan_prompt = f"""Synthesize all available information and create a step-by-step plan to comprehensively answer the user's query.
        USER QUERY: {user_query}
        PROJECT CONTEXT:\n{project_context}
        CHAT HISTORY:\n{history}
        WEB SEARCH RESULTS:\n{web_context if web_context else 'No web search was performed.'}
        Respond with a numbered list outlining the plan. Determine if code generation is needed."""
        detailed_plan = await call_cerebras([{"role": "user", "content": detailed_plan_prompt}], "qwen-3-235b-a22b-thinking-2507", temperature=0.4)
        print(f"-> Detailed plan generated:\n{detailed_plan}")
        current_step += 1

        # TAHAP 4
        print(f"STEP {current_step}: Generating explanation text...")
        yield json.dumps({"status": "update", "message": f"{current_step}/6 Menulis penjelasan..."})
        instruct_prompt = f"""Based on this execution plan, write the explanatory text for the user. Do NOT write any code, but mark where code should be inserted with [CODE_BLOCK].
        PLAN:\n{detailed_plan}\nCONTEXT:\nUSER QUERY: {user_query}\nPROJECT CONTEXT:\n{project_context}\nWEB SEARCH RESULTS:\n{web_context}"""
        instructional_text = await call_cerebras([{"role": "user", "content": instruct_prompt}], "qwen-3-235b-a22b-instruct-2507", temperature=0.6)
        print("-> Explanation text generated.")
        current_step += 1
        
        # TAHAP 5
        generated_code = ""
        if "code" in detailed_plan.lower() or "kode" in detailed_plan.lower() or "[CODE_BLOCK]" in instructional_text:
            print(f"STEP {current_step}: Generating code...")
            yield json.dumps({"status": "update", "message": f"{current_step}/6 Membuat kode..."})
            coder_prompt = f"""Based on the following plan and context, generate the necessary code. Format it in a single Markdown code block.
            PLAN:\n{detailed_plan}\nCONTEXT:\nUSER QUERY: {user_query}\nPROJECT CONTEXT:\n{project_context}\nWEB SEARCH RESULTS:\n{web_context}"""
            generated_code = await call_cerebras([{"role": "user", "content": coder_prompt}], "qwen-3-coder-480b", temperature=0.5)
            print("-> Code generated.")
        else:
            print(f"STEP {current_step}: Code generation not required.")
        current_step += 1
        
        # TAHAP 6
        print(f"STEP {current_step}: Assembling final response...")
        yield json.dumps({"status": "update", "message": f"{current_step}/6 Merakit jawaban akhir..."})
        final_assembly_prompt = f"""Assemble the final response. Combine the instructional text and code into a single, cohesive, well-formatted Markdown response. Replace [CODE_BLOCK] with the actual code.
        INSTRUCTIONAL TEXT:\n{instructional_text}\nCODE BLOCK:\n{generated_code}"""
        final_stream = stream_cerebras([{"role": "user", "content": final_assembly_prompt}], "gpt-oss-120b", temperature=0.7)
        
        full_response = ""
        for chunk in final_stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_response += content
                yield content
        print("--- [AI CHAIN FINISHED] ---")

    except Exception as e:
        print(f"!!!!!! [AI CHAIN ERROR]: {e} !!!!!!")
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
