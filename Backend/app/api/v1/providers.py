from dataclasses import asdict

from fastapi import APIRouter, Depends

from app.schemas.provider_health import (
    ProviderHealthResponse,
    ProvidersHealthResponse,
)
from app.services.api_key_service import get_api_key
from app.services.provider_health_service import (
    ProviderHealth,
    provider_health_service,
)

router = APIRouter(prefix="/v1/providers", tags=["providers"])
CONFIGURED_PROVIDERS = ("groq", "gemini", "openrouter")


@router.get(
    "/health",
    response_model=ProvidersHealthResponse,
)
async def providers_health(
    _api_key=Depends(get_api_key),
) -> ProvidersHealthResponse:
    health_by_provider = await provider_health_service.get_all_health()
    providers = {
        provider: asdict(health_by_provider.get(provider, ProviderHealth()))
        for provider in CONFIGURED_PROVIDERS
    }
    return ProvidersHealthResponse(
        providers={
            provider: ProviderHealthResponse(**health)
            for provider, health in providers.items()
        }
    )
