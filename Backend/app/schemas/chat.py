from pydantic import BaseModel
from typing import Optional

class Message(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str="openai/gpt-oss-20b"
    messages: list[Message]
    stream: Optional[bool] = False
    temperature: Optional[float] = 0.7