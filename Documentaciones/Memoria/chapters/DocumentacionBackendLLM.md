# Documentación Técnica: Backend LLM

## 1. Visión General

El **Backend LLM** es un servidor FastAPI que actúa como orquestador entre el frontend, múltiples proveedores de IA y el sandbox de ejecución (KaliSandbox). Gestiona conversaciones con estructura de árbol, streaming de respuestas, ejecución de tools, y un sistema completo de misiones autónomas (modo agéntico).

### 1.1 Arquitectura de Alto Nivel

```
┌─────────────────┐     HTTP/SSE      ┌─────────────────────────────────────┐
│    Frontend     │◄─────────────────►│         Backend LLM (FastAPI)       │
│    (Next.js)    │                   │                                     │
└─────────────────┘                   │  ┌─────────────┐ ┌──────────────┐  │
                                      │  │   Routes    │ │   Database   │  │
                                      │  │   /chat     │ │   (SQLite)   │  │
                                      │  │   /conv     │ │              │  │
                                      │  │   /missions │ │  - messages  │  │
                                      │  └──────┬──────┘ │  - missions  │  │
                                      │         │        │  - objectives│  │
                                      │         ▼        └──────────────┘  │
                                      │  ┌─────────────┐                   │
                                      │  │   Scoring   │                   │
                                      │  │  (LMArena)  │                   │
                                      │  └─────────────┘                   │
                                      └───────────┬───────────────────────┘
                                                  │
                    ┌─────────────────────────────┼─────────────────────────┐
                    │                             │                         │
                    ▼                             ▼                         ▼
           ┌────────────────┐           ┌────────────────┐         ┌──────────────┐
           │    OpenAI      │           │     Google     │         │   KaliSandbox│
           │    Anthropic   │           │     Gemini     │         │   (Flask)    │
           │    DeepSeek    │           │                │         │   Puerto 5000│
           │    OpenRouter  │           │                │         └──────────────┘
           │    Ollama      │           │                │
           └────────────────┘           └────────────────┘
```

---

## 2. Estructura del Proyecto

```
LLM/backend/
├── main.py                 # Punto de entrada FastAPI
├── database.py             # Gestión SQLite + Árbol de mensajes
├── models.py               # Modelos Pydantic (Request/Response)
├── scoring.py              # Sistema de scoring ELO desde LMArena
├── security.py             # Análisis de riesgo de comandos
├── job_monitor.py          # Monitor de jobs en background
├── list.py                 # Procesamiento de listas de modelos
├── routes_legacy.py        # Endpoints legacy de discovery
├── routes/
│   ├── __init__.py
│   ├── chat.py             # Endpoint /chat (streaming + tools)
│   ├── conversations.py    # CRUD de conversaciones
│   ├── health.py           # Health check + validación de keys
│   ├── jobs.py             # Gestión de jobs en background
│   ├── messages.py         # CRUD de mensajes
│   └── missions.py         # Modo agéntico (misiones/objetivos)
├── chat_history.db         # Base de datos SQLite (generada)
└── fallbackRank.csv        # Rankings ELO de respaldo
```

---

## 3. Punto de Entrada (main.py)

### 3.1 Configuración de la Aplicación

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Cerebro LLM",
    description="Backend para el agente de ciberseguridad con soporte multi-proveedor",
    version="6.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 3.2 Lifespan (Arranque/Cierre)

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # === ARRANQUE ===
    init_db()                              # Inicializar SQLite
    threading.Thread(target=update_scores_from_internet).start()  # Actualizar rankings
    start_job_monitor(interval=5.0)        # Monitor de jobs en background
    
    yield  # Servidor corriendo
    
    # === CIERRE ===
    stop_job_monitor()
```

### 3.3 Routers Registrados

```python
app.include_router(health_router)           # /health, /health/keys
app.include_router(conversations_router)    # /conversations/*
app.include_router(chat_router)             # /chat
app.include_router(messages_router)         # /messages/*
app.include_router(jobs_router)             # /jobs/*
app.include_router(missions_router)         # /missions/*
app.include_router(legacy_router)           # /models/discover
```

---

## 4. Base de Datos (database.py)

### 4.1 Esquema de Tablas

#### 4.1.1 Conversaciones

```sql
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT 'Nueva conversación',
    system_prompt TEXT,
    active_leaf_id INTEGER,       -- Puntero al último mensaje de la rama activa
    pinned INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### 4.1.2 Mensajes (Estructura de Árbol)

```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    parent_id INTEGER,            -- NULL para system prompt (raíz)
    role TEXT NOT NULL CHECK(role IN ('system', 'user', 'assistant', 'tool')),
    content TEXT,
    tool_calls TEXT,              -- JSON string de tool calls
    tool_call_id TEXT,            -- ID si es respuesta de tool
    model_used TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_id) REFERENCES messages(id) ON DELETE SET NULL
);
```

**Árbol de Mensajes:**
```
                    [system prompt]  (parent_id = NULL)
                          │
                    [user msg 1]
                          │
                    [assistant 1]
                          │
               ┌──────────┴──────────┐
          [user edit A]         [user msg 2]
               │                     │
          [assistant A]         [assistant 2]
                                     │
                               [tool result]
                                     │
                               [assistant 3]
```

#### 4.1.3 Jobs Pendientes

```sql
CREATE TABLE pending_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL UNIQUE,
    conversation_id TEXT NOT NULL,
    leaf_id INTEGER NOT NULL,      -- Leaf cuando se lanzó el job
    command TEXT NOT NULL,
    tool_call_id TEXT,             -- ID del tool_call original
    status TEXT DEFAULT 'running',
    result TEXT,
    notified INTEGER DEFAULT 0,    -- Si ya se notificó al LLM
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME
);
```

#### 4.1.4 Misiones (Modo Agéntico)

```sql
CREATE TABLE missions (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    goal TEXT NOT NULL,
    current_phase TEXT,
    status TEXT DEFAULT 'PLANNING',  -- PLANNING, IN_PROGRESS, COMPLETED, FAILED, CANCELLED
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    metadata TEXT                    -- JSON con info adicional
);
```

#### 4.1.5 Objetivos

```sql
CREATE TABLE objectives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id TEXT NOT NULL,
    order_index INTEGER NOT NULL,
    task TEXT NOT NULL,
    status TEXT DEFAULT 'PENDING',   -- PENDING, IN_PROGRESS, COMPLETED, FAILED, SKIPPED, AWAITING_AUTHORIZATION
    result_summary TEXT,
    reflection TEXT,
    requires_approval INTEGER DEFAULT 0,
    approval_status TEXT,            -- AWAITING_AUTHORIZATION, APPROVED, REJECTED
    pending_command TEXT,            -- Comando esperando aprobación
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME
);
```

#### 4.1.6 Auditoría de Comandos

```sql
CREATE TABLE command_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    mission_id TEXT,
    objective_id INTEGER,
    command TEXT NOT NULL,
    risk_level TEXT NOT NULL,        -- safe, low, medium, high, critical
    requires_approval INTEGER DEFAULT 0,
    reason TEXT,
    status TEXT DEFAULT 'PENDING',   -- PENDING, ALLOWED, EXECUTING, COMPLETED, FAILED
    result_summary TEXT,
    approved_by TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    executed_at DATETIME
);
```

#### 4.1.7 Resúmenes de Tools

```sql
CREATE TABLE tool_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL,
    tool_call_id TEXT NOT NULL,
    original_output TEXT NOT NULL,
    original_length INTEGER NOT NULL,
    summary TEXT NOT NULL,
    compression_ratio REAL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 4.2 Funciones Principales de Base de Datos

#### 4.2.1 Reconstrucción de Thread

```python
def reconstruct_thread(leaf_id: int) -> List[Dict]:
    """
    Reconstruye la rama desde un mensaje hoja hasta la raíz.
    Returns: [system, msg1, msg2, ..., leaf]
    """
    thread = []
    current_id = leaf_id
    
    while current_id is not None:
        msg = get_message(current_id)
        thread.insert(0, msg)  # Insertar al principio
        current_id = msg['parent_id']
    
    return thread
```

#### 4.2.2 Truncado Inteligente de Mensajes

```python
def smart_truncate_messages(messages: List[Dict], max_messages: int) -> List[Dict]:
    """
    Trunca mensajes preservando pares tool_call/tool_response.
    
    REGLAS:
    1. Siempre preservar el system prompt
    2. Nunca separar assistant con tool_calls de sus tool responses
    3. Eliminar bloques completos, no mensajes sueltos
    """
```

**Problema que resuelve:**
```
# MAL: Si truncamos aquí, Gemini falla
[assistant con tool_calls: id="tc_123"]
[tool response: tool_call_id="tc_123"]  ← Huérfano si se elimina el anterior

# BIEN: Truncado inteligente mantiene el bloque completo o lo elimina entero
```

#### 4.2.3 Formato para LLM

```python
def get_conversation_for_llm(leaf_id: int) -> List[Dict]:
    """
    Reconstruye el historial en formato OpenAI.
    - Trunca respuestas de tools muy largas
    - Añade 'name' a tool responses (requerido por Gemini)
    - Aplica truncado inteligente
    """
```

---

## 5. Modelos Pydantic (models.py)

### 5.1 Request de Chat

```python
class ChatRequest(BaseModel):
    # Autenticación
    provider: Literal["openai", "google", "deepseek", "openrouter", "anthropic", "ollama"]
    api_key: str
    model_id: str
    
    # Contexto
    conversation_id: Optional[str] = None
    parent_message_id: Optional[int] = None
    user_message: str
    
    # Regeneración
    regenerate: bool = False
    
    # Parámetros avanzados
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None
    
    # Configuración
    tools: Optional[List[Dict]] = None
    stream: bool = False
    system_prompt: Optional[str] = None
    
    # Modo agéntico
    auto_summarize: bool = True
    summarizer_model: Optional[str] = None
```

### 5.2 Otros Modelos Importantes

```python
class MessageResponse(BaseModel):
    id: int
    conversation_id: str
    parent_id: Optional[int]
    role: str
    content: Optional[str]
    tool_calls: Optional[str]
    tool_call_id: Optional[str]
    model_used: Optional[str]
    created_at: str

class TreeNode(BaseModel):
    id: int
    parent_id: Optional[int]
    role: str
    content_preview: Optional[str]
    children_count: int
```

---

## 6. Endpoint de Chat (routes/chat.py)

### 6.1 Flujo Principal

```
┌────────────┐     POST /chat      ┌──────────────────────────────────────┐
│  Frontend  │ ────────────────────►│                                      │
└────────────┘                     │  1. Crear/obtener conversación       │
                                   │  2. Determinar mensaje padre         │
                                   │  3. Guardar mensaje de usuario       │
                                   │  4. Detectar modo agéntico           │
                                   │  5. Reconstruir contexto             │
                                   │  6. Llamar al LLM                    │
                                   │  7. Procesar tool_calls              │
                                   │  8. Loop hasta finish_reason="stop"  │
                                   │  9. Guardar respuesta                │
                                   └──────────────────────────────────────┘
```

### 6.2 Factory de Clientes

```python
def get_client(provider: str, api_key: str) -> AsyncOpenAI:
    if provider == "openai":
        return AsyncOpenAI(api_key=api_key)
    
    elif provider == "google":
        return AsyncOpenAI(
            api_key=api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )
    
    elif provider == "deepseek":
        return AsyncOpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    
    elif provider == "openrouter":
        return AsyncOpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
    
    elif provider == "ollama":
        return AsyncOpenAI(api_key="ollama", base_url=f"{api_key}/v1")
    
    elif provider == "anthropic":
        # Anthropic usa su propio SDK, pero se maneja compatible
        ...
```

### 6.3 Detección de Modo Agéntico

```python
AGENTIC_KEYWORDS = [
    r"de forma autónoma", r"automáticamente",
    r"pentesting completo", r"assessment completo",
    r"accede a root", r"consigue root",
    r"compromete el sistema",
    r"autonomous(ly)?", r"full assessment",
    r"get root", r"complete pentest",
]

AGENTIC_PATTERN = re.compile("|".join(AGENTIC_KEYWORDS), re.IGNORECASE)

def is_agentic_request(user_message: str) -> bool:
    return bool(AGENTIC_PATTERN.search(user_message))
```

### 6.4 System Prompt Agéntico

Cuando se detecta modo agéntico, se inyecta un system prompt especializado:

```python
AGENTIC_SYSTEM_PROMPT = """You are an **Autonomous Offensive Security Agent**...

## CRITICAL: AGENTIC MISSION PROTOCOL

### STEP 1: CREATE A MISSION PLAN
Before ANY technical action, call `manage_mission` with action="create"

### STEP 2: EXECUTE WITH STATE TRACKING
For EACH objective:
a) Mark IN_PROGRESS before starting
b) Execute the technical commands
c) Mark COMPLETED/FAILED immediately after with results

### STEP 3: ADAPT DYNAMICALLY
If you discover unexpected information, modify your plan

### STEP 4: COMPLETE THE MISSION
When done: {"action": "complete", "mission_id": "...", "status": "COMPLETED"}
"""
```

### 6.5 Ejecución de Tool Calls

```python
async def execute_tool_call(tool_call: Dict, conversation_id: str, leaf_id: int = None) -> str:
    function_name = tool_call["function"]["name"]
    function_args = json.loads(tool_call["function"]["arguments"])
    
    if function_name == "execute_command":
        # 1. Analizar riesgo del comando
        analysis = analyze_command(command)
        
        # 2. Si requiere aprobación, pausar
        if analysis["requires_approval"]:
            return json.dumps({
                "status": "AWAITING_AUTHORIZATION",
                "risk_level": analysis["risk_level"],
                "command": command,
                ...
            })
        
        # 3. Ejecutar en sandbox
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{SANDBOX_URL}/execute", json=payload)
            result = response.json()
        
        # 4. Si queda en background, registrar para seguimiento
        if result.get("status") == "running":
            db.add_pending_job(job_id, conversation_id, leaf_id, command, tool_call_id)
        
        return formatted_result
    
    elif function_name == "manage_mission":
        # Gestión de misiones autónomas
        ...
    
    elif function_name == "check_job_status":
        # Consulta de estado de jobs
        ...
```

### 6.6 Streaming con SSE

```python
async def stream_chat_response(...):
    """Generador asíncrono para Server-Sent Events."""
    
    stream = await client.chat.completions.create(**params, stream=True)
    
    async for chunk in stream:
        delta = chunk.choices[0].delta
        
        if delta.content:
            yield f"event: message\ndata: {json.dumps({'type': 'content', 'chunk': delta.content})}\n\n"
        
        if delta.tool_calls:
            yield f"event: tool_call\ndata: {json.dumps({'type': 'tool_call', 'tool_call': tc_dict})}\n\n"
    
    # Loop de tool calls
    while has_tool_calls and iteration < max_iterations:
        # Ejecutar tools
        for tc in tool_calls:
            yield f"event: tool_executing\ndata: ...\n\n"
            result = await execute_tool_call(tc, ...)
            yield f"event: tool_result\ndata: ...\n\n"
        
        # Continuar conversación
        stream = await client.chat.completions.create(...)
        ...
    
    # Finalizar
    yield f"event: done\ndata: {json.dumps(final_data)}\n\n"
```

### 6.7 Auto-Summarize

Para outputs muy largos (>2000 chars por defecto), el sistema genera un resumen:

```python
SUMMARIZE_THRESHOLD = 2000  # Caracteres mínimos para resumir

async def summarize_tool_output(output: str, client: AsyncOpenAI, model_id: str) -> Dict:
    """Genera un resumen del output manteniendo información técnica clave."""
    
    prompt = f"""Summarize this security tool output. Keep:
    - IPs, ports, versions
    - Vulnerabilities found
    - Critical errors
    ...
    
    OUTPUT:
    {output}
    """
    
    response = await client.chat.completions.create(model=model_id, messages=[...])
    return {"summary": response.choices[0].message.content, "compressed": True}
```

---

## 7. Sistema de Seguridad (security.py)

### 7.1 Niveles de Riesgo

```python
class RiskLevel(Enum):
    SAFE = "safe"           # Comandos de reconocimiento pasivo
    LOW = "low"             # Escaneos ligeros
    MEDIUM = "medium"       # Enumeración activa
    HIGH = "high"           # Exploits, brute-force
    CRITICAL = "critical"   # Shells reversos, post-explotación
```

### 7.2 Patrones de Comandos Peligrosos

```python
DANGEROUS_PATTERNS = [
    # CRITICAL - Siempre requiere aprobación
    (r"msfconsole", RiskLevel.CRITICAL, "Metasploit Framework"),
    (r"nc\s+.*-e", RiskLevel.CRITICAL, "Netcat reverse shell"),
    (r"bash\s+-i\s+>&", RiskLevel.CRITICAL, "Bash reverse shell"),
    (r"rm\s+-rf\s+/", RiskLevel.CRITICAL, "Eliminación recursiva"),
    
    # HIGH - Requiere aprobación por defecto
    (r"hydra", RiskLevel.HIGH, "Brute-force de credenciales"),
    (r"sqlmap.*--dump", RiskLevel.HIGH, "Dumping de base de datos"),
    (r"hashcat", RiskLevel.HIGH, "Password cracking GPU"),
    
    # MEDIUM - Advertencia pero se puede ejecutar
    (r"nmap\s+.*-A", RiskLevel.MEDIUM, "Aggressive scan"),
    (r"nikto", RiskLevel.MEDIUM, "Web vulnerability scanner"),
    (r"sqlmap\s+", RiskLevel.MEDIUM, "SQL injection testing"),
]
```

### 7.3 Whitelist de Comandos Seguros

```python
SAFE_PATTERNS = [
    r"^whoami$",
    r"^id$",
    r"^ls\s+",
    r"^cat\s+",
    r"^nmap\s+.*-sn",  # Solo ping scan
]
```

### 7.4 Análisis de Comandos

```python
def analyze_command(command: str) -> Dict:
    """
    Returns:
    {
        "risk_level": "high",
        "requires_approval": True,
        "matched_patterns": [...],
        "reason": "Brute-force de credenciales"
    }
    """
```

---

## 8. Sistema de Scoring (scoring.py)

### 8.1 Fuentes de Datos

1. **LMArena Leaderboard** (online): CSV de fboulnois/llm-leaderboard-csv
2. **Fallback local**: `fallbackRank.csv` si no hay conexión

### 8.2 Algoritmo de Matching

```python
def assign_score(model_name: str) -> int:
    """
    Prioridad de búsqueda:
    1. Match exacto
    2. Match normalizado (sin fechas)
    3. Herencia de modelos nuevos (gpt-5 → gpt-4o + 100)
    4. Match por familia (gpt-3.5-turbo-instruct → gpt-3.5-turbo)
    5. Fuzzy match (>85% similaridad)
    6. Return 0 si no hay match
    """
```

### 8.3 Herencia de Modelos Nuevos

```python
MODEL_INHERITANCE = {
    r"gpt-5": ("ChatGPT-4o-latest", 100),
    r"o1-pro": ("o1-preview", 50),
    r"gemini-3": ("gemini-2.5-pro", 100),
    r"claude-4": ("claude-3.5-sonnet", 100),
}
```

---

## 9. Monitor de Jobs (job_monitor.py)

### 9.1 Propósito

Polling asíncrono de jobs en background del sandbox para:
1. Detectar cuando terminan
2. Guardar el resultado en la BD
3. Crear mensaje tool en la conversación
4. Notificar vía callback

### 9.2 Loop Principal

```python
async def poll_pending_jobs():
    pending = db.get_pending_jobs()
    
    for job in pending:
        result = await check_job_status(job['job_id'])
        
        if result.get("status") == "finished":
            # Guardar resultado
            db.complete_pending_job(job_id, formatted_result)
            
            # Crear mensaje tool en la conversación
            tool_msg_id = db.add_message(
                conversation_id=conv_id,
                role="tool",
                content=f"[RESULTADO DE JOB EN SEGUNDO PLANO]\n{formatted_result}",
                parent_id=current_leaf_id,
                tool_call_id=tool_call_id
            )
            
            # Actualizar leaf activo
            db.update_conversation_leaf(conv_id, tool_msg_id)
```

### 9.3 Intervalo

```python
async def job_monitor_loop(interval: float = 5.0):
    while True:
        await poll_pending_jobs()
        await asyncio.sleep(interval)
```

---

## 10. Endpoints REST por Módulo

### 10.1 Health (routes/health.py)

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/health` | GET | Estado del servidor |
| `/health/keys` | POST | Validar API keys de todos los proveedores |
| `/ollama/models` | POST | Obtener modelos disponibles en un servidor Ollama |

### 10.2 Conversations (routes/conversations.py)

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/conversations` | GET | Listar conversaciones |
| `/conversations` | POST | Crear conversación |
| `/conversations/{id}` | GET | Obtener metadatos |
| `/conversations/{id}` | DELETE | Eliminar conversación |
| `/conversations/{id}/thread` | GET | Obtener rama activa |
| `/conversations/{id}/tree` | GET | Obtener árbol completo |
| `/conversations/{id}/active-leaf` | PATCH | Cambiar rama activa |
| `/conversations/{id}/pin` | POST | Fijar/desfijar conversación |
| `/conversations/{id}/title` | PATCH | Renombrar conversación |

### 10.3 Chat (routes/chat.py)

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/chat` | POST | Enviar mensaje (stream/normal) |

### 10.4 Messages (routes/messages.py)

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/messages/{id}` | GET | Obtener mensaje |
| `/messages/{id}/edit` | POST | Editar mensaje (crear rama) |

### 10.5 Jobs (routes/jobs.py)

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/jobs` | GET | Listar jobs pendientes |
| `/jobs/{id}/notify` | POST | Marcar job como notificado |
| `/jobs/stream/{conv_id}` | GET | SSE de notificaciones de jobs |

### 10.6 Missions (routes/missions.py)

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/missions` | POST | Crear misión |
| `/missions/{id}` | GET | Estado de misión |
| `/missions/{id}/phase` | PATCH | Actualizar fase |
| `/missions/{id}/complete` | POST | Completar misión |
| `/missions/{id}/objectives` | GET | Listar objetivos |
| `/missions/objectives/{id}` | PATCH | Actualizar objetivo |
| `/missions/conversation/{id}/active` | GET | Misión activa de conversación |
| `/missions/approvals` | GET | Aprobaciones pendientes |
| `/missions/approvals/{id}` | POST | Aprobar/rechazar comando |

### 10.7 Models Discovery (routes_legacy.py)

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/models/discover` | POST | Descubrir modelos disponibles |

---

## 11. Flujo de una Petición de Chat con Tools

```
                    ┌────────────────────────────────────────────────────────┐
                    │                    POST /chat                          │
                    └────────────────────────────────────────────────────────┘
                                           │
                                           ▼
                    ┌────────────────────────────────────────────────────────┐
                    │  1. Validar request (provider, api_key, model_id)      │
                    │  2. Crear conversación si es nueva                     │
                    │  3. Determinar parent_id (active_leaf o especificado)  │
                    │  4. Guardar mensaje de usuario en BD                   │
                    └────────────────────────────────────────────────────────┘
                                           │
                                           ▼
                    ┌────────────────────────────────────────────────────────┐
                    │  5. Detectar modo agéntico (keywords)                  │
                    │  6. Si agéntico: inyectar system prompt especial       │
                    │  7. Si hay misión activa: añadir contexto al prompt    │
                    └────────────────────────────────────────────────────────┘
                                           │
                                           ▼
                    ┌────────────────────────────────────────────────────────┐
                    │  8. Reconstruir contexto (get_conversation_for_llm)    │
                    │     - Truncado inteligente si > 30 mensajes            │
                    │     - Añadir 'name' a tool responses (Gemini)          │
                    └────────────────────────────────────────────────────────┘
                                           │
                                           ▼
                    ┌────────────────────────────────────────────────────────┐
                    │  9. Llamar al LLM (stream=True)                        │
                    │     - yield chunks de contenido                        │
                    │     - yield tool_calls cuando llegan                   │
                    └────────────────────────────────────────────────────────┘
                                           │
                           finish_reason == "tool_calls"?
                                           │
                         ┌─────────────────┴─────────────────┐
                         │ SÍ                                │ NO
                         ▼                                   ▼
    ┌────────────────────────────────────────┐    ┌─────────────────────┐
    │  10. Para cada tool_call:              │    │  Guardar respuesta  │
    │      a) Analizar riesgo                │    │  yield done event   │
    │      b) Si HIGH/CRITICAL: pausar       │    │  FIN                │
    │      c) Ejecutar en sandbox            │    └─────────────────────┘
    │      d) Si background: registrar job   │
    │      e) Auto-summarize si > 2000 chars │
    │      f) Guardar mensaje tool en BD     │
    │      g) yield tool_result event        │
    └────────────────────────────────────────┘
                         │
                         ▼
    ┌────────────────────────────────────────────────────────────────────┐
    │  11. LOOP: Llamar al LLM con los resultados de tools              │
    │      - Máximo 15 iteraciones                                      │
    │      - Repetir hasta finish_reason != "tool_calls"                │
    │      - Si AWAITING_AUTHORIZATION: pausar loop                     │
    └────────────────────────────────────────────────────────────────────┘
                         │
                         ▼
    ┌────────────────────────────────────────────────────────────────────┐
    │  12. Guardar respuesta final del asistente                        │
    │  13. Actualizar active_leaf_id                                    │
    │  14. yield done event con IDs de mensajes                         │
    └────────────────────────────────────────────────────────────────────┘
```

---

## 12. Modo Agéntico: Misiones

### 12.1 Estados de Misión

```
PLANNING → IN_PROGRESS → COMPLETED
                       → FAILED
                       → CANCELLED
```

### 12.2 Estados de Objetivo

```
PENDING → IN_PROGRESS → COMPLETED
                      → FAILED
                      → SKIPPED
                      → AWAITING_AUTHORIZATION
```

### 12.3 Flujo de Aprobación

```
1. LLM ejecuta comando peligroso (hydra, msfconsole...)
2. security.py detecta riesgo HIGH/CRITICAL
3. Se marca objetivo como AWAITING_AUTHORIZATION
4. Se registra en command_audit
5. Frontend muestra ApprovalDialog
6. Usuario aprueba/rechaza
7. Si aprueba: se ejecuta y continúa
8. Si rechaza: se marca como SKIPPED
```

### 12.4 Tool `manage_mission`

El LLM tiene acceso a esta tool para gestionar su propia misión:

```python
# Crear misión
{"action": "create", "goal": "...", "objectives": [...]}

# Actualizar objetivo
{"action": "update_objective", "objective_id": 1, "status": "COMPLETED", "result": "..."}

# Cambiar fase
{"action": "update_phase", "mission_id": "...", "phase": "Exploitation"}

# Completar
{"action": "complete", "mission_id": "...", "status": "COMPLETED"}

# Consultar estado
{"action": "get_status"}

# Modificar plan dinámicamente
{"action": "modify_objectives", "modifications": [{"type": "insert", "after_id": 2, "task": "..."}]}
```

---

## 13. Proveedores Soportados

| Proveedor | Base URL | Notas |
|-----------|----------|-------|
| OpenAI | `https://api.openai.com/v1` | SDK nativo |
| Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai/` | API compatible OpenAI |
| Anthropic | SDK propio | `AsyncAnthropic` |
| DeepSeek | `https://api.deepseek.com` | API compatible OpenAI |
| OpenRouter | `https://openrouter.ai/api/v1` | Acceso a +200 modelos |
| Ollama | `http://localhost:11434/v1` | Modelos locales |

---

## 14. Configuración

### 14.1 Variables de Entorno

El backend no usa variables de entorno directamente; las API keys se reciben por request.

### 14.2 Constantes Configurables

```python
# database.py
MAX_MESSAGES_FOR_LLM = 30
MAX_TOOL_RESPONSE_LENGTH = 2000

# chat.py
SANDBOX_URL = "http://localhost:5000"
SUMMARIZE_THRESHOLD = 2000

# job_monitor.py
DEFAULT_INTERVAL = 5.0  # segundos
```

---

## 15. Manejo de Errores

### 15.1 Códigos de Error

```python
ERROR_CODES = {
    "INVALID_API_KEY": "La API Key proporcionada es inválida",
    "RATE_LIMITED": "Has excedido el límite de peticiones",
    "MODEL_NOT_FOUND": "El modelo solicitado no existe",
    "CONVERSATION_NOT_FOUND": "La conversación no existe",
    "MESSAGE_NOT_FOUND": "El mensaje no existe",
    "PROVIDER_ERROR": "Error del proveedor de LLM",
    "NETWORK_ERROR": "Error de conexión con el proveedor",
    "DATABASE_ERROR": "Error en la base de datos",
    "INTERNAL_ERROR": "Error interno del servidor",
    "STREAM_ERROR": "Error durante el streaming"
}
```

### 15.2 Formato de Error

```json
{
  "error": true,
  "code": "RATE_LIMITED",
  "message": "Has excedido el límite de peticiones",
  "details": {"retry_after": 60}
}
```

---

## 16. Dependencias Python

```
fastapi
uvicorn
pydantic
sqlite3  # Built-in
openai   # SDK oficial
anthropic
httpx    # Cliente HTTP async
pandas   # Para CSV de rankings
colorama # Colores en logs
thefuzz  # Fuzzy matching de modelos
gitpython  # No usado en backend, pero importado
```

---

## 17. Ejecución

```bash
cd LLM/backend
uvicorn main:app --host 0.0.0.0 --port 4000 --reload
```

El servidor estará disponible en:
- API: `http://localhost:4000`
- Docs: `http://localhost:4000/docs`
- ReDoc: `http://localhost:4000/redoc`
