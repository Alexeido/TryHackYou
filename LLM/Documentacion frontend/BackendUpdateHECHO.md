# 🔧 Backend Updates - Cambios Necesarios en FastAPI

> **Objetivo:** Documentar todas las modificaciones necesarias en el backend Python para soportar la nueva arquitectura del frontend.

---

## 1. Nueva Funcionalidad: Gestión de Conversaciones

El backend actual solo tiene `/models/discover` y `/chat`. Necesitamos endpoints para **persistir el historial**.

### Base de Datos SQLite - Sistema de Árbol

Crear archivo `database.py`:

```python
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

DB_PATH = Path(__file__).parent / "chat_history.db"

def init_db():
    """Crea las tablas con estructura de árbol."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Tabla de conversaciones
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            system_prompt TEXT,
            active_leaf_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Tabla de mensajes con estructura de árbol
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            parent_id INTEGER,
            role TEXT NOT NULL,
            content TEXT,
            tool_calls TEXT,
            tool_call_id TEXT,
            model_used TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
            FOREIGN KEY (parent_id) REFERENCES messages(id) ON DELETE CASCADE
        )
    """)
    
    # Índices para optimizar queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_parent ON messages(parent_id)")
    
    conn.commit()
    conn.close()

def get_db_connection():
    """Context manager para conexión a BD."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def reconstruct_thread(leaf_id: int) -> List[Dict]:
    """
    Reconstruye la rama desde un mensaje hoja hasta la raíz.
    Devuelve lista ordenada [system, msg1, msg2, ..., leaf]
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Obtener mensaje hoja
    current_id = leaf_id
    thread = []
    
    while current_id is not None:
        cursor.execute("""
            SELECT id, parent_id, role, content, tool_calls, tool_call_id, model_used, created_at
            FROM messages WHERE id = ?
        """, (current_id,))
        
        msg = cursor.fetchone()
        if not msg:
            break
            
        thread.insert(0, dict(msg))  # Insertar al principio
        current_id = msg['parent_id']
    
    conn.close()
    return thread

def get_tree_structure(conversation_id: str) -> Dict:
    """
    Obtiene la estructura completa del árbol para mostrar ramificaciones.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT m.id, m.parent_id, m.role, 
               COUNT(c.id) as children_count
        FROM messages m
        LEFT JOIN messages c ON c.parent_id = m.id
        WHERE m.conversation_id = ?
        GROUP BY m.id
        ORDER BY m.created_at
    """, (conversation_id,))
    
    nodes = [dict(row) for row in cursor.fetchall()]
    
    # Obtener active_leaf
    cursor.execute("SELECT active_leaf_id FROM conversations WHERE id = ?", (conversation_id,))
    active_leaf = cursor.fetchone()['active_leaf_id']
    
    conn.close()
    
    return {
        "nodes": nodes,
        "active_leaf": active_leaf
    }
```

---

## 2. Nuevos Endpoints Requeridos

### 2.1. Crear Conversación

```
POST /conversations
```

**Request Body:**
```json
{
  "title": "Escaneo de puertos"  // Opcional, auto-genera si no se envía
}
```

**Response:**
```json
{
  "id": "conv_abc123",
  "title": "Escaneo de puertos",
  "created_at": "2025-12-17T10:30:00Z",
  "updated_at": "2025-12-17T10:30:00Z"
}
```

**Notas:**
- Si no se envía `title`, usar el primer mensaje o "Nueva conversación"
- Generar `id` con UUID o nanoid

---

### 2.2. Listar Conversaciones

```
GET /conversations
```

**Query Params:**
- `limit` (int, default: 50) - Cantidad máxima
- `offset` (int, default: 0) - Para paginación

**Response:**
```json
{
  "total": 42,
  "conversations": [
    {
      "id": "conv_abc123",
      "title": "Escaneo de puertos",
      "created_at": "2025-12-17T10:30:00Z",
      "updated_at": "2025-12-17T12:45:00Z",
      "message_count": 8
    },
    ...
  ]
}
```

**Notas:**
- Ordenar por `updated_at` descendente (más reciente primero)
- Incluir `message_count` para mostrar info en sidebar

---

### 2.3. Obtener Historial de Conversación

```
GET /conversations/{conversation_id}
```

**Response:**
```json
{
  "id": "conv_abc123",
  "title": "Escaneo de puertos",
  "created_at": "2025-12-17T10:30:00Z",
  "updated_at": "2025-12-17T12:45:00Z",
  "messages": [
    {
      "id": 1,
      "role": "user",
      "content": "Escanea el puerto 80 de la IP 10.5.0.3",
      "tool_calls": null,
      "created_at": "2025-12-17T10:30:05Z"
    },
    {
      "id": 2,
      "role": "assistant",
      "content": "Voy a ejecutar un escaneo con nmap...",
      "tool_calls": [{"id": "call_123", "type": "function", "function": {"name": "run_command", "arguments": "{\"cmd\": \"nmap -p 80 10.5.0.3\"}"}}],
      "created_at": "2025-12-17T10:30:08Z"
    },
    ...
  ]
}
```

---

### 2.4. Eliminar Conversación

```
DELETE /conversations/{conversation_id}
```

**Response:**
```json
{
  "success": true,
  "deleted_id": "conv_abc123"
}
```

**Notas:**
- Eliminar en cascada todos los mensajes asociados
- Devolver 404 si no existe

---

### 2.5. Actualizar Título de Conversación

```
PATCH /conversations/{conversation_id}
```

**Request Body:**
```json
{
  "title": "Nuevo título del chat"
}
```

**Response:**
```json
{
  "id": "conv_abc123",
  "title": "Nuevo título del chat",
  "updated_at": "2025-12-17T14:00:00Z"
}
```

---

## 3. Modificaciones al Endpoint `/chat`

### Cambios Requeridos

El endpoint actual `/chat` necesita:

1. **Aceptar `conversation_id`** (opcional)
2. **Guardar mensajes automáticamente**
3. **Actualizar `updated_at` de la conversación**

### Nuevo Request Model

```python
class ChatRequest(BaseModel):
    provider: Literal["openai", "google", "deepseek", "openrouter"]
    api_key: str
    model_id: str
    messages: List[Message]
    tools: Optional[List[Dict[str, Any]]] = None
    
    # NUEVOS CAMPOS
    conversation_id: Optional[str] = None  # Si es None, crea nueva conversación
    save_history: bool = True  # Permite desactivar guardado (útil para tests)
```

### Nuevo Response Model

```python
class ChatResponse(BaseModel):
    role: str
    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    finish_reason: str
    
    # NUEVOS CAMPOS
    conversation_id: str  # ID de la conversación (nuevo o existente)
    message_id: int  # ID del mensaje guardado
```

### Lógica de Guardado

```python
@app.post("/chat", response_model=ChatResponse)
async def chat_completion(req: ChatRequest):
    # 1. Si no hay conversation_id, crear nueva conversación
    if not req.conversation_id:
        conv_id = create_conversation(title=extract_title(req.messages[-1].content))
    else:
        conv_id = req.conversation_id
    
    # 2. Guardar mensaje del usuario
    if req.save_history:
        save_message(conv_id, req.messages[-1])
    
    # 3. Llamar al LLM (código existente)
    response = await client.chat.completions.create(...)
    
    # 4. Guardar respuesta del asistente
    if req.save_history:
        msg_id = save_message(conv_id, response.message)
        update_conversation_timestamp(conv_id)
    
    # 5. Devolver respuesta con IDs
    return ChatResponse(
        ...
        conversation_id=conv_id,
        message_id=msg_id
    )
```

---

## 4. Mejoras en Manejo de Errores

### Estructura de Error Estandarizada

Actualmente los errores devuelven strings. Necesitamos estructura consistente:

```python
class ErrorResponse(BaseModel):
    error: bool = True
    code: str  # Código único para el frontend
    message: str  # Mensaje legible
    details: Optional[Dict[str, Any]] = None

# Códigos de error
ERROR_CODES = {
    "INVALID_API_KEY": "La API Key proporcionada es inválida",
    "RATE_LIMITED": "Has excedido el límite de peticiones",
    "MODEL_NOT_FOUND": "El modelo solicitado no existe",
    "PROVIDER_ERROR": "Error del proveedor de LLM",
    "NETWORK_ERROR": "Error de conexión con el proveedor",
    "CONVERSATION_NOT_FOUND": "La conversación no existe",
    "INTERNAL_ERROR": "Error interno del servidor"
}
```

### Detección de Errores Específicos

```python
@app.post("/chat")
async def chat_completion(req: ChatRequest):
    try:
        client = get_client(req.provider, req.api_key)
        response = await client.chat.completions.create(...)
        return response
        
    except AuthenticationError as e:
        raise HTTPException(
            status_code=401,
            detail=ErrorResponse(
                code="INVALID_API_KEY",
                message=f"API Key inválida para {req.provider}",
                details={"provider": req.provider}
            ).model_dump()
        )
        
    except RateLimitError as e:
        raise HTTPException(
            status_code=429,
            detail=ErrorResponse(
                code="RATE_LIMITED",
                message="Límite de peticiones excedido",
                details={"retry_after": e.retry_after}
            ).model_dump()
        )
        
    except NotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                code="MODEL_NOT_FOUND",
                message=f"Modelo {req.model_id} no encontrado",
                details={"model": req.model_id}
            ).model_dump()
        )
```

---

## 5. Streaming

### Endpoint de Streaming

```
POST /chat/stream
```

**Tecnología:** Server-Sent Events (SSE)

**Response Type:** `text/event-stream`

**Formato de Eventos:**

```
event: message
data: {"chunk": "Voy a ", "done": false}

event: message
data: {"chunk": "ejecutar ", "done": false}

event: message
data: {"chunk": "nmap...", "done": false}

event: done
data: {"conversation_id": "conv_123", "message_id": 5, "finish_reason": "stop"}

event: error
data: {"code": "RATE_LIMITED", "message": "..."}
```

### Implementación Básica

```python
from fastapi.responses import StreamingResponse
import asyncio

@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    async def generate():
        client = get_client(req.provider, req.api_key)
        
        stream = await client.chat.completions.create(
            model=req.model_id,
            messages=[m.model_dump() for m in req.messages],
            stream=True  # ← Activa streaming
        )
        
        full_content = ""
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                text = chunk.choices[0].delta.content
                full_content += text
                yield f"event: message\ndata: {json.dumps({'chunk': text, 'done': False})}\n\n"
        
        # Guardar mensaje completo
        msg_id = save_message(req.conversation_id, full_content)
        yield f"event: done\ndata: {json.dumps({'message_id': msg_id, 'done': True})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )
```

---

## 6. Endpoint de Health Check

Útil para que el frontend detecte si el backend está vivo:

```
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "5.0.0",
  "database": "connected",
  "timestamp": "2025-12-17T10:00:00Z"
}
```

---

## 7. Resumen de Cambios

### Archivos a Crear

| Archivo | Descripción |
|:--------|:------------|
| `database.py` | Conexión SQLite y funciones CRUD |
| `models_db.py` | Modelos Pydantic para conversaciones |
| `errors.py` | Clases de error estandarizadas |

### Archivos a Modificar

| Archivo | Cambios |
|:--------|:--------|
| `main.py` | Añadir endpoints de conversaciones, modificar `/chat` |

### Nuevos Endpoints

| Método | Ruta | Prioridad |
|:-------|:-----|:----------|
| `GET` | `/health` | 🔴 Alta |
| `POST` | `/conversations` | 🔴 Alta |
| `GET` | `/conversations` | 🔴 Alta |
| `GET` | `/conversations/{id}` | 🔴 Alta |
| `DELETE` | `/conversations/{id}` | 🟡 Media |
| `PATCH` | `/conversations/{id}` | 🟡 Media |
| `POST` | `/chat/stream` | 🔴 Alta |

### Modificaciones a Endpoints Existentes

| Endpoint | Cambio |
|:---------|:-------|
| `POST /chat` | Añadir `conversation_id`, guardar historial |
