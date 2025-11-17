import { useState, useEffect, useRef, type FormEvent, type MouseEvent} from 'react'
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import { v4 as uuidv4 } from 'uuid';
import stripAnsi from 'strip-ansi';
import { NewCell } from '@/components/NewCell';
import type { Message, ManualMessageType, CreateRequest, ExecutionStatus, Output, Chat} from '@/types';

const BASE_URL = "http://localhost:8000"

function LoginScreen({onSuccess}: {onSuccess: (v: Chat) => void}) {
  const [input, setInput] = useState("")  
  const [error, setError] = useState("")
  const [recent, setRecent] = useState([])
  useEffect(() => {
    fetch(BASE_URL + "/recent")
    .then(res => res.json())
    .then(data => setRecent(data))
  }, [setRecent])
  async function getOrCreateChat(create: boolean, id: string | null = null) {
    let response;
    if (create) {
      response = await fetch(`${BASE_URL}/chats`, {
        "method": "POST"
      })
    } else {
      const chatId = (id ?? input).trim()
      response = await fetch(`${BASE_URL}/chats/${chatId}`)
    }
    if (response.status != 200) {
      const text = await response.text();
      setError(`${response.status}: ${text}`)
      return
    }

    const content = await response.json()
    onSuccess(content)
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!input) return

    await getOrCreateChat(false)
  }

  async function onClick(e: MouseEvent) {
    e.preventDefault()

    await getOrCreateChat(true)
  }

  async function selectRecent(v: string) {
    await getOrCreateChat(false, v)
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col place-content-center">
      {error && <p className="red-800">while trying to retrieve chat: {error}</p>}
      <div className="flex place-content-stretch">
        <input type="text" value={input} onChange={e => setInput(e.target.value)} className="border-1 rounded-sm px-2 py-1 flex-grow-1"/>
        <button type="submit" className="border-1 p-4 rounded-sm flex-grow-1">Go</button>
      </div>
      <div>
        {recent.map(r => <button key={r} type="button" onClick={selectRecent.bind(null, r)}>{r}</button>)}
      </div>
      <button type="button" onClick={onClick} className="border-1 p-4 rounded-sm">Create new</button>
    </form>
  )
}

function MarkdownRenderer({ text }: {text: string}) {
  const html = DOMPurify.sanitize(marked(text, {async: false}));
  return <div className="my-1 mx-2 prose" dangerouslySetInnerHTML={{ __html: html }} />;
}

function CodeOutput({output, className}: {output: Output[], className: string}) {
  function renderOut(out: Output) {
    if (out.type == "stream") {
      const isStdErr = out.content.name == "stderr"
      return <pre>{isStdErr ? "(stderr) " : ""}{out.content.text}</pre>
    }

    if (out.type == "error") {
      return <pre className="red-700">{stripAnsi(out.content)}</pre>
    }
    
    if (out.type == "data") {
      switch (out.content.type) {
        case "image/png":
          return <img src={`data:image/png;base64,${out.content.data}`} />;
        case "text/html":
          return <div dangerouslySetInnerHTML={{__html: out.content.data}}/>
        case "text/plain":
          return <pre>{out.content.data}</pre>
      }
    }
  }
  return (
    <>
      <hr className="mt-2" />
      <div className={className}>
        {...output.map(v => renderOut(v))}
      </div>
    </>
  )
}

function getStatus(msg: Message) {
  if (msg.type === "code") {
    const statusMap = {
      "started": "S",
      "done": "",
      "pending": "P"
    }
    return statusMap[msg.executionStatus];
  }

  return msg.acknowledged ? "" : '!!'

}

function CodeRenderer({content, output}: {content: string, output: Output[]}) {
  return (
    <>
      <code className="my-1 mx-2">{content}</code>
      <CodeOutput output={output} className={"mx-2"} />
    </>
  )
}

function renderMessage(msg: Message) {
  switch (msg.type) {
    case "query":
    case "llm":
      return <p className="my-1 mx-2">{msg.content}</p>
    case "text":
      return <MarkdownRenderer text={msg.content} />
    case "code":
      return <CodeRenderer content={msg.content} output={msg.output} />
  }
}

function MessageBubble(msg: Message) {
  return (
    <div key={msg.id} className="border-1 rounded-sm p-1">
      <div className="relative h-8">
        <strong className="absolute left-2 top-1">{msg.author}</strong>
        <span className="absolute right-2 top-1">{msg.type}{getStatus(msg)}</span>
      </div>
      {renderMessage(msg)}
    </div>
  )
}



function Chat({initialMessages, id}: {initialMessages: Message[], id: string}) {
  const [messages, setMessages] = useState<Message[]>(() => initialMessages)
  const wsRef = useRef<WebSocket | null>(null)
  // it should be better to use a datasource that's not state since 
  // react might batch state updates 
  // const dataRef = useRef<Message[]>([]), 


  useEffect(() => {
    // Establish WebSocket connection
    const ws = new WebSocket(BASE_URL + "/ws/" + id)
    
    ws.onopen = () => {
      console.log("WebSocket connected")
    }


    ws.onmessage = (event) => {
      const response = JSON.parse(event.data)
      const {result, tmpID, id, content, type} = response;
      switch (result) {
        case "code execution":
          if (type === "status") {
            const statusMap: {[key: string]: ExecutionStatus} = {
              "busy": "started",
              "idle": "done"
            }
            if (!(content in statusMap)) {
              console.error(`unhandled status update: ${content}`)
              return
            }
            setMessages(msgs => msgs.map(m => m.id === id ? {...m, executionStatus: statusMap[content]} : m))
          } else {
            setMessages(msgs => msgs.map(m => m.id === id && m.type === "code" ? {...m, output: [...m.output, {type,content}]} : m))
          }
          break
        case "created": 
          setMessages(msgs => msgs.map(m => m.id === tmpID ? {...m, acknowledged: true, id: id} : m))
          break
        case "generation success":
          let mym = messages.find(m => m.id === id) 
          console.debug(`mym ${mym} new content ${content}`)
          setMessages(msgs => msgs.map(m => m.id === id ? {...m, content: m.content + content} : m)) 
          break
        default:
          console.error(`unhandled response: ${response}`)
      }
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

  function sendCreationRequest(ws: WebSocket, id: string, content: string, type: ManualMessageType, responseID: string | null = null) {
    const toSend: CreateRequest = {
      request_type: "create",
      id,
      content,
      type
    }
    if (type === "query") {
      if (responseID === null) {
        throw new TypeError("responseID null when trying to send request for llm generation")
      }

      toSend["response_id"] = responseID
    }
    ws.send(JSON.stringify(toSend))
  }

  async function sendMessage(input: string, msgType: ManualMessageType) {
    const wsState = wsRef.current?.readyState
    if (!wsRef.current || wsState !== WebSocket.OPEN) {
      console.error(`failed to send message, ws state ${wsState}`)
      return
    }

    const msgId = uuidv4()
    let newMessage: Message;
    if (msgType === "code") {
      newMessage = {
        acknowledged: false as const,
        id: msgId,
        author: "user",
        content: input,
        type: "code",
        executionStatus: "pending",
        output: []
      }
    } else {
      newMessage = {
        acknowledged: false as const,
        id: msgId,
        author: "user",
        content: input,
        type: msgType,
      }
    }
    if (msgType !== "query") {
      sendCreationRequest(wsRef.current, msgId, input, msgType)
      setMessages(msgs => [...msgs, newMessage])
    } else {
      const dummyMessage = {
        acknowledged: false as const,
        id: uuidv4(),
        author: "assistant",
        content: "",
        type: "llm" as const,
      }
      sendCreationRequest(wsRef.current, msgId, input, msgType, dummyMessage.id)
      setMessages(msgs => [...msgs, newMessage, dummyMessage])
    }
  }

  return (
    <div className="my-12">
      <div className="flex flex-col gap-2 mb-2">
        {
          messages.map(m => MessageBubble(m))
        }
      </div>
      <NewCell onSubmit={sendMessage} />
    </div>
  )

}
function App() {
  const [chat, setChat] = useState<Chat | null>(null)

  function onSuccess(content: Chat) {
    setChat(content)
  }
  return (
    <>
      {chat ? <Chat initialMessages={chat.messages} id={chat.id} /> : <LoginScreen onSuccess={onSuccess} />}
    </>
  )
}

export default App
