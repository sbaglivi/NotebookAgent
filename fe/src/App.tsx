import { useState} from 'react'
import { LoginScreen } from '@/components/loginScreen';
import {ChatComponent} from "@/components/chat"
import type { Chat} from '@/types';

const BASE_URL = "http://localhost:8000"


function App() {
  const [chat, setChat] = useState<Chat | null>(null)

  function onSuccess(content: Chat) {
    setChat(content)
  }
  return (
    <>
      {chat ? <ChatComponent initialMessages={chat.messages} id={chat.id} baseUrl={BASE_URL} /> : <LoginScreen onSuccess={onSuccess} baseUrl={BASE_URL} />}
    </>
  )
}

export default App
