import { useRef, useEffect, useImperativeHandle, forwardRef} from 'react';
import * as monaco from 'monaco-editor';

type EditorProps = {
    initialCode: string
    onChange: (text: string) => void,
    baseUrl: string,
    chatId: string
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

export const Editor = forwardRef<EditorHandle, EditorProps>(({ initialCode, onChange, baseUrl, chatId}: EditorProps, ref) => {
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

    }

    ws.onerror = (error) => {
      console.error("WebSocket error:", error)
    }

    ws.onclose = () => {
      console.log("WebSocket closed")
    }

    wsRef.current = ws

    return () => {
      ws.close()
    }
  }, [])

  useImperativeHandle(ref, () => ({
    clear() {
      editorRef.current?.getModel()?.setValue("");
    }
  }));

  useEffect(() => {
    if (!domRef.current) return;


    if (!monaco.languages.getLanguages().some((l) => l.id === 'python')) {
      monaco.languages.register({ id: 'python' });
    }
    const disposable = monaco.languages.registerCompletionItemProvider("python", {
      triggerCharacters: ["."],
      provideCompletionItems: function(model, position) {
        console.debug("completion fired", model, position);
        return { suggestions: [] };
      }
    });
    const editor = monaco.editor.create(domRef.current, {
      value: initialCode,
      language: 'python',
      overviewRulerLanes: 0,
      renderLineHighlight: 'none',
      occurrencesHighlight: 'off',
      lineNumbers: 'off',
      minimap: {enabled: false},
      lineDecorationsWidth: 8,
      folding: false,
      padding: {top: 8, bottom: 8},
      quickSuggestions: false
    });

    editor.focus()
    editorRef.current = editor;

    editor.onDidChangeModelContent(() => {
      onChange(editor.getValue());
    });
    return () => {
      disposable.dispose()
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
