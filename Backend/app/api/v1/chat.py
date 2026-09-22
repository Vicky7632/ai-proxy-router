from fastapi import APIRouter, Depends, HTTPException
import httpx
from app.db.models.api_key import APIKey
from app.services.api_key_service import get_api_key
from app.schemas.chat import ChatCompletionRequest

router = APIRouter()

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

@router.post("/v1/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    api_key: APIKey = Depends(get_api_key),
):
    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }
    payload = request.model_dump()

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(GROQ_URL, json=payload, headers=headers)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Provider request failed: {str(e)}")

    return response.json()