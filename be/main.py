import os
import json
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from . import mytypes
import asyncio
import secrets
from queue import Empty
from jupyter_client import KernelManager, KernelClient
from typing import Literal
from itertools import groupby
from datetime import datetime, UTC

with open("/usr/share/dict/words") as f:
    words = [l.strip() for l in f.readlines()]

class MessageBase(BaseModel):
    type: mytypes.MessageType
    content: str

class MessageReq(MessageBase):
    id: str
    response_id: str | None = None

class Message(MessageBase):
    id: int

    @classmethod
    def from_message_req(cls, msg: MessageReq, id: int):
        return cls(id=id, type=msg.type, content=msg.content)

class CodeMessage(Message):
    type: Literal["code"]
    output: list
    execution_status: str

    @classmethod
    def from_message(cls, msg: Message):
        assert msg.type == "code", "CodeMessage should be built from msgs with type code"
        return cls(**msg.model_dump(), output=[], execution_status="pending")


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

def prepare_query(convs: list[Message | CodeMessage], query: str) -> list[dict[str,str]]:
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

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    conversation: list[Message | CodeMessage] = []
    await ws.accept()
    loop = asyncio.get_running_loop()
    queue = asyncio.Queue()
    count = 0
    km = KernelManager()
    km.start_kernel()
    kc = km.client()
    kc.start_channels()
    kc.wait_for_ready()
    async def read_ws():
        nonlocal count
        try:
            while True:
                json_str = await ws.receive_text()
                msg = MessageReq.model_validate_json(json_str)
                if msg.type == mytypes.MessageType.LLM:
                    print("ERROR: received msg with type LLM")
                    continue

                old_id = msg.id
                response_id = msg.response_id
                msg = Message.from_message_req(msg, count)
                count += 1
                if msg.type == mytypes.MessageType.CODE:
                    msg = CodeMessage.from_message(msg)

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

    done, pending = await asyncio.wait(
        [reader, writer],
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
