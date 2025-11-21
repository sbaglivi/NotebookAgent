import asyncio
import websockets
import json
import uuid
import httpx
from pathlib import Path

BASE_URL = "http://localhost:8000"

async def test_lsp():
    # 1. Create chat
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/chats")
        chat_id = resp.json()["id"]
        print(f"Created chat: {chat_id}")

    # 1.5 Pre-populate chat with a code cell
    chat_file = Path(f"be/chats/{chat_id}.json")
    with open(chat_file, "r") as f:
        chat_data = json.load(f)
    
    chat_data["messages"].append({
        "type": "code",
        "content": "x = 100",
        "id": 0,
        "version": 1,
        "output": [],
        "execution_status": "done"
    })
    
    with open(chat_file, "w") as f:
        json.dump(chat_data, f)

    chat_ws_url = f"ws://localhost:8000/ws/{chat_id}"
    lsp_ws_url = f"ws://localhost:8000/ws/{chat_id}/lsp"

    # 2. Connect to WS
    async with websockets.connect(chat_ws_url) as chat_ws, \
               websockets.connect(lsp_ws_url) as lsp_ws:
        
        print("Connected to Chat WS")
        print("Connected to LSP WS")

        # Wait for LSP initialization (it happens on connect)
        # We can just start sending requests

        # 5. Send LSP completion request for 'x'
        # We need to use the pending cell URI: file:///{chat_id}_pending.py
        pending_uri = f"file:///{chat_id}_pending.py"
        
        # We simulate typing 'x.' in the pending cell
        # First, update content to 'x.'
        did_change = {
            "jsonrpc": "2.0",
            "method": "textDocument/didChange",
            "params": {
                "textDocument": {
                    "uri": pending_uri,
                    "version": 2
                },
                "contentChanges": [{"text": "x."}]
            }
        }
        await lsp_ws.send(json.dumps(did_change))
        
        # Request completion
        req_id = 2
        completion_req = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "textDocument/completion",
            "params": {
                "textDocument": {
                    "uri": pending_uri
                },
                "position": {
                    "line": 0,
                    "character": 2
                }
            }
        }
        await lsp_ws.send(json.dumps(completion_req))
        print("Sent completion request")
        
        # Wait for response
        while True:
            resp = await lsp_ws.recv()
            print(f"LSP Client received: {resp}")
            resp = json.loads(resp)
            
            if resp.get("id") == req_id:
                print(f"Received completion response: {resp}")
                items = resp.get("result", {}).get("items", [])
                print(f"Got {len(items)} completion items")
                
                found = False
                for item in items:
                    if item["label"] == "bit_length":
                        found = True
                        break
                
                if found:
                    print("SUCCESS: Found int method 'bit_length' for variable x")
                else:
                    print("WARNING: Did not find 'bit_length', maybe x is not inferred as int?")
                    print(f"Top 5 items: {items[:5]}")
                break

if __name__ == "__main__":
    asyncio.run(test_lsp())
