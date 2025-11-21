from pydantic import BaseModel
from typing import Literal, Any
from . import mytypes
from enum import StrEnum
import json
import time
from pathlib import Path
import subprocess

class LRRequest(BaseModel):
    type: Literal["completion", "hover", "signature", "change"] # send diagnostic, but only be -> fe


class Cell(BaseModel):
    kind: Literal[2] = 2 # code
    document: str # id e.g. {chat_id}_{cell_id}

class TextDocumentItemMin(BaseModel):
    uri: str # same as document I guess?

class TextDocumentItemSmall(TextDocumentItemMin):
    version: int # increases with each change

    @classmethod
    def create(cls, uri: str, version: int = 1):
        return cls(uri=uri, version=version)

class TextDocumentItem(TextDocumentItemSmall):
    languageId: Literal['python'] = 'python'
    text: str # actual content

    @classmethod
    def create(cls, uri: str, text: str, version: int = 1):
        return cls(text=text, uri=uri, version=version)

class NotebookDoc(BaseModel):
    uri: str # chat_id
    notebookType: str = "jupyter-notebook"
    version: int # increases when insert, delete, reorder cells, not just modify cell
    cells: list[Cell]
    # cellTextDocuments removed as it's not part of NotebookDocument

def cid(chat_id: str, cell_id: int) -> str:
    return f"file:///{chat_id}_cell_{cell_id}.py"

def pending_cid(chat_id: str) -> str:
    return f"file:///{chat_id}_pending.py"

def build_notebook(chat_id: str, version: int, msgs: list[mytypes.Message]) -> tuple[NotebookDoc, list[TextDocumentItem]]:
    cells = []
    cell_docs = []
    for msg in msgs:
        if msg.type != "code":
            continue
        doc_id = cid(chat_id, msg.id)
        cells.append(Cell(document=doc_id))
        cell_docs.append(TextDocumentItem(uri=doc_id, version=msg.version, text=msg.content))
    
    return NotebookDoc(uri=f"file:///{chat_id}.ipynb", version=version, cells=cells), cell_docs

class Method(StrEnum):
  OPEN = "textDocument/didOpen"
  CHANGE = "textDocument/didChange"
  HOVER = "textDocument/hover"
  COMPLETION = "textDocument/completion"
  NOTEBOOK_OPEN = "notebookDocument/didOpen"
  NOTEBOOK_CHANGE = "notebookDocument/didChange"

class JSONMessage(BaseModel):
  jsonrpc: Literal["2.0"] = "2.0"
  method: Method

class JSONRequest(JSONMessage):
  id: int
  params: Any

  # "method": "textDocument/didOpen",
class OpenParams(BaseModel):
  textDocument: TextDocumentItem

  @classmethod
  def create(cls, uri: str, text: str, version: int = 1):
      return cls(textDocument=TextDocumentItem.create(uri, text, version))

class OpenRequest(JSONMessage):
  method: Literal[Method.OPEN] = Method.OPEN
  params: OpenParams

  @classmethod
  def create(cls, uri: str, text: str, version: int = 1):
    return cls(params=OpenParams.create(uri, text, version))

  # "method": "textDocument/didChange",
class TextChange(BaseModel):
  text: str
  # here you should be able to also specify a range to not send the whole thing

class ChangeParams(BaseModel):
  textDocument: TextDocumentItemSmall
  contentChanges: list[TextChange]

  @classmethod
  def create(cls, uri: str, text: str, version: int = 1):
    return cls(textDocument=TextDocumentItemSmall.create(uri, version), contentChanges=[TextChange(text=text)])

class ChangeRequest(JSONMessage):
  method: Literal[Method.CHANGE] = Method.CHANGE
  params: ChangeParams

  @classmethod
  def create(cls, uri: str, text: str, version: int = 1):
    return cls(params=ChangeParams.create(uri, text, version))

class Position(BaseModel):
  line: int # 0 index
  character: int # 0 index

  # "method": "textDocument/hover",
class HoverParams(BaseModel):
  textDocument: TextDocumentItemMin
  position: Position

  @classmethod
  def create(cls, uri: str, line: int, col: int):
    return cls(textDocument=TextDocumentItemMin(uri=uri), position=Position(line=line, character=col))

class HoverRequest(JSONMessage):
  method: Literal[Method.HOVER] = Method.HOVER
  params: HoverParams

  @classmethod
  def create(cls, uri: str, line: int, col: int):
    return cls(params=HoverParams.create(uri, line, col))

  # "method": "textDocument/completion",
CompletionParams = HoverParams
class CompletionRequest(JSONMessage):
  method: Literal[Method.COMPLETION] = Method.COMPLETION
  params: CompletionParams

  @classmethod
  def create(cls, uri: str, line: int, col: int):
    return cls(params=CompletionParams.create(uri, line, col))

class InitParams(BaseModel):
  process_id: int | None = None
  rootUri: str = "file:///"
  capabilities: dict = {
      "textDocument": {},
      "notebookDocument": {
          "synchronization": {
              "dynamicRegistration": True,
              "executionSummarySupport": True
          }
      }
  }

class NotebookOpenParams(BaseModel):
    notebookDocument: NotebookDoc
    cellTextDocuments: list[TextDocumentItem]

    @classmethod
    def create(cls, notebook: NotebookDoc, cell_docs: list[TextDocumentItem]):
        return cls(notebookDocument=notebook, cellTextDocuments=cell_docs)

class NotebookOpenRequest(JSONMessage):
    method: Literal[Method.NOTEBOOK_OPEN] = Method.NOTEBOOK_OPEN
    params: NotebookOpenParams

    @classmethod
    def create(cls, notebook: NotebookDoc, cell_docs: list[TextDocumentItem]):
        return cls(params=NotebookOpenParams.create(notebook, cell_docs))

class NotebookCellTextDocumentFilter(BaseModel):
    notebook: Any # NotebookDocumentFilter

class NotebookDocumentFilter(BaseModel):
    notebookType: str
    scheme: str | None = None
    pattern: str | None = None

class NotebookCellStructure(BaseModel):
    cell: Cell
    kind: Literal[2] = 2
    didOpen: list[TextDocumentItem] | None = None
    didClose: list[TextDocumentItemMin] | None = None

class NotebookDocumentStructureChange(BaseModel):
    start: int
    deleteCount: int
    cells: list[NotebookCellStructure] | None = None

class NotebookDocumentChangeEvent(BaseModel):
    structure: NotebookDocumentStructureChange | None = None
    textContent: Any | None = None # NotebookDocumentCellContentChange

class VersionedNotebookDocumentIdentifier(BaseModel):
    version: int
    uri: str

class NotebookChangeParams(BaseModel):
    notebookDocument: VersionedNotebookDocumentIdentifier
    change: NotebookDocumentChangeEvent

    @classmethod
    def create(cls, uri: str, version: int, start: int, delete_count: int, new_cells: list[Cell], new_docs: list[TextDocumentItem]):
        # Structure change
        struct_cells = []
        for cell, doc in zip(new_cells, new_docs):
            struct_cells.append(NotebookCellStructure(cell=cell, didOpen=[doc]))
        
        change = NotebookDocumentChangeEvent(
            structure=NotebookDocumentStructureChange(
                start=start,
                deleteCount=delete_count,
                cells=struct_cells
            )
        )
        return cls(
            notebookDocument=VersionedNotebookDocumentIdentifier(uri=uri, version=version),
            change=change
        )

class NotebookChangeRequest(JSONMessage):
    method: Literal[Method.NOTEBOOK_CHANGE] = Method.NOTEBOOK_CHANGE
    params: NotebookChangeParams

    @classmethod
    def create(cls, uri: str, version: int, start: int, delete_count: int, new_cells: list[Cell], new_docs: list[TextDocumentItem]):
        return cls(params=NotebookChangeParams.create(uri, version, start, delete_count, new_cells, new_docs))

def reader(stdout):
    buffer = b""
    while True:
        chunk = stdout.read(1)
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
                buffer += stdout.read(length - len(buffer))

            body = buffer[:length]
            buffer = buffer[length:]

            try:
                msg = json.loads(body.decode())
                yield msg
            except Exception:
                print("Invalid JSON:", body)

def create_proc(root_dir: str, init_params: InitParams):
  BASE_DIR = Path(__file__).parent
  cmd = f"{BASE_DIR}/.venv/bin/pyright-langserver --stdio"
  proc = subprocess.Popen(
      cmd.split(),
      stdin=subprocess.PIPE,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE,
  )
  initialize = {
    "jsonrpc": "2.0",
    "id": 0,
    "method": "initialize",
    "params": init_params.model_dump()
  }

  send_msg(proc, initialize)
  time.sleep(0.2)

  send_msg(proc, {
    "jsonrpc": "2.0",
    "method": "initialized",
    "params": {}
  })
  return proc

def send_msg(proc: subprocess.Popen, msg: dict):
    body = json.dumps(msg)
    print(f"LSP SEND: {body}")
    header = f"Content-Length: {len(body)}\r\n\r\n"
    proc.stdin.write(header.encode("utf-8"))
    proc.stdin.write(body.encode("utf-8"))
    proc.stdin.flush()
