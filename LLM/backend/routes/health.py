"""
routes/health.py - Endpoints de health check y validación de API keys.
"""

from fastapi import APIRouter
from datetime import datetime
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
import asyncio
import httpx
from typing import List, Optional

from models import (
    HealthResponse,
    KeysValidationRequest,
    KeysValidationResponse,
    KeyValidationResult
)
from database import DB_PATH
from pydantic import BaseModel

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
    
    if req.ollama_url and len(req.ollama_url) > 5:
        tasks.append(validate_ollama(req.ollama_url))
        providers.append("ollama")
    
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


# =============================================================================
# OLLAMA - Modelos Locales
# =============================================================================

class OllamaModel(BaseModel):
    """Información de un modelo de Ollama."""
    name: str
    model: str
    size: int
    parameter_size: Optional[str] = None
    quantization_level: Optional[str] = None
    family: Optional[str] = None


class OllamaModelsRequest(BaseModel):
    """Request para obtener modelos de Ollama."""
    url: str  # URL del servidor Ollama (ej: http://localhost:11434)


class OllamaModelsResponse(BaseModel):
    """Response con modelos de Ollama."""
    connected: bool
    models: List[OllamaModel] = []
    error: Optional[str] = None


@router.post("/ollama/models", response_model=OllamaModelsResponse)
async def get_ollama_models(req: OllamaModelsRequest):
    """
    Obtiene la lista de modelos disponibles en un servidor Ollama.
    """
    try:
        base_url = req.url.rstrip('/')
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{base_url}/api/tags")
            response.raise_for_status()
            data = response.json()
            
            models = []
            for m in data.get('models', []):
                details = m.get('details', {})
                models.append(OllamaModel(
                    name=m.get('name', ''),
                    model=m.get('model', ''),
                    size=m.get('size', 0),
                    parameter_size=details.get('parameter_size'),
                    quantization_level=details.get('quantization_level'),
                    family=details.get('family')
                ))
            
            return OllamaModelsResponse(connected=True, models=models)
            
    except httpx.ConnectError:
        return OllamaModelsResponse(
            connected=False, 
            error=f"No se puede conectar a {req.url}"
        )
    except httpx.TimeoutException:
        return OllamaModelsResponse(
            connected=False, 
            error="Timeout al conectar"
        )
    except Exception as e:
        return OllamaModelsResponse(
            connected=False, 
            error=str(e)[:100]
        )


async def validate_ollama(url: str) -> KeyValidationResult:
    """Valida conexión a servidor Ollama."""
    try:
        base_url = url.rstrip('/')
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{base_url}/api/tags")
            response.raise_for_status()
            return KeyValidationResult(valid=True)
    except httpx.ConnectError:
        return KeyValidationResult(valid=False, error="No se puede conectar")
    except Exception as e:
        return KeyValidationResult(valid=False, error=str(e)[:100])
