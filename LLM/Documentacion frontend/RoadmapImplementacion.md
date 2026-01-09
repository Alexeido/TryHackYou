# 🗺️ Roadmap de Implementación - Frontend + Backend

> **Objetivo:** Definir el orden óptimo de tareas para conseguir un frontend funcional conectado al backend.

---

## Visión General

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FASES DE IMPLEMENTACIÓN                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   FASE 0          FASE 1           FASE 2           FASE 3                  │
│   Backend DB      Frontend Base    Integración      Polish                  │
│   ────────────    ─────────────    ───────────      ──────                  │
│   [2-3 días]      [3-4 días]       [2-3 días]       [1-2 días]              │
│                                                                              │
│   ┌─────────┐     ┌─────────┐     ┌─────────┐      ┌─────────┐             │
│   │ SQLite  │     │ Stores  │     │ API     │      │ Stream  │             │
│   │ CRUD    │────▶│ Zustand │────▶│ Connect │─────▶│ (Opt)   │             │
│   │ Health  │     │ Modals  │     │ Errors  │      │ Docker  │             │
│   └─────────┘     └─────────┘     └─────────┘      └─────────┘             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## FASE 0: Preparación del Backend (Primero)

> **¿Por qué primero?** El frontend necesita endpoints reales para funcionar. Mejor tenerlos listos antes de conectar.

### Tarea 0.1: Health Check Mejorado
**Prioridad:** 🔴 Crítica  
**Tiempo estimado:** 30-45 min  
**Archivo:** `main.py`

**Descripción:** Dos endpoints de health check:

1. **GET `/health`** - Check básico (servidor vivo)
```python
@app.get("/health")
def health_check():
    return {"status": "healthy", "version": "5.0.0", "database": "connected"}
```

2. **POST `/health/keys`** - Validación de API Keys del usuario
```python
@app.post("/health/keys")
async def validate_api_keys(req: KeysValidationRequest):
    # Intenta llamada mínima a cada proveedor
    return {
        "openai": {"valid": True/False, "error": None/"message"},
        "google": {"valid": True/False, "error": None/"message"},
        "deepseek": {"valid": True/False, "error": None/"message"},
        "openrouter": {"valid": True/False, "error": None/"message"}
    }
```

**Subtareas:**
1. [ ] Endpoint GET `/health` básico
2. [ ] Modelo `KeysValidationRequest` con las 4-5 keys opcionales
3. [ ] Lógica de validación: llamada mínima a cada API (list models o similar)
4. [ ] Captura de errores de autenticación y timeout
5. [ ] Response estructurado con estado por proveedor

**Criterio de éxito:** 
- `curl http://localhost:8000/health` devuelve JSON
- POST a `/health/keys` con keys válidas devuelve `valid: true`
- POST con key inválida devuelve `valid: false` y mensaje de error

---

### Tarea 0.2: Base de Datos SQLite con Árbol de Mensajes
**Prioridad:** 🔴 Crítica  
**Tiempo estimado:** 2-3 horas  
**Archivos:** Crear `database.py`

**Descripción:** Sistema de árbol de mensajes para soportar ramificaciones (edición de mensajes previos).

**Estructura de Tablas:**

```sql
-- Tabla de conversaciones
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    system_prompt TEXT,  -- System message inicial de esta conversación
    active_leaf_id INTEGER,  -- ID del último mensaje de la rama activa
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de mensajes (árbol)
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    parent_id INTEGER,  -- NULL = mensaje raíz (system prompt)
    role TEXT NOT NULL,  -- user, assistant, system, tool
    content TEXT,
    tool_calls TEXT,  -- JSON: [{"id": "call_123", "function": {...}}]
    tool_call_id TEXT,  -- Para respuestas de tool (vincula con tool_call)
    model_used TEXT,  -- Qué modelo generó esta respuesta (para assistant)
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_id) REFERENCES messages(id) ON DELETE CASCADE
);

-- Índices para optimizar queries
CREATE INDEX idx_messages_conversation ON messages(conversation_id);
CREATE INDEX idx_messages_parent ON messages(parent_id);
```

**Lógica del Árbol:**
- **System prompt:** Primer mensaje con `parent_id = NULL` y `role = system`
- **Rama lineal:** Cada mensaje apunta a su padre mediante `parent_id`
- **Ramificación:** Cuando editas mensaje 4, creas nuevo mensaje 4b con mismo `parent_id` que 4a
- **Rama activa:** `active_leaf_id` en `conversations` indica qué hoja está seleccionada
- **Reconstruir conversación:** Desde `active_leaf_id` hacia atrás (parent → parent → parent) hasta llegar a NULL

**Subtareas:**
1. [ ] Crear función `init_db()` con las tablas y índices
2. [ ] Función `get_db_connection()` con context manager
3. [ ] Función `reconstruct_thread(leaf_id)` - Reconstruye rama desde hoja hasta raíz
4. [ ] Función `get_tree_structure(conversation_id)` - Devuelve árbol completo para UI
5. [ ] Llamar a `init_db()` en el lifespan de FastAPI

**Criterio de éxito:** 
- Al arrancar servidor, se crea `chat_history.db` con las 2 tablas
- `reconstruct_thread(leaf_id)` devuelve lista ordenada [system, msg1, msg2, ...]
- `get_tree_structure(conv_id)` devuelve diccionario con padres e hijos

---

### Tarea 0.3: CRUD de Conversaciones y Árbol de Mensajes
**Prioridad:** 🔴 Crítica  
**Tiempo estimado:** 3-4 horas  
**Archivos:** `main.py`, `database.py`

**Endpoints:**

1. **`POST /conversations`** - Crear conversación
   - Request: `{"title": "...", "system_prompt": "Eres un agente..."}`
   - Crea conversación + mensaje raíz (system) con `parent_id = NULL`
   - Response: `{"id": "conv_123", "system_message_id": 1}`

2. **`GET /conversations`** - Listar conversaciones
   - Query params: `limit`, `offset`
   - Ordenar por `updated_at` descendente
   - Response: Lista con `id`, `title`, `updated_at`, `message_count`

3. **`GET /conversations/{id}/thread`** - Obtener rama activa
   - Reconstruye desde `active_leaf_id` hacia atrás
   - Response: Array ordenado `[system, msg1, msg2, ..., active_leaf]`
   - Cada mensaje incluye: `id`, `role`, `content`, `tool_calls`, `parent_id`, `created_at`

4. **`GET /conversations/{id}/tree`** - Obtener árbol completo
   - Para mostrar ramificaciones en UI
   - Response: Estructura jerárquica con todos los nodos
   ```json
   {
     "nodes": [
       {"id": 1, "parent_id": null, "role": "system", "children_count": 1},
       {"id": 2, "parent_id": 1, "role": "user", "children_count": 2},
       {"id": 3, "parent_id": 2, "role": "assistant", "children_count": 1},
       {"id": 4, "parent_id": 2, "role": "assistant", "children_count": 0}
     ],
     "active_leaf": 3
   }
   ```

5. **`DELETE /conversations/{id}`** - Eliminar conversación
   - Cascade elimina todos los mensajes

6. **`PATCH /conversations/{id}/active-leaf`** - Cambiar rama activa
   - Request: `{"leaf_id": 42}`
   - Actualiza `active_leaf_id` en conversación

**Subtareas:**
1. [ ] Endpoint POST para crear conversación con system prompt
2. [ ] Endpoint GET para listar conversaciones
3. [ ] Endpoint GET thread - Reconstruir rama activa
4. [ ] Endpoint GET tree - Obtener estructura completa
5. [ ] Endpoint DELETE conversación
6. [ ] Endpoint PATCH cambiar rama activa
7. [ ] Modelos Pydantic para requests/responses

**Criterio de éxito:** 
- Crear conversación, obtener thread, ver mensajes ordenados
- Cambiar `active_leaf`, hacer GET thread, ver otra rama
- GET tree devuelve estructura con ramificaciones

---

### Tarea 0.4: Endpoint `/chat` con Streaming y Árbol
**Prioridad:** 🔴 Crítica  
**Tiempo estimado:** 3-4 horas  
**Archivo:** `main.py`

**Descripción:** Endpoint unificado que soporta modo normal Y streaming.

**Request Model:**
```python
class ChatRequest(BaseModel):
    # Autenticación y modelo
    provider: Literal["openai", "google", "deepseek", "openrouter"]
    api_key: str
    model_id: str
    
    # Contexto de conversación
    conversation_id: Optional[str] = None  # Si None, crea nueva
    parent_message_id: Optional[int] = None  # Mensaje padre en árbol
    
    # Mensaje del usuario
    user_message: str
    
    # Configuración
    tools: Optional[List[Dict[str, Any]]] = None
    stream: bool = False  # ← Parámetro clave
    system_prompt: Optional[str] = None  # Override system prompt
```

**Flujo de Trabajo:**

1. **Crear/obtener conversación**
   - Si `conversation_id` es None → crear nueva con system prompt
   - Si existe → obtener conversación

2. **Guardar mensaje del usuario**
   - Crear mensaje con `role=user`, `content=user_message`
   - `parent_id = parent_message_id` (o último mensaje si None)
   - Devuelve `user_msg_id`

3. **Reconstruir contexto**
   - Desde `user_msg_id` hacia atrás: `[system, msg1, msg2, ..., user_msg]`
   - Este es el contexto que se envía al LLM

4. **Llamar al LLM**
   - **Si `stream=False`:** 
     - Espera respuesta completa
     - Guarda respuesta con `role=assistant`, `parent_id=user_msg_id`
     - Actualiza `active_leaf_id = assistant_msg_id`
     - Response: `ChatResponse` con contenido completo
   
   - **Si `stream=True`:**
     - Usa `StreamingResponse` con SSE
     - Acumula chunks en memoria
     - Al finalizar, guarda mensaje completo
     - Envía eventos: `message`, `tool_call`, `done`, `error`

5. **Tool calls (si los hay)**
   - Si assistant pide tool, guardar mensaje con `tool_calls` JSON
   - Frontend ejecuta tool → envía nueva petición con `role=tool`
   - Nueva petición tiene `parent_id = assistant_msg_id`

**Response (Modo Normal):**
```python
class ChatResponse(BaseModel):
    conversation_id: str
    user_message_id: int
    assistant_message_id: int
    content: Optional[str]
    tool_calls: Optional[List[Dict]]
    finish_reason: str
```

**Response (Modo Streaming):**
```
event: message
data: {"chunk": "Voy a", "done": false}

event: message  
data: {"chunk": " ejecutar", "done": false}

event: done
data: {"conversation_id": "conv_123", "user_message_id": 5, "assistant_message_id": 6}
```

**Subtareas:**
1. [ ] Modelo `ChatRequest` con todos los campos
2. [ ] Lógica de crear/obtener conversación
3. [ ] Guardar mensaje del usuario
4. [ ] Reconstruir contexto desde árbol
5. [ ] Modo normal: llamada sin stream
6. [ ] Modo streaming: `StreamingResponse` con SSE
7. [ ] Guardar respuesta del asistente (ambos modos)
8. [ ] Actualizar `active_leaf_id` y `updated_at`
9. [ ] Manejo de tool_calls en respuesta

**Criterio de éxito:**
- `stream=false`: POST a `/chat`, GET thread, ver mensajes guardados
- `stream=true`: EventSource recibe chunks, al final mensaje guardado
- Editar mensaje previo: nuevo POST con `parent_message_id`, crea ramificación

---

### Tarea 0.5: Endpoint de Edición de Mensajes
**Prioridad:** 🔴 Crítica  
**Tiempo estimado:** 1 hora  
**Archivo:** `main.py`

**Descripción:** Permite editar mensajes y crear ramificaciones.

**Endpoint:**
```
PATCH /messages/{message_id}
```

**Request:**
```json
{
  "content": "Nuevo contenido del mensaje",
  "create_branch": true  // Si true, crea nuevo nodo; si false, edita in-place
}
```

**Response:**
```json
{
  "message_id": 42,  // ID del mensaje (nuevo si branch, mismo si edit)
  "conversation_id": "conv_123",
  "is_new_branch": true,
  "parent_id": 5
}
```

**Lógica:**

1. **Si `create_branch=true` (recomendado):**
   - Obtener `parent_id` del mensaje original
   - Crear NUEVO mensaje con mismo `parent_id` pero contenido editado
   - Actualizar `active_leaf_id` a este nuevo mensaje
   - Response: ID del nuevo mensaje

2. **Si `create_branch=false` (destructivo):**
   - Editar contenido del mensaje in-place
   - ELIMINAR todos los descendientes (hijos, nietos, etc.)
   - Response: Mismo ID

**Subtareas:**
1. [ ] Endpoint PATCH `/messages/{message_id}`
2. [ ] Lógica de crear rama (nuevo nodo con mismo padre)
3. [ ] Lógica de edición destructiva (eliminar descendientes)
4. [ ] Actualizar `active_leaf_id` tras edición
5. [ ] Modelo Pydantic para request/response

**Criterio de éxito:**
- Editar mensaje con `create_branch=true`, GET tree, ver 2 ramas
- Editar con `create_branch=false`, ver descendientes eliminados

---

### Tarea 0.6: Mejorar Manejo de Errores
**Prioridad:** 🟡 Media  
**Tiempo estimado:** 1 hora  
**Archivo:** `main.py`

**Subtareas:**
1. [ ] Crear clase `ErrorResponse`
2. [ ] Capturar `AuthenticationError` → 401
3. [ ] Capturar `RateLimitError` → 429
4. [ ] Capturar `NotFoundError` → 404
5. [ ] Capturar errores de streaming y enviar event: error

**Criterio de éxito:** Mandar API key inválida y recibir JSON estructurado con código de error

---
✅ Fase 0 Completada!

Resumen de Archivos Creados/Modificados:
Nuevos archivos:
Archivo	Descripción
database.py	Gestión SQLite con árbol de mensajes (parent_id)
models.py	Modelos Pydantic para todos los endpoints
routes/health.py	GET /health + POST /health/keys
routes/conversations.py	CRUD conversaciones + /thread + /tree
routes/chat.py	Chat con streaming SSE
routes/messages.py	Edición de mensajes con ramificación
routes_legacy.py	Discovery de modelos (código original)
main.py	Punto de entrada modular
Endpoints implementados:
Método	Ruta	Función
GET	/health	✅ Server alive
POST	/health/keys	✅ Validar API keys
POST	/conversations	✅ Crear conversación
GET	/conversations	✅ Listar conversaciones
GET	/conversations/{id}	✅ Metadata conversación
DELETE	/conversations/{id}	✅ Eliminar conversación
GET	/conversations/{id}/thread	✅ Rama activa
GET	/conversations/{id}/tree	✅ Árbol completo
PATCH	/conversations/{id}/active-leaf	✅ Cambiar rama
POST	/chat	✅ Chat (normal + streaming)
POST	/chat/tool-response	✅ Respuesta de tool
GET	/messages/{id}	✅ Obtener mensaje
PATCH	/messages/{id}	✅ Editar con rama
DELETE	/messages/{id}	✅ Eliminar mensaje
Funcionalidades verificadas:
✅ Health check básico
✅ Validación de API keys (paralelo)
✅ Creación de conversación con system prompt
✅ Listado de conversaciones
✅ Chat sin streaming (respuesta completa)
✅ Chat con streaming SSE (chunks en tiempo real)
✅ Árbol de mensajes con parent_id
✅ Ramificación al editar mensajes
✅ Reconstrucción de thread desde leaf
El servidor está corriendo en http://localhost:8000. Puedes ver la documentación en http://localhost:8000/docs.
---

## FASE 1: Frontend Base (Segundo)

> **¿Por qué segundo?** Con el backend listo, podemos probar cada componente inmediatamente.

### Tarea 1.1: Stores Zustand (ampliadas)
**Prioridad:** 🔴 Crítica
**Tiempo estimado:** 2 horas
**Archivos:** `stores/configStore.ts`, `stores/chatStore.ts`, `stores/modelsStore.ts`

**Subtareas:**
1. [ ] `configStore` - API Keys, theme, system prompt (persistencia en localStorage)
2. [ ] `chatStore` - `messages`, `conversationId`, `isLoading`, **`isStreaming`, `currentChunk`, `fullTree`, `activeLeafId`**
3. [ ] `modelsStore` - Lista de modelos, modelo activo, favoritos

**Criterio de éxito:** Abrir DevTools → Application → LocalStorage y ver los datos guardados, y `chatStore` soportando streaming y árbol

---

### Tarea 1.2: Modal de Configuración (con validación)
**Prioridad:** 🔴 Crítica
**Tiempo estimado:** 2-3 horas
**Archivos:** `components/ConfigModal.tsx`

**Subtareas:**
1. [ ] Dialog con Tabs (Apariencia, Instrucciones, API Keys)
2. [ ] Inputs para cada API Key
3. [ ] Guardar en `configStore` → localStorage
4. [ ] Toggle de tema oscuro/claro
5. [ ] **Botón "Test Keys" que llame a `POST /health/keys` y muestre badges por proveedor (OK / Invalid / Rate-limited)**

**Criterio de éxito:** Guardar API keys y poder validar claves desde la UI mostrando estado por proveedor

---

### Tarea 1.3: ChatArea Básico (con streaming y tool calls)
**Prioridad:** 🔴 Crítica
**Tiempo estimado:** 2-4 horas
**Archivos:** `components/ChatArea.tsx`, `components/MessageBubble.tsx`

**Subtareas:**
1. [ ] Lista de mensajes con `ScrollArea`
2. [ ] `MessageBubble` (user vs assistant) y render `role='tool'`
3. [ ] Input de texto + botón enviar
4. [ ] Estado `isLoading` y `isStreaming` (spinner vs streaming incremental)
5. [ ] **Integrar `EventSource` para SSE cuando `stream=true`**: abrir/cerrar conexión, parsear eventos `message`, `tool_call`, `done`, `error`, y acumular chunks en `chatStore.currentChunk`
6. [ ] Mostrar `tool_calls` en UI (JSON colapsable / panel)
7. [ ] Botón `Edit` en mensajes del usuario → modal/inline editor con checkbox **"Crear nueva rama"** que llame a `PATCH /messages/{id}`

**Criterio de éxito:** Envío user→assistant funciona, streaming muestra texto progresivamente, tool calls renderizados y edición con opción de crear rama disponible

---

### Tarea 1.4: Selector de Modelos (Dual)
**Prioridad:** 🟡 Media
**Tiempo estimado:** 3-4 horas
**Archivos:** `components/ModelDropdown.tsx`, `components/ModelSelectorModal.tsx`

**Subtareas:**
1. [ ] Dropdown simple con favoritos
2. [ ] Modal completo con búsqueda y filtros
3. [ ] Sistema de favoritos (estrella)
4. [ ] Guardar favoritos en localStorage

**Criterio de éxito:** Cambiar modelo desde dropdown y desde modal

---

### Tarea 1.5: Sidebar de Conversaciones
**Prioridad:** 🟡 Media
**Tiempo estimado:** 2 horas
**Archivos:** `components/ChatSidebar.tsx`

**Subtareas:**
1. [ ] Botón "+ Nuevo Chat"
2. [ ] Lista de conversaciones (mock data primero)
3. [ ] Agrupación por fecha (Hoy, Ayer, Esta semana)
4. [ ] Click para cambiar de conversación

**Criterio de éxito:** Ver lista y poder crear "nuevo chat"

---

### Tarea 1.6: UI de Árbol y Navegación de Ramas
**Prioridad:** 🟡 Media
**Tiempo estimado:** 2-3 horas
**Archivos:** `components/BranchIndicator.tsx`, `components/TreeView.tsx`

**Subtareas:**
1. [ ] Componente `BranchIndicator` en `MessageBubble` que muestre número de hijos
2. [ ] `TreeView` que consuma `GET /conversations/{id}/tree` y muestre ramas
3. [ ] Botón para cambiar `active_leaf` (llamar `PATCH /conversations/{id}/active-leaf`)
4. [ ] Preview rápido de rama alternativa al pasar el ratón

**Criterio de éxito:** Cambiar a una rama alternativa y ver el hilo reconstruido desde `active_leaf`

---

## FASE 2: Integración Frontend ↔ Backend (Tercero)

> **¿Por qué tercero?** Ahora conectamos las piezas.

### Tarea 2.1: Servicio de API
**Prioridad:** 🔴 Crítica  
**Tiempo estimado:** 1-2 horas  
**Archivos:** `services/api.ts`

**Subtareas:**
1. [ ] Función `fetchModels(keys)` → `/models/discover`
2. [ ] Función `sendMessage(...)` → `/chat`
3. [ ] Función `getConversations()` → `/conversations`
4. [ ] Función `getConversation(id)` → `/conversations/{id}`
5. [ ] Manejo de errores centralizado

**Criterio de éxito:** Console.log muestra datos reales del backend

---

### Tarea 2.2: Conectar ChatArea con Backend
**Prioridad:** 🔴 Crítica  
**Tiempo estimado:** 2 horas  

**Subtareas:**
1. [ ] Al enviar mensaje, llamar a `sendMessage()`
2. [ ] Mostrar respuesta del LLM
3. [ ] Actualizar lista de conversaciones en sidebar
4. [ ] Manejar errores con Toast

**Criterio de éxito:** Conversación completa user→assistant funciona

---

### Tarea 2.3: Conectar Sidebar con Backend
**Prioridad:** 🔴 Crítica  
**Tiempo estimado:** 1-2 horas  

**Subtareas:**
1. [ ] Al cargar, llamar a `getConversations()`
2. [ ] Al click en conversación, cargar historial
3. [ ] Al crear nuevo chat, llamar a backend

**Criterio de éxito:** Historial persiste tras refrescar página

---

### Tarea 2.4: Conectar Selector de Modelos
**Prioridad:** 🔴 Crítica  
**Tiempo estimado:** 1 hora  

**Subtareas:**
1. [ ] Al abrir selector, llamar a `fetchModels()`
2. [ ] Mostrar modelos reales con ELO scores
3. [ ] Filtrar por proveedor/ranking

**Criterio de éxito:** Ver modelos reales de tus API keys

---

### Tarea 2.5: Manejo de Errores UI
**Prioridad:** 🟡 Media  
**Tiempo estimado:** 1-2 horas  
**Archivos:** `components/ErrorToast.tsx`

**Subtareas:**
1. [ ] Componente Toast para errores
2. [ ] Detectar backend caído → mensaje
3. [ ] Detectar API key inválida → mensaje específico
4. [ ] Detectar rate limit → mensaje con tiempo

**Criterio de éxito:** Apagar backend, ver toast "No se puede conectar"

---

## FASE 3: Polish y Extras (Último)

> **¿Por qué último?** Son mejoras, no funcionalidad core.

### Tarea 3.1: Panel de Terminal/Logs
**Prioridad:** 🟢 Baja  
**Tiempo estimado:** 2-3 horas  
**Archivos:** `components/TerminalPanel.tsx`

**Subtareas:**
1. [ ] Panel colapsable (inicialmente oculto)
2. [ ] Se abre si hay `tool_calls`
3. [ ] Muestra JSON de herramientas
4. [ ] Scroll automático

---

### Tarea 3.2: Streaming (Opcional)
**Prioridad:** 🟢 Baja  
**Tiempo estimado:** 4-6 horas  

**Backend:**
1. [ ] Endpoint `/chat/stream` con SSE

**Frontend:**
1. [ ] EventSource para recibir chunks
2. [ ] Actualizar mensaje progresivamente

---

### Tarea 3.3: Dockerización Frontend
**Prioridad:** 🟢 Baja  
**Tiempo estimado:** 1-2 horas  

**Subtareas:**
1. [ ] Dockerfile multi-stage
2. [ ] Añadir a docker-compose.yml
3. [ ] Variables de entorno para API_URL

---

## Checklist Resumido

### Fase 0 - Backend (Días 1-4)
- [ ] Health check + validación de API keys
- [ ] SQLite con árbol de mensajes (parent_id)
- [ ] CRUD conversaciones + árbol
- [ ] Endpoint /chat con streaming
- [ ] Endpoint edición de mensajes
- [ ] Mejorar errores

### Fase 1 - Frontend Base (Días 4-7)
- [ ] Stores Zustand
- [ ] Modal configuración
- [ ] ChatArea básico
- [ ] Selector modelos
- [ ] Sidebar conversaciones

### Fase 2 - Integración (Días 8-10)
- [ ] Servicio API
- [ ] Conectar chat
- [ ] Conectar sidebar
- [ ] Conectar selector
- [ ] Toasts de error

### Fase 3 - Polish (Días 11-12)
- [ ] Panel terminal
- [ ] (Opcional) Streaming
- [ ] (Opcional) Docker

---

## Dependencias entre Tareas

```
0.1 Health + Keys ──────────────────────────────────┐
                                                    │
0.2 SQLite Árbol ──┬──▶ 0.3 CRUD + Tree ───────────┤
                   │                                │
                   ├──▶ 0.4 /chat + Stream ─────────┤
                   │                                │
                   └──▶ 0.5 Edit Messages ──────────┤
                                                    │
                        0.6 Errors ─────────────────┤
                                                    │
                                                    ▼
1.1 Stores ──┬──▶ 1.2 Config Modal                 │
             │                                      │
             ├──▶ 1.3 ChatArea ────────────────────┤
             │                                      │
             ├──▶ 1.4 Model Selector               │
             │                                      │
             └──▶ 1.5 Sidebar ─────────────────────┤
                                                    │
                                                    ▼
2.1 API Service ──┬──▶ 2.2 Conectar Chat + Stream  │
                  │                                 │
                  ├──▶ 2.3 Conectar Sidebar        │
                  │                                 │
                  ├──▶ 2.4 Conectar Selector       │
                  │                                 │
                  └──▶ 2.5 Error Toasts ───────────┘
                                                    
                                                    ▼
                            3.x Polish (Independientes)
```

---

## Estimación Total

| Fase | Tiempo | Acumulado |
|:-----|:-------|:----------|
| Fase 0 | 3-4 días | 3-4 días |
| Fase 1 | 3-4 días | 6-8 días |
| Fase 2 | 2-3 días | 8-11 días |
| Fase 3 | 1-2 días | 9-13 días |

**Total: ~11-13 días de trabajo** (asumiendo dedicación parcial)

**Nota:** Fase 0 es más larga por sistema de árbol y streaming, pero evita refactorizar después.

---

## Próximo Paso Inmediato

**Empezar por:** `Tarea 0.1 - Health Check Mejorado`

Aunque ahora toma 30-45 min (más que antes), es fundamental para que el frontend pueda:
1. Detectar si el backend está vivo
2. Validar las API keys del usuario ANTES de usarlas
3. Mostrar en la UI qué proveedores están configurados correctamente

---

## Notas Importantes de Arquitectura

### ¿Por qué Sistema de Árbol?

El árbol de mensajes permite:
- ✅ Editar cualquier mensaje y crear ramificaciones (como ChatGPT)
- ✅ Explorar diferentes respuestas sin perder historial
- ✅ Tool calls encadenados (user → assistant+tool_call → tool → assistant)
- ✅ Regenerar respuestas sin borrar nada

### ¿Por qué Streaming desde el Inicio?

Implementar streaming después implica:
- ❌ Refactorizar el estado del frontend
- ❌ Cambiar componentes de chat para chunks
- ❌ Reescribir lógica de guardado en BD

Haciéndolo ahora:
- ✅ Arquitectura correcta desde día 1
- ✅ V1 usa `stream=false`, V2 solo cambia a `stream=true`
- ✅ No hay "deuda técnica"

### Esquema del Árbol de Mensajes

```
Conversación: "Escaneo de puertos"
├─ [1] system: "Eres un agente..." (parent_id=NULL)
    └─ [2] user: "Escanea puerto 80" (parent_id=1)
        ├─ [3] assistant: "Ejecutando nmap..." (parent_id=2, active_leaf)
        │   └─ [5] user: "Ahora puerto 443" (parent_id=3)
        │
        └─ [4] assistant: "Voy a usar curl..." (parent_id=2, rama alternativa)
            └─ [6] user: "Perfecto, continúa" (parent_id=4)
```

En este caso:
- `active_leaf_id = 5` (rama principal)
- Thread reconstruido: `[1, 2, 3, 5]`
- Si cambio a rama alternativa: `active_leaf_id = 6` → Thread: `[1, 2, 4, 6]`
