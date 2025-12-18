"""
routes_legacy.py - Endpoints originales de discovery de modelos.

Este archivo preserva la funcionalidad existente de /models/discover
sin modificaciones, para mantener compatibilidad.
"""

import asyncio
from typing import List, Optional, Dict, Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic

from scoring import assign_score
from list import process_models

router = APIRouter(tags=["Models Discovery"])


# =============================================================================
# MODELOS DE DATOS
# =============================================================================

class DiscoveryRequest(BaseModel):
    openai_key: Optional[str] = None
    gemini_key: Optional[str] = None
    anthropic_key: Optional[str] = None
    deepseek_key: Optional[str] = None
    openrouter_key: Optional[str] = None
    
    sorting: Literal["default", "ranking", "context"] = "default"
    group: bool = Field(default=False, description="Agrupar visualmente por proveedor")
    snapshots: bool = Field(default=False, description="Mostrar versiones antiguas/fechadas")
    openrouter_free: bool = Field(default=False, description="Mostrar solo modelos gratuitos")


class ModelInfo(BaseModel):
    id: str
    provider: str
    name: str
    elo_score: int = 0
    context_window: Optional[int] = 0
    pricing_input: Optional[float] = 0.0
    pricing_output: Optional[float] = 0.0
    details: Dict[str, Any] = {}


class DiscoveryResponse(BaseModel):
    total: int
    models: List[ModelInfo]


# =============================================================================
# FETCHERS (Funciones de Búsqueda por Proveedor)
# =============================================================================

async def fetch_openai(api_key: str):
    if not api_key: return []
    try:
        client = AsyncOpenAI(api_key=api_key)
        models = await client.models.list()
        
        results = []
        for m in models.data:
            if "gpt" in m.id or "o1" in m.id:
                score = assign_score(m.id)
                results.append(ModelInfo(
                    id=m.id,
                    provider="openai",
                    name=m.id,
                    elo_score=score,
                    details=m.model_dump()
                ))
        return results
    except Exception as e:
        print(f"❌ Error OpenAI: {str(e)}")
        return []


async def fetch_google(api_key: str):
    if not api_key: return []
    try:
        client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )
        models = await client.models.list()
        
        results = []
        for m in models.data:
            if "gemini" in m.id:
                clean_name = m.id.replace("models/", "")
                score = assign_score(clean_name)
                results.append(ModelInfo(
                    id=m.id,
                    provider="google",
                    name=clean_name,
                    elo_score=score,
                    details=m.model_dump()
                ))
        return results
    except Exception as e:
        print(f"❌ Error Google: {str(e)}")
        return []


async def fetch_deepseek(api_key: str):
    if not api_key: return []
    try:
        client = AsyncOpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        models = await client.models.list()
        
        results = []
        for m in models.data:
            score = assign_score(m.id)
            results.append(ModelInfo(
                id=m.id,
                provider="deepseek",
                name=m.id,
                elo_score=score,
                details=m.model_dump()
            ))
        return results
    except Exception as e:
        print(f"❌ Error DeepSeek: {str(e)}")
        return []


async def fetch_anthropic(api_key: str):
    if not api_key: return []
    try:
        client = AsyncAnthropic(api_key=api_key)
        models = await client.models.list(limit=100)
        
        results = []
        for m in models.data:
            score = assign_score(m.id)
            results.append(ModelInfo(
                id=m.id,
                provider="anthropic",
                name=m.display_name,
                elo_score=score,
                details=m.to_dict()
            ))
        return results
    except Exception as e:
        print(f"❌ Error Anthropic: {str(e)}")
        return []


async def fetch_openrouter(api_key: str):
    if not api_key: return []
    try:
        client = AsyncOpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
        models = await client.models.list()
        results = []
        for m in models.data:
            raw = m.model_dump()
            
            pricing = raw.get("pricing", {})
            try:
                p_in = float(pricing.get("prompt", 0) or 0) * 1_000_000
            except: p_in = 0.0
            
            try:
                p_out = float(pricing.get("completion", 0) or 0) * 1_000_000
            except: p_out = 0.0
            
            ctx = raw.get("context_length") or raw.get("top_provider", {}).get("context_length") or 0
            score = assign_score(m.id)

            results.append(ModelInfo(
                id=m.id,
                provider="openrouter",
                name=m.id.split("/")[-1],
                elo_score=score,
                context_window=int(ctx),
                pricing_input=p_in,
                pricing_output=p_out,
                details=raw
            ))
        return results
    except Exception as e:
        print(f"❌ Error OpenRouter: {e}")
        return []


# =============================================================================
# ENDPOINT PRINCIPAL
# =============================================================================

@router.post("/models/discover", response_model=DiscoveryResponse)
async def discover_models(req: DiscoveryRequest):
    """
    Endpoint que:
    1. Recibe API Keys
    2. Consulta proveedores en paralelo
    3. Calcula ELO Scores
    4. Filtra, Ordena y Agrupa
    """
    tasks = []
    
    if req.openai_key and len(req.openai_key) > 5:
        tasks.append(fetch_openai(req.openai_key))
        
    if req.gemini_key and len(req.gemini_key) > 5:
        tasks.append(fetch_google(req.gemini_key))
        
    if req.deepseek_key and len(req.deepseek_key) > 5:
        tasks.append(fetch_deepseek(req.deepseek_key))
        
    if req.anthropic_key and len(req.anthropic_key) > 5:
        tasks.append(fetch_anthropic(req.anthropic_key))
        
    if req.openrouter_key and len(req.openrouter_key) > 5:
        tasks.append(fetch_openrouter(req.openrouter_key))
    
    if not tasks: 
        return {"total": 0, "models": []}

    print(f"🚀 Procesando {len(tasks)} proveedores en paralelo...")
    
    results = await asyncio.gather(*tasks)
    raw_models = [m for sub in results for m in sub]
    
    clean_models = process_models(
        raw_models,
        sort_by=req.sorting,
        group_by_provider=req.group,
        show_snapshots=req.snapshots,
        only_free=req.openrouter_free
    )

    return {
        "total": len(clean_models),
        "models": clean_models
    }
