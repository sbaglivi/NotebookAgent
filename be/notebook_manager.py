import asyncio
import threading
import subprocess
from jupyter_client import KernelManager, KernelClient
from . import lsp, mytypes
from typing import Optional
import json
import os

class NotebookSession:
    def __init__(self, chat_id: str):
        self.chat_id = chat_id
        self.ref_count = 0
        self.km: Optional[KernelManager] = None
        self.kc: Optional[KernelClient] = None
        self.ls_proc: Optional[subprocess.Popen] = None
        self.ls_queue: Optional[asyncio.Queue] = None
        self.ls_thread: Optional[threading.Thread] = None
        self.notebook_version = 1
        self.cell_count = 0

    def start(self, initial_messages: list[mytypes.Message]):
        # Start Kernel
        self.km = KernelManager()
        self.km.start_kernel()
        self.kc = self.km.client()
        self.kc.start_channels()
        self.kc.wait_for_ready()

        # Start LS
        self.ls_proc = lsp.create_proc(os.getcwd(), lsp.InitParams(
            rootUri=f"file://{os.getcwd()}",
            capabilities={
                "notebookDocument": {
                    "synchronization": {
                        "dynamicRegistration": True,
                        "executionSummarySupport": True
                    }
                }
            }
        ))
        self.ls_queue = asyncio.Queue()
        
        # Initialize LS with Notebook
        notebook, cell_docs = lsp.build_notebook(self.chat_id, self.notebook_version, initial_messages)
        
        # Add pending cell
        pending_uri = lsp.pending_cid(self.chat_id)
        notebook.cells.append(lsp.Cell(document=pending_uri))
        cell_docs.append(lsp.TextDocumentItem(uri=pending_uri, text="", version=1))
        
        self.cell_count = len(notebook.cells)
        
        req = lsp.NotebookOpenRequest.create(notebook, cell_docs)
        lsp.send_msg(self.ls_proc, req.model_dump())

        # Send didOpen for pending cell
        did_open = {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {
                "textDocument": {
                    "uri": pending_uri,
                    "languageId": "python",
                    "version": 1,
                    "text": ""
                }
            }
        }
        lsp.send_msg(self.ls_proc, did_open)

        # Start LS reader thread
        loop = asyncio.get_running_loop()
        self.ls_thread = threading.Thread(
            target=self._lsp_read_loop, 
            args=(self.ls_queue, self.ls_proc.stdout, loop), 
            daemon=True
        )
        self.ls_thread.start()

    def add_cell(self, msg: mytypes.Message):
        if msg.type != "code":
            return
        
        doc_id = lsp.cid(self.chat_id, msg.id)
        new_cell = lsp.Cell(document=doc_id)
        new_doc = lsp.TextDocumentItem(uri=doc_id, version=msg.version, text=msg.content)
        
        # Insert before pending cell (last one)
        insert_index = self.cell_count - 1
        
        self.notebook_version += 1
        req = lsp.NotebookChangeRequest.create(
            uri=f"file:///{self.chat_id}.ipynb",
            version=self.notebook_version,
            start=insert_index,
            delete_count=0,
            new_cells=[new_cell],
            new_docs=[new_doc]
        )
        lsp.send_msg(self.ls_proc, req.model_dump())
        
        self.cell_count += 1

    def stop(self):
        if self.kc:
            self.kc.stop_channels()
        if self.km:
            self.km.shutdown_kernel(now=True)
        if self.ls_proc:
            self.ls_proc.kill() # or terminate
        
        self.km = None
        self.kc = None
        self.ls_proc = None
        self.ls_queue = None
        self.ls_thread = None

    def _lsp_read_loop(self, queue: asyncio.Queue, stdout, loop: asyncio.AbstractEventLoop):
        for msg in lsp.reader(stdout):
            loop.call_soon_threadsafe(queue.put_nowait, msg)

class NotebookManager:
    def __init__(self):
        self.sessions: dict[str, NotebookSession] = {}
        self._lock = asyncio.Lock() # Protect access to sessions dict

    async def connect(self, chat_id: str, initial_messages: list[mytypes.Message]) -> NotebookSession:
        async with self._lock:
            if chat_id not in self.sessions:
                session = NotebookSession(chat_id)
                session.start(initial_messages)
                self.sessions[chat_id] = session
            
            session = self.sessions[chat_id]
            session.ref_count += 1
            return session

    async def disconnect(self, chat_id: str):
        async with self._lock:
            if chat_id not in self.sessions:
                return
            
            session = self.sessions[chat_id]
            session.ref_count -= 1
            
            if session.ref_count <= 0:
                session.stop()
                del self.sessions[chat_id]

    def get_session(self, chat_id: str) -> Optional[NotebookSession]:
        return self.sessions.get(chat_id)

# Global instance
manager = NotebookManager()
