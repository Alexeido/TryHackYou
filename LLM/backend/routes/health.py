"""
routes/health.py - Endpoints de health check y validación de API keys.
"""

from fastapi import APIRouter
from datetime import datetime
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
import asyncio

from models import (
    HealthResponse,
    KeysValidationRequest,
    KeysValidationResponse,
    KeyValidationResult
)
from database import DB_PATH

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check básico - verifica que el servidor está vivo.
    """
    db_status = "connected" if DB_PATH.exists() else "not_initialized"
    
    return HealthResponse(
        status="healthy",
        version="6.0.0",
        database=db_status,
        timestamp=datetime.utcnow().isoformat()
    )


@router.post("/health/keys", response_model=KeysValidationResponse)
async def validate_api_keys(req: KeysValidationRequest):
    """
    Valida todas las API keys proporcionadas.
    Hace una llamada mínima a cada proveedor para verificar autenticación.
    """
    results = {}
    tasks = []
    providers = []
    
    # Preparar tareas de validación
    if req.openai_key and len(req.openai_key) > 5:
        tasks.append(validate_openai(req.openai_key))
        providers.append("openai")
    
    if req.gemini_key and len(req.gemini_key) > 5:
        tasks.append(validate_google(req.gemini_key))
        providers.append("google")
    
    if req.anthropic_key and len(req.anthropic_key) > 5:
        tasks.append(validate_anthropic(req.anthropic_key))
        providers.append("anthropic")
    
    if req.deepseek_key and len(req.deepseek_key) > 5:
        tasks.append(validate_deepseek(req.deepseek_key))
        providers.append("deepseek")
    
    if req.openrouter_key and len(req.openrouter_key) > 5:
        tasks.append(validate_openrouter(req.openrouter_key))
        providers.append("openrouter")
    
    # Ejecutar validaciones en paralelo
    if tasks:
        validation_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for provider, result in zip(providers, validation_results):
            if isinstance(result, Exception):
                results[provider] = KeyValidationResult(valid=False, error=str(result))
            else:
                results[provider] = result
    
    return KeysValidationResponse(**results)


# =============================================================================
# FUNCIONES DE VALIDACIÓN POR PROVEEDOR
# =============================================================================

async def validate_openai(api_key: str) -> KeyValidationResult:
    """Valida API key de OpenAI listando modelos."""
    try:
        client = AsyncOpenAI(api_key=api_key)
        # Llamada mínima: listar modelos
        await client.models.list()
        return KeyValidationResult(valid=True)
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "invalid" in error_msg.lower():
            return KeyValidationResult(valid=False, error="API Key inválida")
        elif "429" in error_msg:
            return KeyValidationResult(valid=False, error="Rate limit excedido")
        else:
            return KeyValidationResult(valid=False, error=f"Error: {error_msg[:100]}")


async def validate_google(api_key: str) -> KeyValidationResult:
    """Valida API key de Google (Gemini) usando adaptador OpenAI."""
    try:
        client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )
        await client.models.list()
        return KeyValidationResult(valid=True)
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "403" in error_msg or "invalid" in error_msg.lower():
            return KeyValidationResult(valid=False, error="API Key inválida")
        else:
            return KeyValidationResult(valid=False, error=f"Error: {error_msg[:100]}")


async def validate_anthropic(api_key: str) -> KeyValidationResult:
    """Valida API key de Anthropic."""
    try:
        client = AsyncAnthropic(api_key=api_key)
        await client.models.list(limit=1)
        return KeyValidationResult(valid=True)
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "authentication" in error_msg.lower():
            return KeyValidationResult(valid=False, error="API Key inválida")
        else:
            return KeyValidationResult(valid=False, error=f"Error: {error_msg[:100]}")


async def validate_deepseek(api_key: str) -> KeyValidationResult:
    """Valida API key de DeepSeek."""
    try:
        client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
        await client.models.list()
        return KeyValidationResult(valid=True)
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "invalid" in error_msg.lower():
            return KeyValidationResult(valid=False, error="API Key inválida")
        else:
            return KeyValidationResult(valid=False, error=f"Error: {error_msg[:100]}")


async def validate_openrouter(api_key: str) -> KeyValidationResult:
    """Valida API key de OpenRouter."""
    try:
        client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1"
        )
        await client.models.list()
        return KeyValidationResult(valid=True)
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "invalid" in error_msg.lower():
            return KeyValidationResult(valid=False, error="API Key inválida")
        else:
            return KeyValidationResult(valid=False, error=f"Error: {error_msg[:100]}")
