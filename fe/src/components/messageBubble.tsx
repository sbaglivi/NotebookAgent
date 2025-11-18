import { marked } from 'marked';
import DOMPurify from 'dompurify';
import stripAnsi from 'strip-ansi';
import type {Output, Message} from '@/types'

export function MessageBubble(msg: Message) {
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

function renderMessage(msg: Message) {
  switch (msg.type) {
    case "query":
      return <p className="my-1 mx-2">{msg.content}</p>
    case "text":
    case "llm":
      return <MarkdownRenderer text={msg.content} />
    case "code":
      return <CodeRenderer content={msg.content} output={msg.output} />
  }
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