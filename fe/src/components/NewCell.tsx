import {useState, useEffect, useRef, type MouseEvent, type KeyboardEvent} from 'react';
import {type ManualMessageType} from "@/types"
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import { Editor, type EditorHandle} from "@/components/editor"

export function NewCell({onSubmit}: {onSubmit: (input: string, type: ManualMessageType) => void}) {
  const [input, setInput] = useState("")
  const [msgType, setMsgType] = useState<ManualMessageType>("text")
  const editorRef = useRef<EditorHandle>(null)
  function handleSubmit() {
    console.log("submitting", input)
    onSubmit(input, msgType)
    editorRef.current?.clear()
    setInput("")
  }

  function onClick(e: MouseEvent<HTMLButtonElement>) {
    e.preventDefault()
    handleSubmit()
  }

    const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
        const isEnter = e.key === 'Enter' || (e as any).keyCode === 13;
        const isModifier = e.ctrlKey || e.metaKey; // ctrl on Windows/Linux, meta (Command) on macOS

        if (!isModifier) {
            return
        }

        if (isEnter) {
            e.preventDefault(); 
            console.log("enter + modifier", input, msgType)
            handleSubmit()
        } else if (e.key == "t") {
            e.preventDefault()
            setMsgType(msgType => {
                const typeCycle: Record<ManualMessageType, ManualMessageType> = {
                    "code": "text",
                    "text": "query",
                    "query": "code"
                };
                const nextType = typeCycle[msgType];
                console.debug(`cycling from ${msgType} to ${nextType}`);
                return nextType;
            });
        }
    }

  let inputField = <Textarea className="h-30" value={input} onChange={e => setInput(e.target.value)} name="message" autoFocus/>
  if (msgType === "code") {
    inputField = <Editor ref={editorRef} onChange={(text: string) => setInput(text)} initialCode={input}/>
  }

  return (
    <form className="relative">
      <select value={msgType} onChange={e => setMsgType(e.target.value as ManualMessageType)} className="absolute top-2 right-2 border-1 rounded-sm pl-2 py-1 z-10">
        <option value="code">code</option>
        <option value="text">text</option>
        <option value="query">query</option>
      </select>
      <div onKeyDown={onKeyDown}>
        {inputField}
        <Button className="absolute right-2 bottom-2 z-10" type="submit" onClick={onClick} >Send</Button>
      </div>
    </form>
  )

}