from enum import StrEnum
from pydantic import BaseModel

class MessageType(StrEnum):
    CODE = "code"
    TEXT = "text"
    QUERY = "query"
    LLM = "llm"

class CreationRequest(BaseModel):
    id: int
    content: str
    type: MessageType

