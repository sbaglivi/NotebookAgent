import { useRef, useEffect, useImperativeHandle, forwardRef } from 'react';
import * as monaco from 'monaco-editor';
import { lspManager } from '@/lib/lsp';

type EditorProps = {
  initialCode: string
  onChange: (text: string) => void,
  baseUrl: string,
  chatId: string,
  uri: string
}
window.MonacoEnvironment = {
  getWorker(_, label) {
    return new Worker(
      new URL(
        'monaco-editor/esm/vs/editor/editor.worker.js',
        import.meta.url
      ),
      { type: 'module' }
    )
  }
}


export interface EditorHandle {
  clear: () => void
}

export const Editor = forwardRef<EditorHandle, EditorProps>(({ initialCode, onChange, baseUrl, chatId, uri }: EditorProps, ref) => {
  const editorRef = useRef<monaco.editor.IStandaloneCodeEditor | null>(null);
  const domRef = useRef<HTMLDivElement | null>(null);
  const wsRef = useRef<WebSocket | null>(null)
  // it should be better to use a datasource that's not state since 
  // react might batch state updates 
  // const dataRef = useRef<Message[]>([]), 


  useEffect(() => {
    // Establish WebSocket connection
    const ws = new WebSocket(`${baseUrl}/ws/${chatId}/lsp`)

    ws.onopen = () => {
      console.log("WebSocket connected")
    }


    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.id !== undefined && (msg.result !== undefined || msg.error !== undefined)) {
        // LSP response
        lspManager.handleMessage(msg);
      }
    }

    ws.onerror = (error) => {
      console.error("WebSocket error:", error)
    }

    ws.onclose = () => {
      console.log("WebSocket closed")
    }

    wsRef.current = ws
    lspManager.register(uri, ws);

    return () => {
      lspManager.unregister(uri);
      ws.close()
    }
  }, [uri])

  useImperativeHandle(ref, () => ({
    clear() {
      editorRef.current?.getModel()?.setValue("");
    }
  }));

  useEffect(() => {
    if (!domRef.current) return;


    const modelUri = monaco.Uri.parse(uri);
    let model = monaco.editor.getModel(modelUri);
    if (!model) {
      model = monaco.editor.createModel(initialCode, 'python', modelUri);
    } else {
      model.setValue(initialCode);
    }

    const editor = monaco.editor.create(domRef.current, {
      model: model,
      overviewRulerLanes: 0,
      renderLineHighlight: 'none',
      occurrencesHighlight: 'off',
      lineNumbers: 'off',
      minimap: { enabled: false },
      lineDecorationsWidth: 8,
      folding: false,
      padding: { top: 8, bottom: 8 },
      quickSuggestions: false
    });

    editor.focus()
    editorRef.current = editor;

    let version = 1;
    editor.onDidChangeModelContent(() => {
      const value = editor.getValue();
      onChange(value);

      // Send didChange to LSP
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        version += 1;
        const req = {
          jsonrpc: "2.0",
          method: "textDocument/didChange",
          params: {
            textDocument: {
              uri: uri,
              version: version
            },
            contentChanges: [{ text: value }]
          }
        };
        wsRef.current.send(JSON.stringify(req));
      }
    });
    return () => {
      editor.dispose();
      editorRef.current = null;
    };
  }, []);

  return (
    <div
      ref={domRef}
      className="h-30 border-1 rounded-sm overflow-hidden"
    />
  );
});
