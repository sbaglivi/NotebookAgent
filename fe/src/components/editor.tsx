import { useRef, useEffect, useImperativeHandle, forwardRef} from 'react';
import * as monaco from 'monaco-editor/esm/vs/editor/editor.api';

type EditorProps = {
    initialCode: string
    onChange: (text: string) => void,
}

export interface EditorHandle {
    clear: () => void
}

export const Editor = forwardRef<EditorHandle, EditorProps>(({ initialCode, onChange }: EditorProps, ref) => {
  const editorRef = useRef<monaco.editor.IStandaloneCodeEditor | null>(null);
  const domRef = useRef<HTMLDivElement | null>(null);

  useImperativeHandle(ref, () => ({
    clear() {
      editorRef.current?.getModel()?.setValue("");
    }
  }));

  useEffect(() => {
    if (!domRef.current) return;

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

    });

    editor.focus()
    editorRef.current = editor;

    editor.onDidChangeModelContent(() => {
      onChange(editor.getValue());
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
