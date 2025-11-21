import {useRef, useState, useEffect} from 'react';
import type {Message, ExecutionStatus, CreateRequest, ManualMessageType} from "@/types";
import { v4 as uuidv4 } from 'uuid';
import { NewCell } from '@/components/NewCell';
import { MessageBubble } from '@/components/messageBubble';

export function ChatComponent({initialMessages, id, baseUrl}: {initialMessages: Message[], id: string, baseUrl: string}) {
  const [messages, setMessages] = useState<Message[]>(() => initialMessages)
  const wsRef = useRef<WebSocket | null>(null)
  // it should be better to use a datasource that's not state since 
  // react might batch state updates 
  // const dataRef = useRef<Message[]>([]), 


  useEffect(() => {
    // Establish WebSocket connection
    const ws = new WebSocket(baseUrl + "/ws/" + id)
    
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
      <NewCell onSubmit={sendMessage} baseUrl={baseUrl} chatId={id}/>
    </div>
  )

}