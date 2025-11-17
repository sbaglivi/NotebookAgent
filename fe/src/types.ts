export type ManualMessageType = "text" | "code" | "query"
type MessageType = ManualMessageType | "llm"

export type Chat = {
  id: string
  messages: Message[]
}

type BaseMessage = {
  author: string
  content: string
}

type MessageState =
  | { id: string; acknowledged: false }
  | { id: number; acknowledged: true }

export type ExecutionStatus = "pending" | "started" | "done";
type CodePayload = {
  type: "code"
  executionStatus: ExecutionStatus
  output: any[]
}

type MessagePayload =
  | { type: "text" | "query" | "llm"}
  | CodePayload

export type Message = BaseMessage & MessageState & MessagePayload

export type CreateRequest = {
  content: string,
  request_type: "create",
  id: string,
  type: ManualMessageType,
  response_id?: string
}


// Code outputs

type StreamOutput = {
  type: "stream",
  content: {
    name: "stdout" | "stderr",
    text: string
  }
}

type ErrorOutput = {
  type: "error",
  content: string
}

type OutContentType = "image/png" | "text/html" | "text/plain"

type DataOutput = {
  type: "data"
  content: {
    type: OutContentType,
    data: string
  }
}

export type Output = StreamOutput | ErrorOutput | DataOutput

// NOT USED YET


type EditRequest = {
  request_type:"edit",
  id: number,
  change: {
    content: string,
    type: ManualMessageType
  }
}

type DeleteRequest = {
  request_type:"delete",
  id: number,
}

// type Request = CreateRequest | EditRequest | DeleteRequest

type NotFoundResponse = {
  result: "not found",
  id: number
}

type CreationSuccessResponse = {
  result: "created"
  id: number
}

type GenerationFailedResponse = {
  result: "generation failed",
  id: number
}

type GenerationSuccessResponse = {
  result: "generation success",
  id: number, // but who creates the id for the llm response message? maybe frontend reserves an id when it requests the generation
  content: string 
}
