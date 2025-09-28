import os
from cerebras.cloud.sdk import Cerebras
from sqlmodel import Session, select
from models import File, Chat

client = Cerebras(api_key=os.environ.get("CEREBRAS_API_KEY"))

def stream_cerebras(messages, model, **kwargs):
    return client.chat.completions.create(
        messages=messages, model=model, stream=True, **kwargs
    )

async def ai_chain_stream(messages, project_id, conv_id, session: Session):
    # Context = semua file terbaru project
    files = session.exec(select(File).where(File.project_id == project_id)).all()
    project_context = "\n".join([f"[{f.path}]:\n{f.content}" for f in files]) if files else ""
    # Chat history (last 10 turns)
    chats = session.exec(select(Chat).where(Chat.conversation_id == conv_id)).all()
    history = "\n".join([f"User: {c.message}\nAI: {c.ai_response}" for c in chats[-10:]]) if chats else ""
    messages = [{"role": "system", "content": project_context + "\n\n" + history}] + messages

    # Reasoning
    reasoning = ""
    for chunk in stream_cerebras(messages, "qwen-3-235b-a22b-thinking-2507", max_completion_tokens=65536, temperature=0.6, top_p=0.95):
        if chunk.choices[0].delta.content:
            reasoning += chunk.choices[0].delta.content
            yield chunk.choices[0].delta.content
    # Instruction
    instruct_input = [{"role": "system", "content": reasoning}] + messages
    instruct = ""
    for chunk in stream_cerebras(instruct_input, "qwen-3-235b-a22b-instruct-2507", max_completion_tokens=20000, temperature=0.7, top_p=0.8):
        if chunk.choices[0].delta.content:
            instruct += chunk.choices[0].delta.content
            yield chunk.choices[0].delta.content
    # Coder (optional)
    if any("code" in m.get("content", "").lower() or "kode" in m.get("content", "").lower() for m in messages):
        coder_input = [{"role": "system", "content": instruct}] + messages
        for chunk in stream_cerebras(coder_input, "qwen-3-coder-480b", max_completion_tokens=40000, temperature=0.7, top_p=0.8):
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    # Final polish
    polish_input = [{"role": "system", "content": instruct}] + messages
    for chunk in stream_cerebras(polish_input, "gpt-oss-120b", max_completion_tokens=65536, temperature=1, top_p=1, reasoning_effort="medium"):
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
