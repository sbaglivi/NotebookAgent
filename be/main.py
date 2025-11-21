import os
import json
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from . import mytypes
import asyncio
from queue import Empty
from jupyter_client import KernelManager, KernelClient
from itertools import groupby
from datetime import datetime
from uuid import uuid4
from pathlib import Path
from tempfile import NamedTemporaryFile
import shutil
import threading
import subprocess
from . import lsp

active_lsp = {}
with open("/usr/share/dict/words") as f:
    words = [l.strip() for l in f.readlines()]

# model = "moonshotai/kimi-k2-thinking"
model = "minimax/minimax-m2"
router_key = os.getenv("OPENROUTER_KEY")
print("ho")
if router_key is None:
    print('hi')
    raise ValueError("empty router key")
# "openai/gpt-4o"

origins = ["http://localhost:5173", "ws://localhost:5173"]
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True, allow_methods=["*"],
    allow_headers=["*"]
)

async def ack(tmp_id: str, msg_id: int, queue: asyncio.Queue):
    content = {"result": "created", "tmpID": tmp_id, "id": msg_id}
    await queue.put(content)

async def generate(query: list[dict[str,str]], msg_id: int, queue: asyncio.Queue):
    fname = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".json"
    response = ""
    async for part in invoke_streaming_llm(query):
        response += part
        await queue.put({"id": msg_id, "result": "generation success", "content": part})
    query.append({"role": "assistant", "content": response})
    with open("llm_queries/"+fname, "w") as f:
        json.dump(query, f)
    
    # for _ in range(6):
    #     n = secrets.randbelow(8) + 4
    #     phrase = " ".join(secrets.choice(words) for _ in range(n)) + ". "
    #     await queue.put({"id": msg_id, "result": "generation success", "content": phrase})
    #     await asyncio.sleep(.3)

@app.get("/recent")
async def get_recent_chats():
    chat_dir = Path("chats")
    # atime for accessed, mtime modified
    all_chats = [(f.stat().st_mtime, f) for f in chat_dir.iterdir() if f.is_file()]
    all_chats.sort(reverse=True)
    return [c[1].stem for c in all_chats[:5]]

def parse_msg(msg: dict):
    msg_type = msg['header']['msg_type']
    content = msg.get("content", {})

    if msg_type == "error":
        _ename, _evalue = content["ename"], content["evalue"]
        return {
            "type": "error", 
            "content": "\n".join(content['traceback'])
        }

    if msg_type == "status":
        # idle / busy
        return {
            "type": "status",
            "content": content["execution_state"]
        }

    if msg_type == "stream":
        # {name: stdout, text: output}
        return {
            "type": msg_type,
            "content": content
        }

    if msg_type in ["execute_result", "display_data"]:
        content = content["data"]
        handled = ["image/png", "text/html", "text/plain"]
        out = {"type": "data"}
        for htype in handled:
            if htype in content:
                out["content"] = {"type": htype, "data": content[htype]}
                return out
        print(f"error, none of handled keys in data: {list(content.keys())}")

    return None

def execute(code: str, id: str, kc: KernelClient, queue: asyncio.Queue, loop: asyncio.EventLoop):
    _msg_id = kc.execute(code)
    while True:
        try:
            msg = kc.get_iopub_msg(timeout=1)
        except (TimeoutError, Empty):
            continue

        out = parse_msg(msg)
        if out is None:
            continue

        print(out)
        out.update({"id": id, "result": "code execution"})
        asyncio.run_coroutine_threadsafe(queue.put(out), loop)
        if out["type"] == "status" and out["content"] == "idle":
            break

def prepare_query(convs: list[mytypes.Message], query: str) -> list[dict[str,str]]:
    PROMPT = """
    Hello, your job is to assist users that are working on a jupyter-notebook like application.
    Be helpful, clear and help them solve their problem while learning new skills.
    Use markdown in your response to improve readibility. Do not produce images.
    Notebook context:
    """
    groups = groupby(convs, lambda m: m.type == "llm")
    turns = [
        {
            "role": "system",
            "content": PROMPT.strip()
        }
    ]
    for is_llm, group in groups:
        if is_llm:
            content = "\n".join(msg.content for msg in group)
            turns.append({"role": "assistant", "content": content})
            continue

        content = []
        for msg in group:
            if msg.type == "code":
                content.append({"code": msg.content, "outputs": msg.output})
            elif msg.type == "text":
                content.append(msg.content)
            else: # query
                content.append("question: " + msg.content)
        turns.append({"role": "user", "content": json.dumps(content)})
    
    turns.append({"role": "user", "content": query})
    return turns

@app.post("/chats")
async def create_chat():
    chat_id = str(uuid4())
    chat_path = Path(f"chats/{chat_id}.json")
    with chat_path.open("w") as f:
        json.dump({"messages": []}, f)
    return {"id": chat_id, "messages": []}

def get_chat(chat_id: str):
    chat_path = Path(f"chats/{chat_id}.json")
    if not chat_path.is_file():
        return None
    
    with chat_path.open() as f:
        chat = json.load(f)

    chat["id"] = chat_id
    return chat
    
@app.get("/chats/{chat_id}")
async def get_chat_route(chat_id: str):
    chat = get_chat(chat_id)
    if chat is None:
        raise HTTPException(404)
    
    return chat

def write_chat(chat_id: str, messages: list[mytypes.Message]):
    chat_path = Path(f"chats/{chat_id}.json")
    with NamedTemporaryFile("w", delete_on_close=False) as f:
        json.dump({"messages": [m.model_dump() for m in messages]}, f, indent=2, ensure_ascii=False)
        f.close()
        shutil.copy2(f.name, chat_path)        

def to_messages(msgs: list[dict]) -> list[mytypes.Message]:
    result = []
    for msg in msgs:
        cls = mytypes.CodeMessage if msg["type"] == "code" else mytypes.Message
        result.append(cls.model_validate(msg))
    return result

def lsp_read(queue: asyncio.Queue, stdout):
    for msg in lsp.reader(stdout):
        # do something
        def tmp(msg):
            return ""
        
        a = tmp(msg)
        # otherwise I'd need run_coroutine_threadsafe for queue.put
        asyncio.get_event_loop().call_soon_threadsafe(queue.put_nowait(a))


@app.websocket("/ws/{chat_id}/lsp")
async def websocket_ls(ws: WebSocket, chat_id: str):
    await ws.accept()
    __file__
    if chat_id not in active_lsp:
        proc = lsp.create_proc()
        req = lsp.OpenRequest.create(chat_id, "")
        lsp.send_msg(proc, req.model_dump())
        q = asyncio.Queue()
        active_lsp[chat_id] = [1, proc, q]
    else:
        count, proc, q = active_lsp[chat_id]
        active_lsp[chat_id] = [count+1, proc, q]
    t = threading.Thread(target=lsp_read, args=(q, proc.stdout), daemon=True)
    t.start()
    try:
        while True:
            done, _ = await asyncio.wait(
                {
                    asyncio.create_task(ws.receive_text()),  # from Monaco
                    asyncio.create_task(q.get()),        # from LS
                },
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in done:
                msg = task.result()

                if isinstance(msg, str):  
                    # from websocket → send to LS
                    # first parse it / validate it?
                    # msg = mytypes.MessageReq.model_validate_json(json_str)
                    # lsp.CompletionRequest.create()
                    new_text = ""
                    version = 1 # not sure if I can just ignore it for now 
                    change_req = lsp.ChangeRequest.create(chat_id, new_text, version)
                    lsp.send_msg(change_req.model_dump())

                else:
                    print(msg)
                    # from LS → send to fe, which will parse what kind of thing it is and call something on monaco appropriately
                    # await ws.send_json(msg)
    finally:
        count, proc, q = active_lsp[chat_id]
        if count == 1:
            proc.kill()
            del active_lsp[chat_id]
        else:
            active_lsp[chat_id] = [count-1, proc, q]


@app.websocket("/ws/{chat_id}")
async def websocket_endpoint(ws: WebSocket, chat_id: str):
    chat = get_chat(chat_id)
    if chat is None:
        return

    conversation: list[mytypes.Message] = to_messages(chat["messages"])

    await ws.accept()
    loop = asyncio.get_running_loop()
    queue = asyncio.Queue()
    count = 0
    km = KernelManager()
    km.start_kernel()
    kc = km.client()
    kc.start_channels()
    kc.wait_for_ready()
    async def save_chat():
        while True:
            await asyncio.sleep(10)
            write_chat(chat_id, conversation)

    async def read_ws():
        nonlocal count
        try:
            while True:
                json_str = await ws.receive_text()
                msg = mytypes.MessageReq.model_validate_json(json_str)
                if msg.type == mytypes.MessageType.LLM:
                    print("ERROR: received msg with type LLM")
                    continue

                old_id = msg.id
                response_id = msg.response_id
                msg = mytypes.Message.from_message_req(msg, count)
                count += 1
                if msg.type == mytypes.MessageType.CODE:
                    msg = mytypes.CodeMessage.from_message(msg)

                conversation.append(msg)
                if msg.type == mytypes.MessageType.QUERY:
                    # with open("tmp.json", "w") as f:
                    #     json.dump(
                    #         [m.model_dump() for m in conversation], 
                    #         f,
                    #         indent=2,
                    #         ensure_ascii=False
                    #     )

                    assert isinstance(response_id, str) and response_id
                    resp_id = count
                    count += 1
                    await ack(response_id, resp_id, queue)
                    asyncio.create_task(generate(prepare_query(conversation[:-1], msg.content), resp_id, queue))
                elif msg.type == mytypes.MessageType.CODE:
                    asyncio.create_task(
                        asyncio.to_thread(execute, msg.content, msg.id, kc, queue, loop)
                    )
                        
                await ack(old_id, msg.id, queue)
        except WebSocketDisconnect:
            kc.stop_channels()
            km.shutdown_kernel(now=True)

    async def write_ws():
        try:
            while True:
                msg = await queue.get()
                if msg.get("result", "") == "code execution":
                    to_update = [c for c in conversation if c.id == msg["id"]]
                    if len(to_update) != 1:
                        print("ERROR: len of items to update for code ex is not 1")
                    else:
                        to_update = to_update[0]
                        if msg["type"] == "status": 
                            if msg["content"] == "busy":
                                to_update.execution_status = "started"
                            else:
                                to_update.execution_status = "done"
                        else:
                            to_update.output.append({"type": msg["type"], "content": msg["content"]})
                await ws.send_json(msg)
        except WebSocketDisconnect:
            kc.stop_channels()
            km.shutdown_kernel(now=True)

    reader = asyncio.create_task(read_ws())
    writer = asyncio.create_task(write_ws())
    saver = asyncio.create_task(save_chat())

    done, pending = await asyncio.wait(
        [reader, writer, saver],
        return_when=asyncio.FIRST_COMPLETED,
    )

prompt = """
Hi, the other day something that looked very similar to a jupyter notebook, but with AI integration: any block could optionally be an 
LLM invocation which, besides the immediate prompt, would contain as context the whole notebook content up to that point. Do you think
we can build something similar?
"""
async def invoke_streaming_llm(messages: list[dict[str,str]]):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
    "Authorization": f"Bearer {router_key}",
    "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": messages,
        "stream": True
    }

    async with httpx.AsyncClient() as client:
        async with client.stream("POST", url, headers=headers, json=payload) as r:
            async for line in r.aiter_lines():
                if not line.startswith('data: '):
                    continue
                data = line[6:]
                if data == '[DONE]':
                    break
                try:
                    data_obj = json.loads(data)
                    content = data_obj["choices"][0]["delta"].get("content")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    pass
