"""
Minimal HTTP API that exposes Rafiqi's brain over HTTP.

This lets external clients (like a LiveKit Agent running in the cloud)
send text to Rafiqi and receive a reply, while all intelligence and tools
stay on this machine.
"""

from fastapi import FastAPI
from pydantic import BaseModel

from brain import chat


class ChatRequest(BaseModel):
    text: str


class ChatResponse(BaseModel):
    reply: str


app = FastAPI(title="Rafiqi Brain API")


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(payload: ChatRequest) -> ChatResponse:
    reply = chat(payload.text)
    return ChatResponse(reply=reply)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

