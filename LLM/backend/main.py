import asyncio
from typing import List, Optional, Dict, Any, Literal
from fastapi import FastAPI, Body
from pydantic import BaseModel, Field
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic

# IMPORTAMOS TUS MÓDULOS DE LÓGICA
from scoring import assign_score
from list import process_models

from contextlib import asynccontextmanager
from scoring import update_scores_from_internet # <--- IMPORTAR LA FUNCIÓN

# FastAPI tiene un sistema de "Lifespan" para hacer cosas al arrancar
@asynccontextmanager
async def lifespan(app: FastAPI):
    # CÓDIGO QUE SE EJECUTA AL ARRANCAR
    # Lo lanzamos en un hilo para no bloquear
    import threading
    t = threading.Thread(target=update_scores_from_internet)
    t.start()
    yield
    # CÓDIGO AL CERRAR (si necesitaras limpiar algo)

app = FastAPI(title="Cerebro LLM", version="5.0.0", lifespan=lifespan)

# --- 1. MODELOS DE DATOS ---

class DiscoveryRequest(BaseModel):
    # 1. Keys (BYOK - Bring Your Own Key)
    openai_key: Optional[str] = None
    gemini_key: Optional[str] = None
    anthropic_key: Optional[str] = None
    deepseek_key: Optional[str] = None
    openrouter_key: Optional[str] = None
    
    # 2. Opciones de Ordenación y Filtrado (Sorting & Filtering)
    sorting: Literal["default", "ranking", "context"] = "default"
    group: bool = Field(default=False, description="Agrupar visualmente por proveedor")
    snapshots: bool = Field(default=False, description="Mostrar versiones antiguas/fechadas")
    openrouter_free: bool = Field(default=False, description="Mostrar solo modelos gratuitos")

class ModelInfo(BaseModel):
    id: str
    provider: str
    name: str
    elo_score: int = 0  # <--- Nota del Juez (scoring.py)
    context_window: Optional[int] = 0
    pricing_input: Optional[float] = 0.0
    pricing_output: Optional[float] = 0.0
    details: Dict[str, Any] = {} # JSON crudo completo (sin recortes)

class DiscoveryResponse(BaseModel):
    total: int
    models: List[ModelInfo]

# --- 2. FETCHERS (Funciones de Búsqueda por Proveedor) ---

async def fetch_openai(api_key: str):
    if not api_key: return []
    try:
        client = AsyncOpenAI(api_key=api_key)
        models = await client.models.list()
        
        results = []
        for m in models.data:
            # Filtro básico: Solo modelos de chat (gpt, o1)
            if "gpt" in m.id or "o1" in m.id:
                score = assign_score(m.id) # Calculamos nota
                
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
        # Usamos adaptador OpenAI
        client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )
        models = await client.models.list()
        
        results = []
        for m in models.data:
            if "gemini" in m.id:
                clean_name = m.id.replace("models/", "")
                score = assign_score(clean_name) # Calculamos nota
                
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
            score = assign_score(m.id) # Calculamos nota
            
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
        # Limitamos a 100 para no paginar eternamente, suficiente para ver los principales
        models = await client.models.list(limit=100)
        
        results = []
        for m in models.data:
            score = assign_score(m.id) # Calculamos nota sobre el ID (ej: claude-3-opus-20240229)
            
            results.append(ModelInfo(
                id=m.id,
                provider="anthropic",
                name=m.display_name,
                elo_score=score,
                details=m.to_dict() # Anthropic usa to_dict()
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
            
            # --- Extracción de Metadata Avanzada (Solo OpenRouter la da) ---
            pricing = raw.get("pricing", {})
            try:
                p_in = float(pricing.get("prompt", 0) or 0) * 1_000_000
            except: p_in = 0.0
            
            try:
                p_out = float(pricing.get("completion", 0) or 0) * 1_000_000
            except: p_out = 0.0
            
            # Contexto (A veces en top_provider, a veces en root)
            ctx = raw.get("context_length") or raw.get("top_provider", {}).get("context_length") or 0

            # Calculamos nota
            score = assign_score(m.id)

            results.append(ModelInfo(
                id=m.id,
                provider="openrouter",
                name=m.id.split("/")[-1], # Quitamos el prefijo de vendedor
                elo_score=score,
                context_window=int(ctx),
                pricing_input=p_in,
                pricing_output=p_out,
                details=raw # Guardamos TODO sin recortar
            ))
        return results
    except Exception as e:
        print(f"❌ Error OpenRouter: {e}")
        return []

# --- 3. ENDPOINT PRINCIPAL ---

@app.post("/models/discover", response_model=DiscoveryResponse)
async def discover_models(req: DiscoveryRequest):
    """
    Endpoint único que:
    1. Recibe API Keys.
    2. Consulta proveedores en paralelo.
    3. Calcula ELO Scores (scoring.py).
    4. Filtra, Ordena y Agrupa (list.py).
    """
    tasks = []
    
    # Lanzamos tareas solo si hay Key válida (> 5 chars)
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
    
    # Si no hay tareas, devolvemos vacío rápido
    if not tasks: return {"total": 0, "models": []}

    print(f"🚀 Procesando {len(tasks)} proveedores en paralelo...")
    
    # Esperamos a todos los proveedores
    results = await asyncio.gather(*tasks)
    
    # Aplanamos la lista de listas
    raw_models = [m for sub in results for m in sub]
    
    # --- DELEGAMOS EL ORDEN Y FILTRADO A LIST.PY ---
    clean_models = process_models(
        raw_models,
        sort_by=req.sorting,         # default, ranking, context
        group_by_provider=req.group, # True/False
        show_snapshots=req.snapshots,# True/False
        only_free=req.openrouter_free# True/False
    )

    return {
        "total": len(clean_models),
        "models": clean_models
    }

# ... (MANTÉN TUS IMPORTS Y CÓDIGO ANTERIOR DE /models/discover) ...

# -----------------------------------------------------------------------------
# NUEVA SECCIÓN: CHAT & TOOLS
# -----------------------------------------------------------------------------

# 1. MODELOS DE DATOS PARA EL CHAT
class Message(BaseModel):
    role: str
    content: Optional[str] = None
    # Campos para Tools (Opcionales, pero necesarios para el historial)
    tool_calls: Optional[List[Dict[str, Any]]] = None 
    tool_call_id: Optional[str] = None
    name: Optional[str] = None

class ChatRequest(BaseModel):
    provider: Literal["openai", "google", "deepseek", "openrouter"]
    api_key: str
    model_id: str
    messages: List[Message]
    # Tools es opcional. Si el frontend manda tools, el modelo podrá usarlas.
    tools: Optional[List[Dict[str, Any]]] = None 

class ChatResponse(BaseModel):
    role: str
    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    finish_reason: str

# 2. FACTORY: EL CAMBIADOR DE ENCHUFES
def get_client(provider: str, api_key: str) -> AsyncOpenAI:
    """
    Devuelve un cliente OpenAI configurado para el proveedor correcto.
    """
    if provider == "openai":
        return AsyncOpenAI(api_key=api_key) # URL por defecto
    
    elif provider == "google":
        # Adaptador OpenAI de Google
        return AsyncOpenAI(
            api_key=api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )
    
    elif provider == "deepseek":
        return AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
    
    elif provider == "openrouter":
        return AsyncOpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1"
        )
    
    else:
        raise ValueError(f"Proveedor '{provider}' no soportado o eliminado (bye Anthropic).")

# 3. ENDPOINT DE CHAT
@app.post("/chat", response_model=ChatResponse)
async def chat_completion(req: ChatRequest):
    """
    Endpoint universal de chat.
    Soporta texto normal Y ejecución de herramientas (Tool Calling).
    """
    try:
        # A. Configuramos el cliente según el proveedor
        client = get_client(req.provider, req.api_key)

        print(f"💬 Chat con {req.provider} -> {req.model_id}")

        # B. Llamada a la API (Compatible con OpenAI standard)
        # Nota: Convertimos los mensajes Pydantic a dicts para evitar líos con la librería
        messages_dict = [m.model_dump(exclude_none=True) for m in req.messages]

        response = await client.chat.completions.create(
            model=req.model_id,
            messages=messages_dict,
            tools=req.tools if req.tools else None,
            tool_choice="auto" if req.tools else None, # Deja que el modelo decida si usar tools
            temperature=0.1 # Bajo para ciberseguridad (más preciso)
        )

        # C. Procesamos la respuesta
        msg = response.choices[0].message
        
        # Convertimos la respuesta de la librería a nuestro modelo Pydantic
        return ChatResponse(
            role=msg.role,
            content=msg.content,
            tool_calls=[t.model_dump() for t in msg.tool_calls] if msg.tool_calls else None,
            finish_reason=response.choices[0].finish_reason
        )

    except Exception as e:
        # Manejo de errores elegante
        print(f"❌ Error en chat: {e}")
        # Devolvemos un error 500 pero con info JSON para el frontend
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))