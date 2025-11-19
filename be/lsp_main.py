import subprocess
import json
import threading
import time

# initialized params = {}


id = 0
def send_msg(proc: subprocess.Popen, msg: dict):
    body = json.dumps(msg)
    header = f"Content-Length: {len(body)}\r\n\r\n"
    proc.stdin.write(header.encode("utf-8"))
    proc.stdin.write(body.encode("utf-8"))
    proc.stdin.flush()

def reader(proc: subprocess.Popen):
    buffer = b""
    while True:
        chunk = proc.stdout.read(1)
        if not chunk:
            break
        buffer += chunk

        if b"\r\n\r\n" in buffer:
            header, rest = buffer.split(b"\r\n\r\n", 1)
            buffer = rest

            headers = header.decode().split("\r\n")
            length = None
            for h in headers:
                if h.lower().startswith("content-length:"):
                    length = int(h.split(":")[1])
            if length is None:
                continue

            # wait for full body
            while len(buffer) < length:
                buffer += proc.stdout.read(length - len(buffer))

            body = buffer[:length]
            buffer = buffer[length:]

            try:
                msg = json.loads(body.decode())
                print("<<<", json.dumps(msg, indent=2))
            except:
                print("Invalid JSON:", body)

cmd = "/Users/emerald/p/ml/agent/be/.venv/bin/pyright-langserver --stdio"

proc = subprocess.Popen(
    cmd.split(),
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)

threading.Thread(target=reader, args=(proc,), daemon=True).start()

class LSClient:
  def __init__(self):
    self.cmd_idx = 0
  
# ------- LSP handshake -------

initialize = {
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "processId": None,
    "rootUri": "file:///",
    "capabilities": {
        "textDocument": {}
    }
  }
}

send_msg(proc, initialize)
time.sleep(0.2)

send_msg(proc, {
  "jsonrpc": "2.0",
  "method": "initialized",
  "params": {}
})

# ------- Open a virtual file -------
did_open = {
  "jsonrpc": "2.0",
  "method": "textDocument/didOpen",
  "params": {
    "textDocument": {
      "uri": "file:///test.py",
      "languageId": "python",
      "version": 1,
      "text": "x = 1\nprint(x)\n"
    }
  }
}

send_msg(proc, did_open)

hover = {
  "jsonrpc": "2.0",
  "id": id,
  "method": "textDocument/hover",
  "params": {
    "textDocument": {
      "uri": "file:///test.py",
    },
    # "position": {
    #     "line": 1,
    #     "character": 6,
    # }
    "position": {
        "line": 1,
        "character": 6,
    }

  }

}
time.sleep(1)
send_msg(proc, hover)
id += 1
time.sleep(1)
did_change = {
  "jsonrpc": "2.0",
  "method": "textDocument/didChange",
  "params": {
    "textDocument": {
      "uri": "file:///test.py",
      "version": 2,
    },
    "contentChanges": [{
        "text": "x = 1\nif x == 3:\n\tprint(x)\nfor x in rang"
    }]
  }
}
send_msg(proc, did_change)
time.sleep(1)
complete = {
  "jsonrpc": "2.0",
  "id": id,
  "method": "textDocument/completion",
  "params": {
    "textDocument": {
      "uri": "file:///test.py",
    },
    "position": {
        "line": 3,
        "character": 13
    }
  }
}
id += 1
send_msg(proc, complete)

# keep alive
while True:
    time.sleep(1)
