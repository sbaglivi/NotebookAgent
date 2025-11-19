from pydantic import BaseModel
from typing import Literal, Any
from . import mytypes
from enum import StrEnum
import json

class LRRequest(BaseModel):
    type: Literal["completion" | "hover" | "signature" | "change"] # send diagnostic, but only be -> fe


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
    notebookType: str = "own" # ? python
    version: int # increases when insert, delete, reorder cells, not just modify cell
    cells: list[Cell]
    cellTextDocuments: list[TextDocumentItem]

def cid(chat_id: str, cell_id: int) -> str:
    return f"{chat_id}_{cell_id}"

def build_notebook(chat_id: str, version: int, msgs: list[mytypes.Message]) -> NotebookDoc:
    cells = []
    cell_docs = []
    for msg in msgs:
        if msg.type != "code":
            continue
        doc_id = cid(chat_id, msg.id)
        cells.append(Cell(document=doc_id))
        cell_docs.append(TextDocumentItem(uri=doc_id, version=msg.version, text=msg.content))
    
    return NotebookDoc(uri=chat_id, version=version, cells=cells, cellTextDocuments=cell_docs)

class Method(StrEnum):
  OPEN = "textDocument/didOpen"
  CHANGE = "textDocument/didChange"
  HOVER = "textDocument/hover"
  COMPLETION = "textDocument/completion"

class JSONMessage(BaseModel):
  jsonrpc: Literal["2.0"] = "2.0"
  method: Method

class JSONRequest(JSONMessage):
  id: int
  params: Any

  # "method": "textDocument/didOpen",
class OpenParams:
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
  capabilities = {"textDocument": {}}

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