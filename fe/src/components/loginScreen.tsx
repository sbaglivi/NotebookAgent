import {useState, useEffect, type FormEvent, type MouseEvent} from 'react';
import type {Chat} from '@/types'

export function LoginScreen({onSuccess, baseUrl}: {onSuccess: (v: Chat) => void, baseUrl: string}) {
  const [input, setInput] = useState("")  
  const [error, setError] = useState("")
  const [recent, setRecent] = useState([])
  useEffect(() => {
    fetch(baseUrl + "/recent")
    .then(res => res.json())
    .then(data => setRecent(data))
  }, [setRecent])
  async function getOrCreateChat(create: boolean, id: string | null = null) {
    let response;
    if (create) {
      response = await fetch(`${baseUrl}/chats`, {
        "method": "POST"
      })
    } else {
      const chatId = (id ?? input).trim()
      response = await fetch(`${baseUrl}/chats/${chatId}`)
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
