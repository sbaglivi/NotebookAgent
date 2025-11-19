from enum import StrEnum
from pydantic import BaseModel
from typing import Literal

class MessageType(StrEnum):
    CODE = "code"
    TEXT = "text"
    QUERY = "query"
    LLM = "llm"

class CreationRequest(BaseModel):
    id: int
    content: str
    type: MessageType

class MessageBase(BaseModel):
    type: MessageType
    content: str

class MessageReq(MessageBase):
    id: str
    response_id: str | None = None

class Message(MessageBase):
    version: int = 1
    id: int

    @classmethod
    def from_message_req(cls, msg: MessageReq, id: int):
        return cls(id=id, type=msg.type, content=msg.content)

class CodeMessage(Message):
    type: Literal["code"]
    output: list
    execution_status: str

    @classmethod
    def from_message(cls, msg: Message):
        assert msg.type == "code", "CodeMessage should be built from msgs with type code"
        return cls(**msg.model_dump(), output=[], execution_status="pending")

