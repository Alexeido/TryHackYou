# Modo Agéntico - Plan de Implementación

## 🎯 Objetivo

Transformar el asistente de un chatbot reactivo con tools a un **Agente Autónomo** capaz de:

1. **Planificar** tareas complejas multi-paso
2. **Mantener estado** a través de ejecuciones largas
3. **Auto-supervisar** su progreso sin perder el hilo
4. **Optimizar contexto** resumiendo outputs largos automáticamente
5. **Operar de forma autónoma** en escenarios de ciberseguridad complejos

### Ejemplo de Caso de Uso

```
Usuario: "Tengo un laboratorio en 10.5.0.5, puedes acceder a root 
         de forma totalmente autónoma y explicarme la falla?"

Agente: [Crea plan de 8 pasos]
        [Ejecuta reconocimiento]
        [Actualiza estado: "Fase 1/8 completada"]
        [Encuentra puerto 21 abierto con vsftpd 2.3.4]
        [Actualiza estado: "Vulnerabilidad detectada"]
        [Ejecuta exploit]
        [Verifica acceso root]
        [Presenta informe completo]
```

---

## 🏗️ Arquitectura del Sistema

### Componentes Principales

```
┌─────────────────────────────────────────────────────────────┐
│                         Frontend                             │
│  - UI para visualizar progreso de misión                    │
│  - Indicadores de estado por objetivo                        │
└─────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────┐
│                      Backend (FastAPI)                       │
│                                                              │
│  ┌────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │ Mission Control│  │ Tool Summarizer │  │ Chat Engine │ │
│  │   (Estado)     │  │  (Optimización) │  │             │ │
│  └────────────────┘  └─────────────────┘  └─────────────┘ │
│           ↕                    ↕                   ↕        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Base de Datos (SQLite)                  │  │
│  │  - Misiones (missions)                               │  │
│  │  - Objetivos (objectives)                            │  │
│  │  - Resúmenes de tools (tool_summaries)               │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────┐
│                     LLM (Gemini/Ollama)                      │
│  - Modo Agéntico con thought blocks                          │
│  - Tools: execute_command + manage_mission                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 Modelo de Datos

### 1. Tabla `missions`

Almacena el estado global de una misión autónoma.

```sql
CREATE TABLE missions (
    id TEXT PRIMARY KEY,              -- UUID de la misión
    conversation_id TEXT NOT NULL,    -- Conversación asociada
    goal TEXT NOT NULL,               -- Objetivo de alto nivel
    current_phase TEXT,               -- Fase actual (ej: "reconnaissance")
    status TEXT DEFAULT 'IN_PROGRESS',-- PLANNING | IN_PROGRESS | COMPLETED | FAILED
    created_at TIMESTAMP,
    completed_at TIMESTAMP,
    metadata JSON,                    -- Info adicional (target, tipo de test, etc)
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);
```

### 2. Tabla `objectives`

Desglosa la misión en objetivos concretos (checklist).

```sql
CREATE TABLE objectives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id TEXT NOT NULL,
    order_index INTEGER NOT NULL,     -- Orden de ejecución
    task TEXT NOT NULL,               -- Descripción del objetivo
    status TEXT DEFAULT 'PENDING',    -- PENDING | IN_PROGRESS | COMPLETED | FAILED | SKIPPED | AWAITING_AUTHORIZATION
    result_summary TEXT,              -- Resumen del resultado
    requires_approval BOOLEAN DEFAULT 0,  -- Si requiere aprobación humana
    approval_status TEXT,             -- NULL | APPROVED | REJECTED
    pending_command TEXT,             -- Comando guardado esperando aprobación
    created_at TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (mission_id) REFERENCES missions(id)
);
```

### 3. Tabla `tool_summaries`

Cache de resúmenes de outputs de tools (optimización de contexto).

```sql
CREATE TABLE tool_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL,      -- Mensaje tool original
    tool_call_id TEXT NOT NULL,       -- ID del tool_call
    original_output TEXT NOT NULL,    -- Output original COMPLETO (para zoom in)
    original_length INTEGER NOT NULL, -- Longitud del output original
    summary TEXT NOT NULL,            -- Resumen compacto
    compression_ratio REAL,           -- Ratio de compresión
    created_at TIMESTAMP,
    FOREIGN KEY (message_id) REFERENCES messages(id)
);

-- Tabla para tracking de jobs en background de misiones
CREATE TABLE mission_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    mission_id TEXT NOT NULL,
    objective_id INTEGER NOT NULL,
    command TEXT NOT NULL,
    status TEXT DEFAULT 'RUNNING',    -- RUNNING | COMPLETED | FAILED
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (mission_id) REFERENCES missions(id),
    FOREIGN KEY (objective_id) REFERENCES objectives(id)
);
```

---

## 🛠️ Implementación por Fases

### **Fase 1: Mission Control (Backend Core)**

#### 1.1 Nuevas Funciones de BD (`database.py`)

```python
# Gestión de Misiones
def create_mission(conversation_id: str, goal: str, metadata: dict = None) -> str
def get_mission(mission_id: str) -> dict
def update_mission_phase(mission_id: str, phase: str)
def complete_mission(mission_id: str, status: str)
def get_active_mission(conversation_id: str) -> dict | None

# Gestión de Objetivos
def add_objectives(mission_id: str, tasks: List[str]) -> List[int]
def update_objective_status(objective_id: int, status: str, result: str = None)
def get_objectives(mission_id: str) -> List[dict]
def get_mission_progress(mission_id: str) -> dict  # % completado

# Gestión de Resúmenes
def save_tool_summary(message_id: int, tool_call_id: str, 
                     original: str, summary: str)
def get_tool_summary(message_id: int, tool_call_id: str) -> str | None
```

#### 1.2 Nueva Tool: `manage_mission`

```python
# En routes/chat.py - execute_tool_call()

elif function_name == "manage_mission":
    """
    Permite al LLM crear, actualizar y consultar el estado de su misión.
    
    Args:
        action: "create" | "update_objective" | "update_phase" | "complete"
        mission_id: ID de la misión (opcional en create)
        goal: Objetivo de alto nivel (solo en create)
        objectives: Lista de tareas (solo en create)
        objective_id: ID del objetivo a actualizar
        status: Nuevo estado del objetivo
        phase: Nueva fase de la misión
        result: Resumen del resultado del objetivo
    """
    action = function_args.get("action")
    
    if action == "create":
        # Crear nueva misión con objetivos
        goal = function_args.get("goal")
        objectives = function_args.get("objectives", [])
        
        mission_id = db.create_mission(conversation_id, goal)
        obj_ids = db.add_objectives(mission_id, objectives)
        
        return json.dumps({
            "mission_id": mission_id,
            "objective_ids": obj_ids,
            "status": "Mission created successfully"
        })
    
    elif action == "update_objective":
        # Actualizar estado de un objetivo
        obj_id = function_args.get("objective_id")
        status = function_args.get("status")
        result = function_args.get("result", "")
        
        db.update_objective_status(obj_id, status, result)
        progress = db.get_mission_progress(mission_id)
        
        return json.dumps({
            "status": "Objective updated",
            "progress": f"{progress['completed']}/{progress['total']} objectives"
        })
    
    elif action == "update_phase":
        # Cambiar fase de la misión
        mission_id = function_args.get("mission_id")
        phase = function_args.get("phase")
        
        db.update_mission_phase(mission_id, phase)
        return json.dumps({"status": "Phase updated", "new_phase": phase})
    
    elif action == "complete":
        # Finalizar misión
        mission_id = function_args.get("mission_id")
        final_status = function_args.get("status", "COMPLETED")
        
        db.complete_mission(mission_id, final_status)
        return json.dumps({"status": "Mission completed"})
    
    elif action == "get_status":
        # Consultar estado actual
        mission_id = function_args.get("mission_id")
        mission = db.get_mission(mission_id)
        objectives = db.get_objectives(mission_id)
        
        return json.dumps({
            "mission": mission,
            "objectives": objectives,
            "progress": db.get_mission_progress(mission_id)
        })
```

---

### **Fase 2: Optimización de Contexto (Tool Summarizer)**

#### 2.1 Nuevo Endpoint: `/summarize-tool-output`

```python
# En routes/chat.py

@router.post("/summarize-tool-output")
async def summarize_tool_output(
    output: str,
    provider: str,
    model_id: str,
    api_key: str
) -> dict:
    """
    Endpoint rápido para resumir outputs largos de tools.
    No usa streaming, solo llamada directa.
    """
    if len(output) < 500:
        # Si es corto, no resumir
        return {"summary": output, "compressed": False}
    
    client = get_client(provider, api_key)
    
    # Prompt especializado en resumir outputs técnicos
    summary_prompt = f"""Resume este output técnico manteniendo SOLO la información crítica.

Reglas:
- Mantén IPs, puertos, versiones, CVEs, cookies de sesion, tokens, hashes
- Omite explicaciones innecesarias
- Elimina líneas repetitivas o de progreso
- Máximo 15 líneas
- Formato conciso, bullets si es apropiado

A tener en cuenta: La Inconsistencia del Summarizer: Si usas un modelo muy pequeño para resumir, podría omitir una cookie de sesión o un puerto raro que el Agente Jefe necesitaba.

    Recomendación: Asegúrate de que el prompt de resumen sea "conservador" (mejor resumir menos que perder datos clave).
OUTPUT:
  No limitaremos realmente el output pero le diremos al modelo que debe de hacer un resumen con lo importante.

RESUMEN:"""

    response = await client.chat.completions.create(
        model=model_id,
        messages=[{"role": "user", "content": summary_prompt}],
        stream=False,
        temperature=0.3,  # Baja temperatura para respuestas deterministas
        max_tokens=500
    )
    
    summary = response.choices[0].message.content
    compression_ratio = len(summary) / len(output)
    
    return {
        "summary": summary,
        "compressed": True,
        "compression_ratio": compression_ratio,
        "original_length": len(output),
        "summary_length": len(summary)
    }
```

#### 2.2 Integración en el Loop de Tools

```python
# Modificar stream_chat_response() después de ejecutar tools

async for tool_call in tool_calls_to_execute:
    result = await execute_tool_call(tool_call, conversation_id, leaf_id)
    
    # NUEVO: Si el resultado es muy largo, resumir
    if len(result) > 1000 and req.auto_summarize:
        print(f"📦 Resumiendo output de {len(result)} chars...")
        
        summary_response = await summarize_tool_output(
            output=result,
            provider=req.provider,
            model_id=req.model_id,  # O usar modelo más rápido
            api_key=req.api_key
        )
        
        if summary_response["compressed"]:
            # Guardar ambas versiones
            db.save_tool_summary(
                message_id=tool_msg_id,
                tool_call_id=tool_call["id"],
                original=result,
                summary=summary_response["summary"]
            )
            
            # Usar versión resumida para el LLM
            result_for_llm = summary_response["summary"]
            
            print(f"✅ Comprimido {summary_response['compression_ratio']:.1%}")
        else:
            result_for_llm = result
    else:
        result_for_llm = result
    
    tool_results.append({
        "tool_call_id": tool_call["id"],
        "role": "tool",
        "content": result_for_llm
    })
```

---

### **Fase 3: Modo Agéntico (System Prompt Evolution)**

#### 3.1 Detección de Intención Agéntica

```python
# En chat_completion() antes de llamar al LLM

AGENTIC_KEYWORDS = [
    "de forma autónoma", "automáticamente", "hazlo completo",
    "full assessment", "comprehensive test", "pentesting completo",
    "desde cero hasta", "start to finish"
]

is_agentic_request = any(
    keyword in req.user_message.lower() 
    for keyword in AGENTIC_KEYWORDS
)

# Si es agéntico, modificar system prompt
if is_agentic_request:
    system_prompt = AGENTIC_SYSTEM_PROMPT
else:
    system_prompt = STANDARD_SYSTEM_PROMPT
```

#### 3.2 System Prompt Agéntico

```python
AGENTIC_SYSTEM_PROMPT = """Eres un Agente Autónomo especializado en ciberseguridad.

## MODO DE OPERACIÓN

Cuando recibas una tarea compleja (ej: "accede a root en 10.5.0.5"), debes:

### 1. PLANIFICACIÓN INICIAL
Antes de ejecutar NADA, usa la tool `manage_mission` con action="create":

```json
{
  "action": "create",
  "goal": "Obtener acceso root en 10.5.0.5",
  "objectives": [
    "Reconocimiento de red y servicios",
    "Identificación de versiones vulnerables",
    "Búsqueda de exploits aplicables",
    "Explotación de vulnerabilidad",
    "Post-explotación y escalada de privilegios",
    "Verificación de acceso root",
    "Documentación de hallazgos"
  ]
}
```

### 2. LOOP DE EJECUCIÓN
Para cada objetivo:

a) **Análisis**: Revisa el estado actual de la misión
   - Usa `manage_mission` con action="get_status" si es necesario

b) **Ejecución**: Ejecuta el comando técnico apropiado
   - Usa `execute_command` con wait_time si es necesario

c) **Actualización**: Marca el objetivo como completado/fallado
   ```json
   {
     "action": "update_objective",
     "objective_id": 2,
     "status": "COMPLETED",
     "result": "Puerto 21 abierto, vsftpd 2.3.4 detectado"
   }
   ```

    Lo que podría darte problemas (Puntos a vigilar)

    La "Alucinación de Progreso": A veces el LLM marca un objetivo como COMPLETED porque el comando se ejecutó, pero el resultado real fue un error silencioso.

        Solución: El prompt debe ser muy estricto: "Solo marca como completado si has verificado el éxito con un comando de comprobación (ej: whoami tras un exploit)".


d) **Cambio de Fase**: Si cambias de fase, actualiza
   ```json
   {
     "action": "update_phase",
     "phase": "Explotación"
   }
   ```

### 3. GESTIÓN DE ERRORES
Si un comando falla:
- Marca el objetivo como FAILED con la razón
- Decide si continuar con estrategia alternativa o abortar
- NO sigas ejecutando a ciegas sin actualizar el estado

### 4. FINALIZACIÓN
Al completar todos los objetivos:
```json
{
  "action": "complete",
  "status": "COMPLETED",  // o "FAILED" si no se logró
  "reflection": "Por que cree que tuvo éxito o fallo"
}
```

## REGLAS CRÍTICAS

1. **SIEMPRE mantén el estado actualizado**: No confíes en tu memoria del chat
2. **Un objetivo a la vez**: No saltarte pasos
3. **Adaptación**: Si algo no funciona, actualiza el plan
4. **Resumen al finalizar**: Presenta informe estructurado

## FORMATO DE RESPUESTA

Para cada acción, usa este formato:

<thought>
Estado actual: Objetivo 3/7 - Identificando vulnerabilidades
Resultado previo: vsftpd 2.3.4 detectado (vulnerable)
Próxima acción: Buscar exploit para esta versión
</thought>

[Actualización de estado con manage_mission]
[Ejecución del comando técnico]
[Interpretación del resultado para el usuario]
"""
```

---

### **Fase 4: Frontend (Visualización de Progreso)**

#### 4.1 Componente `MissionProgress.tsx`

```typescript
interface Mission {
  id: string;
  goal: string;
  current_phase: string;
  status: string;
  objectives: Objective[];
}

interface Objective {
  id: number;
  task: string;
  status: 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' | 'FAILED';
  result_summary?: string;
}

export function MissionProgress({ missionId }: { missionId: string }) {
  const [mission, setMission] = useState<Mission | null>(null);
  
  // Polling cada 2 segundos para actualizar progreso
  useEffect(() => {
    const interval = setInterval(async () => {
      const response = await fetch(`/api/missions/${missionId}`);
      const data = await response.json();
      setMission(data);
    }, 2000);
    
    return () => clearInterval(interval);
  }, [missionId]);
  
  if (!mission) return <div>Cargando misión...</div>;
  
  const progress = mission.objectives.filter(o => o.status === 'COMPLETED').length;
  const total = mission.objectives.length;
  
  return (
    <div className="mission-panel">
      <h3>🎯 {mission.goal}</h3>
      <div className="phase-badge">Fase: {mission.current_phase}</div>
      <div className="progress-bar">
        <div style={{ width: `${(progress/total)*100}%` }} />
        <span>{progress}/{total}</span>
      </div>
      
      <div className="objectives-list">
        {mission.objectives.map((obj, idx) => (
          <div key={obj.id} className={`objective ${obj.status.toLowerCase()}`}>
            <span className="objective-number">{idx + 1}</span>
            <span className="objective-task">{obj.task}</span>
            <span className="objective-status">{getStatusIcon(obj.status)}</span>
            {obj.result_summary && (
              <div className="objective-result">{obj.result_summary}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function getStatusIcon(status: string) {
  switch(status) {
    case 'COMPLETED': return '✅';
    case 'IN_PROGRESS': return '⏳';
    case 'FAILED': return '❌';
    case 'PENDING': return '⏸️';
    default: return '❓';
  }
}
```

#### 4.2 Layout con Sidebar de Misión

```typescript
// En Chat.tsx - Layout de 2 columnas

export default function Chat() {
  const [activeMission, setActiveMission] = useState<Mission | null>(null);
  
  return (
    <div className="chat-container">
      {/* Columna izquierda: Chat normal */}
      <div className="chat-column">
        <MessageList messages={messages} />
        <InputBox />
      </div>
      
      {/* Columna derecha: Sidebar de Misión (si está activa) */}
      {activeMission && (
        <div className="mission-sidebar">
          <MissionProgress missionId={activeMission.id} />
          
          {/* Logs de pensamiento (acordeón) */}
          <ThoughtLogs conversationId={conversationId} />
          
          {/* Jobs en background */}
          <BackgroundJobs missionId={activeMission.id} />
        </div>
      )}
    </div>
  );
}
```

#### 4.3 Componente de Logs de Pensamiento

```typescript
// ThoughtLogs.tsx - Acordeón para ver razonamiento del agente

import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";

export function ThoughtLogs({ conversationId }: { conversationId: string }) {
  const [thoughts, setThoughts] = useState<ThoughtEntry[]>([]);
  
  // Extraer bloques <thought> del historial de mensajes
  useEffect(() => {
    // Polling o SSE para actualizar
    fetchThoughts(conversationId).then(setThoughts);
  }, [conversationId]);
  
  return (
    <div className="thought-logs">
      <h4>🧠 Razonamiento del Agente</h4>
      <Accordion type="single" collapsible>
        {thoughts.map((thought, idx) => (
          <AccordionItem key={idx} value={`thought-${idx}`}>
            <AccordionTrigger>
              Pensamiento #{idx + 1} - {thought.timestamp}
            </AccordionTrigger>
            <AccordionContent>
              <pre className="thought-content">{thought.content}</pre>
            </AccordionContent>
          </AccordionItem>
        ))}
      </Accordion>
    </div>
  );
}
```

#### 4.4 Vista de Jobs en Background

```typescript
// BackgroundJobs.tsx

export function BackgroundJobs({ missionId }: { missionId: string }) {
  const [jobs, setJobs] = useState<Job[]>([]);
  
  useEffect(() => {
    const interval = setInterval(async () => {
      const response = await fetch(`/api/missions/${missionId}/jobs`);
      const data = await response.json();
      setJobs(data.jobs);
    }, 3000);
    
    return () => clearInterval(interval);
  }, [missionId]);
  
  const runningJobs = jobs.filter(j => j.status === 'RUNNING');
  
  if (runningJobs.length === 0) return null;
  
  return (
    <div className="background-jobs">
      <h4>⏳ Comandos en Ejecución</h4>
      {runningJobs.map(job => (
        <div key={job.id} className="job-card">
          <code>{job.command}</code>
          <div className="job-timer">
            Ejecutando hace {formatDuration(job.started_at)}
          </div>
          <Spinner className="animate-spin" />
        </div>
      ))}
    </div>
  );
}
```

---

### **Fase 5: Endpoints de API para Misiones**

```python
# En routes/missions.py (NUEVO archivo)

@router.get("/missions/{mission_id}")
async def get_mission_status(mission_id: str):
    """Obtiene el estado completo de una misión"""
    mission = db.get_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    
    objectives = db.get_objectives(mission_id)
    progress = db.get_mission_progress(mission_id)
    
    return {
        "mission": mission,
        "objectives": objectives,
        "progress": progress
    }

@router.get("/conversations/{conversation_id}/active-mission")
async def get_active_mission(conversation_id: str):
    """Obtiene la misión activa de una conversación"""
    mission = db.get_active_mission(conversation_id)
    if not mission:
        return {"active": False}
    
    return { (REORGANIZADO)

### Sprint 1 (4-5 días): Foundation + Core Tools
**Objetivo**: MVP funcional con estado básico

- [ ] Crear tablas de BD (missions, objectives, tool_summaries, mission_jobs)
- [ ] Implementar funciones CRUD de misiones en database.py
- [ ] Tool `manage_mission` con actions:
  - [x] create, update_objective, update_phase, complete, get_status
  - [ ] **modify_objectives** (insertar/borrar objetivos dinámicamente)
- [ ] Tool `get_original_output` (zoom in a outputs resumidos)
- [ ] Testing básico con misión simple (3 objetivos)

**Entregable**: Agente puede crear y seguir un plan básico, reorganizarlo si es necesario.

---

### Sprint 2 (3-4 días): Tool Summarizer + Background Jobs
**Objetivo**: Optimización de contexto y comandos largos

- [ ] Endpoint `/summarize-tool-output` (no streaming)
- [ ] Integración en loop de tools con auto_summarize
- [ ] Guardar output original en tool_summaries (para zoom in)
- [ ] Worker de background jobs (comandos con wait_time >30s)
- [ ] Tabla mission_jobs y tracking de estado asíncrono
- [ ] Testing con nmap (output largo + comando lento)

**Entregable**: Outputs se resumen automáticamente, comandos largos no bloquean el sistema.

---

### Sprint 3 (3-4 días): Human-in-the-Loop + Seguridad
**Objetivo**: Control ético sobre comandos peligrosos

- [ ] Detector de comandos peligrosos (regex patterns)
- [ ] Estado AWAITING_AUTHORIZATION en objetivos
- [ ] Endpoint `/objectives/{id}/approve` (aprobar/rechazar)
- [ ] Frontend: Botón de aprobación con preview del comando
- [ ] Testing con exploits de Metasploit (deben requerir aprobación)
- [ ] Sistema de auditoría (log de todos los comandos ejecutados)

**Entregable**: Comandos destructivos requieren aprobación humana explícita.

---

### Sprint 4 (2-3 días): System Prompt Agéntico + Detección
**Objetivo**: Comportamiento autónomo inteligente

- [ ] Detección de intención agéntica (keywords)
- [ ] System prompt especializado con instrucciones de:
  - Planificación inicial
  - Loop de ejecución
  - Reorganización dinámica de plan
  - Gestión de errores
- [ ] Integración de todas las tools en el prompt
- [ ] Testing end-to-end: "Accede a root en X de forma autónoma"

**Entregable**: El agente planifica, ejecuta y se adapta sin intervención humana (salvo aprobaciones).

---

### Sprint 5 (4-5 días): Frontend Avanzado + UX
**Objetivo**: Visualización profesional para demo/tribunal

- [ ] **Sidebar de Misión** (componente persistente a la derecha)
  - Progress bar con % completado
  - Lista de objetivos con estados
  - Indicador de fase actual
- [ ] **Logs de Pensamiento** (Accordion para `<thought>` blocks)
  - Colapsables por defecto
  - Ver razonamiento del agente sin ensuciar chat
- [ ] Componente `MissionProgress.tsx` con polling cada 2s
- [ ] Notificaciones al completar objetivos
- [ ] Vista de jobs en background (en progreso)
- [ ] Endpoints de API REST para misiones
- [ ] Botones de control: Pausar/Reanudar/Cancelar misión

**Entregable**: UI que impresiona en una demo de TFG.

---

### Sprint 6 (2-3 días): Polish, Testing & Documentation
**Objetivo**: Preparación para defensa de TFG

- [ ] Casos de prueba end-to-end:
  - Reconocimiento simple (nmap + análisis)
  - Pentesting completo (reconocimiento → exploit → post-exploit)
  - Recuperación de fallos (exploit falla, cambia estrategia)
  - Comando largo en background (sin perder estado)
- [ ] Fine-tuning de prompts según resultados
- [ ] Documentación técnica (Markdown en /Documentaciones)
- [ ] Video demo de 5 minutos para el tribunal
- [ ] Mejora de mensajes de error y logs

**Entregable**: Sistema robusto listo para defensa académica.

---

## 📊 Roadmap Visual

```
Sprint 1: ████████░░░░░░░░░░  Foundation + Tools
Sprint 2: ████████░░░░░░░░░░  Summarizer + Background
Sprint 3: ████████░░░░░░░░░░  Security + Approvals  
Sprint 4: ██████░░░░░░░░░░░░  Agentic Behavior
Sprint 5: ██████████░░░░░░░░  Frontend Premium
Sprint 6: ██████░░░░░░░░░░░░  Polish + Testing

Total: 18-24 días (~4-5 semanas)
```rgos (nmap, dirb, etc)

### Sprint 3 (2-3 días): System Prompt Agéntico
- [ ] Detección de intención agéntica
- [ ] System prompt especializado
- [ ] Testing end-to-end con tareas complejas

### Sprint 4 (3-4 días): Frontend
- [ ] Componente MissionProgress
- [ ] Endpoints de API para misiones
- [ ] Integración en la UI del chat

### Sprint 5 (2 días): Polish & Testing
- [ ] Pruebas con escenarios de pentesting reales
- [ ] Documentación de uso
- [ ] Fine-tuning de prompts

---

## 📝 Consideraciones de Diseño

### 🎯 Plan Dinámico vs. Estático (CRÍTICO)

**Problema Real**: En pentesting, el escaneo inicial puede revelar 10 servicios inesperados. El plan de 8 pasos original queda obsoleto.

**Solución - Plan Evolutivo**:

```python
# Nueva action en manage_mission: "modify_objectives"
elif action == "modify_objectives":
    """
    Permite al agente reorganizar el plan sobre la marcha.
    
    Args:
        mission_id: ID de la misión
        modifications: [
            {"type": "insert", "after_id": 2, "task": "Explotar vuln PHP"},
            {"type": "delete", "objective_id": 5},
            {"type": "update", "objective_id": 3, "new_task": "Escanear puerto 8080"}
        ]
    """
    modifications = function_args.get("modifications", [])
    
    for mod in modifications:
        if mod["type"] == "insert":
            db.insert_objective_after(
                mission_id, 
                mod["after_id"], 
                mod["task"]
            )
        elif mod["type"] == "delete":
            db.delete_objective(mod["objective_id"])
        elif mod["type"] == "update":
            db.update_objective_task(
                mod["objective_id"], 
                mod["new_task"]
            )
    
    return json.dumps({
        "status": "Plan reorganizado",
        "new_objectives": db.get_objectives(mission_id)
    })
```

**Trigger de Reorganización**: El agente detecta que el resultado de un comando cambia drásticamente el escenario (ej: encuentra un servidor web no esperado).

---

### 🛡️ Human-in-the-Loop: Autorización para Comandos Críticos

**Problema Ético/Legal**: Un agente autónomo lanzando exploits sin supervisión es peligroso y éticamente cuestionable para un TFG.

**Solución - Sistema de Autorización**:

#### Nuevo Estado de Objetivo: `AWAITING_AUTHORIZATION`

```sql
-- Añadir a la tabla objectives
ALTER TABLE objectives ADD COLUMN requires_approval BOOLEAN DEFAULT 0;
ALTER TABLE objectives ADD COLUMN approval_status TEXT; -- NULL | APPROVED | REJECTED
```

#### Detector de Comandos Peligrosos

```python
# En execute_tool_call(), antes de ejecutar

DANGEROUS_PATTERNS = [
    r"msfconsole",           # Metasploit
    r"exploit/",             # Ruta de exploits
    r"--script.*vuln",       # Scripts de vulnerabilidad agresivos
    r"sqlmap.*--dump",       # Dumping de BD
    r"hydra",                # Brute force
    r"john.*--crack",        # Password cracking
    r"nc.*-e",               # Reverse shells
]

def is_dangerous_command(command: str) -> bool:
    return any(
        re.search(pattern, command, re.IGNORECASE) 
        for pattern in DANGEROUS_PATTERNS
    )

# En execute_tool_call()
if function_name == "execute_command":
    command = function_args.get("command")
    
    if is_dangerous_command(command):
        # Marcar objetivo actual como pendiente de aprobación
        current_obj = db.get_current_objective(conversation_id)
        db.update_objective_approval_status(
            current_obj["id"], 
            "AWAITING_AUTHORIZATION"
        )
        
        # Guardar comando pendiente
        db.save_pending_command(current_obj["id"], command)
        
        return json.dumps({
            "status": "AWAITING_AUTHORIZATION",
            "message": "Este comando requiere aprobación humana",
            "command": command,
            "reason": "Potencialmente destructivo/ruidoso"
        })
```

#### Endpoint de Aprobación

```python
# En routes/missions.py

@router.post("/objectives/{objective_id}/approve")
async def approve_command(objective_id: int, approved: bool):
    """
    Aprueba o rechaza un comando peligroso.
    Si se aprueba, ejecuta el comando guardado.
    """
    objective = db.get_objective_by_id(objective_id)
    pending_cmd = db.get_pending_command(objective_id)
    
    if approved:
        db.update_objective_approval_status(objective_id, "APPROVED")
        
        # Ejecutar comando ahora
        result = await execute_command_in_sandbox(pending_cmd)
        
        # Continuar la misión automáticamente
        # (el agente recibirá el resultado en el próximo turno)
        
        return {"status": "approved", "executing": True}
    else:
        db.update_objective_approval_status(objective_id, "REJECTED")
        db.update_objective_status(objective_id, "SKIPPED")
        
        return {"status": "rejected", "objective_skipped": True}
```

#### Frontend - Botón de Aprobación

```typescript
// En MissionProgress.tsx

{obj.approval_status === 'AWAITING_AUTHORIZATION' && (
  <div className="approval-required">
    <AlertTriangle className="text-yellow-500" />
    <p>Comando peligroso requiere aprobación:</p>
    <code>{obj.pending_command}</code>
    <div className="approval-buttons">
      <Button 
        variant="destructive" 
        onClick={() => approveCommand(obj.id, true)}
      >
        ✓ Aprobar Ejecución
      </Button>
      <Button 
        variant="outline" 
        onClick={() => approveCommand(obj.id, false)}
      >
        ✗ Rechazar
      </Button>
    </div>
  </div>
)}
```

---

### 🔍 Zoom In: Recuperación de Outputs Originales

**Problema de la "Memoria de Pez"**: El resumen elimina detalles técnicos que luego pueden ser necesarios.

**Solución - Tool de Zoom In**:

```python
# Nueva tool: get_original_output

elif function_name == "get_original_output":
    """
    Recupera el output original completo de un tool anterior.
    
    Args:
        tool_call_id: ID del tool_call cuyo output original se necesita
    """
    tool_call_id = function_args.get("tool_call_id")
    
    # Buscar en tool_summaries
    summary_entry = db.get_tool_summary_entry(tool_call_id)
    
    if not summary_entry:
        return json.dumps({
            "error": "No se encontró el output original",
            "tool_call_id": tool_call_id
        })
    
    original = summary_entry["original_output"]
    
    return json.dumps({
        "status": "success",
        "original_length": len(original),
        "output": original,
        "note": "Este es el output COMPLETO sin resumir"
    })
```

**Tabla extendida de tool_summaries**:

```sql
-- Añadir columna para guardar el output original
ALTER TABLE tool_summaries ADD COLUMN original_output TEXT;
```

**System Prompt - Instrucción de Zoom**:

```python
# Añadir al AGENTIC_SYSTEM_PROMPT

"""
## RECUPERACIÓN DE DETALLES

Si un resumen de output no contiene la información que necesitas:
1. Identifica el tool_call_id del comando previo (visible en el historial)
2. Usa `get_original_output` para recuperar el log completo
3. Analiza el detalle específico que faltaba
4. Continúa con la misión

Ejemplo: Si el resumen dice "3 hosts activos" pero necesitas las IPs exactas,
recupera el output completo del nmap.
"""
```

---

### ⚙️ Concurrencia y Workers (Background Processing)

**Problema**: Un escaneo de red puede tardar 10 minutos. El backend no puede bloquear esperando.

**Solución - Sistema de Workers**:

#### Arquitectura de Jobs Asíncronos

```python
# En routes/chat.py - execute_tool_call()

if function_name == "execute_command":
    command = function_args.get("command")
    wait_time = function_args.get("wait_time")
    
    # Si wait_time > 30s, considerar background
    if wait_time and wait_time > 30:
        # Lanzar en background
        job_id = await launch_background_job(
            command=command,
            conversation_id=conversation_id,
            objective_id=current_objective_id
        )
        
        # Marcar objetivo como IN_PROGRESS
        db.update_objective_status(
            current_objective_id, 
            "IN_PROGRESS",
            f"Ejecutando comando en background (job: {job_id})"
        )
        
        return json.dumps({
            "status": "JOB_LAUNCHED",
            "job_id": job_id,
            "message": "Comando ejecutándose en background. Serás notificado al completarse.",
            "estimated_time": f"{wait_time}s"
        })
```

#### Worker de Monitoreo

```python
# En job_monitor.py (ya existe pero extender)

async def monitor_mission_jobs():
    """
    Worker que verifica jobs en background y actualiza objetivos.
    """
    while True:
        await asyncio.sleep(5)
        
        # Obtener jobs en progreso
        running_jobs = db.get_running_jobs_with_objectives()
        
        for job in running_jobs:
            # Verificar estado en sandbox
            status = await check_job_status(job["job_id"])
            
            if status["completed"]:
                # Actualizar objetivo
                db.update_objective_status(
                    job["objective_id"],
                    "COMPLETED",
                    f"Comando finalizado. Exit code: {status['exit_code']}"
                )
                
                # Guardar output (resumido si es largo)
                if len(status["output"]) > 1000:
                    summary = await summarize_output(status["output"])
                    db.save_tool_summary(
                        job["message_id"],
                        job["tool_call_id"],
                        status["output"],
                        summary
                    )
                
                # Notificar al frontend via SSE
                await notify_mission_update(job["conversation_id"])
```

#### Persistencia de Estado

```sql
-- Tabla para tracking de jobs de misiones
CREATE TABLE mission_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    mission_id TEXT NOT NULL,
    objective_id INTEGER NOT NULL,
    command TEXT NOT NULL,
    status TEXT DEFAULT 'RUNNING', -- RUNNING | COMPLETED | FAILED
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (mission_id) REFERENCES missions(id),
    FOREIGN KEY (objective_id) REFERENCES objectives(id)
);
```

**Beneficio**: Si el usuario cierra el navegador durante un escaneo de 10 minutos, al volver verá que el objetivo sigue en progreso y el job continuará hasta completarse.

---

### Optimización de Contexto

**Problema**: Un nmap puede generar 5000 tokens, empujando la misión fuera del contexto.

**Solución Multi-Capa**:
1. **Resumen inmediato**: Outputs >1000 chars se resumen antes de pasar al LLM
2. **Zoom In disponible**: Si el resumen no es suficiente, recuperar original con `get_original_output`
3. **Estado explícito**: La misión y objetivos se reinyectan en cada turno (via tool calls)
4. **History compression**: Después de 10 turnos, resumir historial manteniendo solo:
   - Estado actual de la misión
   - Últimos 2-3 comandos
   - Hallazgos críticos

### Gestión de Fallos

El agente debe ser robusto ante:
- **Comandos que fallan**: Actualizar objetivo como FAILED y proponer alternativa
- **Timeouts**: Marcar como IN_PROGRESS y permitir reanudar
- **Conexión perdida**: Guardar estado en BD para retomar
- **Plan obsoleto**: Reorganizar objetivos dinámicamente con `modify_objectives`

### Seguridad

- **Validación de targets**: Verificar que IPs están en rangos autorizados
- **Rate limiting**: Evitar bucles infinitos de comandos
- **Auditoría**: Log completo de todos los comandos ejecutados en modo agéntico
- **Human-in-the-Loop**: Aprobación obligatoria para comandos peligrosos
- **Sandbox aislado**: Todos los comandos se ejecutan en contenedor controlado

---

## 🧪 Casos de Prueba

### Test 1: Reconocimiento Simple
```
Input: "Escanea 10.5.0.0/24 de forma autónoma"
Expected:
  - Crear misión con 3 objetivos
  - Ejecutar nmap en paralelo (ping sweep)
  - Identificar hosts activos
  - Resumen final de hosts encontrados
```

### Test 2: Pentesting Completo
```
Input: "Accede a root en 10.5.0.5 y explícame la vulnerabilidad"
Expected:
  - 7-8 objetivos creados
  - Reconocimiento → Enumeración → Explotación → Post-exploit
  - Cada paso actualiza el estado
  - Informe final estructurado
```

### Test 3: Recuperación de Fallos
```
Input: "Explota la vulnerabilidad en 10.5.0.5"
Simular: Exploit falla
Expected:
  - Marcar objetivo como FAILED
  - Proponer exploit alternativo
  - Actualizar plan sin reiniciar desde cero
```

---

## 📚 Referencias y Mejoras Futuras

### V2: Multi-Agent System
- Agente "Reconocimiento" especializado
- Agente "Explotación" con base de conocimiento de exploits
- Agente "Reportes" que genera documentación automática

### V3: Aprendizaje Continuo
- Guardar estrategias exitosas en BD
- RAG con vulnerabilidades anteriores encontradas
- Fine-tuning con logs de pentesting exitosos

### V4: Paralelización
- Ejecutar múltiples objetivos en paralelo (safe)
- Threading para escaneos de red grandes
- Job queue distribuida para tareas pesadas

---

## 🎓 Conclusión

Este diseño transforma tu asistente en un **verdadero agente autónomo** que:

✅ Mantiene **estado estructurado** (no solo memoria del chat)  
✅ **Planifica antes de actuar** (no es reactivo)  
✅ **Se auto-supervisa** actualizando su checklist  
✅ **Optimiza contexto** resumiendo outputs técnicos  
✅ **Es resiliente** ante fallos y timeouts  
✅ **Plan dinámico**: Reorganiza objetivos según descubrimientos  
✅ **Control ético**: Aprobación humana para comandos peligrosos  
✅ **Zoom In**: Recupera detalles técnicos cuando el resumen no basta  
✅ **Background Jobs**: Comandos largos no bloquean el sistema  

---

## 🔥 Puntos Críticos Implementados (vs. Diseño Original)

### ⚠️ Lo que faltaba y ahora está cubierto:

| Problema Original | Solución Implementada | Sprint |
|-------------------|----------------------|--------|
| **Plan estático** → El agente no puede adaptarse | `modify_objectives`: Insertar/borrar/actualizar objetivos dinámicamente | Sprint 1 |
| **Comandos peligrosos sin control** → Riesgo ético/legal | Sistema de aprobación `AWAITING_AUTHORIZATION` + detector de patrones | Sprint 3 |
| **Resúmenes pierden detalles** → Agente "amnésico" | Tool `get_original_output`: Recupera logs completos cuando es necesario | Sprint 1 |
| **Comandos largos bloquean** → UX horrible | Background jobs + worker asíncrono + tabla `mission_jobs` | Sprint 2 |
| **Chat sobrecargado** → Difícil seguir misión | Sidebar persistente + Acordeón de pensamiento + Vista de jobs | Sprint 5 |

### 🎯 Diferencias Clave para el Tribunal

**Antes**: "Es un chatbot con comandos Linux"  
**Ahora**: "Es un agente autónomo que planifica, ejecuta y se supervisa, con control ético sobre acciones destructivas"

**Argumentos Técnicos Sólidos**:
1. **Estado persistente** → No depende solo del contexto del LLM
2. **Plan evolutivo** → Se adapta a descubrimientos inesperados
3. **Human-in-the-Loop** → Responsabilidad ética clara
4. **Optimización de contexto multi-capa** → Escalable a misiones largas
5. **UX profesional** → No es solo consola, tiene visualización de progreso

---

## 🚧 Limitaciones Conocidas y Trabajo Futuro

### Limitaciones Actuales (v1.0)

1. **Un solo agente**: No hay especialización (reconocimiento vs explotación)
2. **Sin memoria entre misiones**: Cada pentesting empieza de cero
3. **No genera informes PDF**: Output solo en la UI
4. **Sin paralelización real**: Los objetivos se ejecutan secuencialmente

### Roadmap Post-TFG (v2.0+)

#### V2: Multi-Agent System
- **Agente Coordinador**: Delega tareas a especialistas
- **Agente Reconocimiento**: Experto en escaneos y enumeración
- **Agente Explotación**: Base de conocimiento de CVEs y exploits
- **Agente Reportes**: Genera informes técnicos automáticos (Markdown/PDF)

#### V3: Aprendizaje Continuo
- **RAG con historial**: Vectorstore de misiones anteriores
- **Estrategias exitosas**: "La última vez que vi vsftpd 2.3.4 funcionó X"
- **Fine-tuning**: Entrenar con logs de pentesting reales (con permiso)

#### V4: Paralelización Real
- **Objetivos paralelos**: Escaneo de puertos + búsqueda de exploits simultáneos
- **Job queue distribuida**: Celery + Redis para comandos pesados
- **Multi-target**: Pentesting de red completa en paralelo

---

## 📚 Referencias Técnicas

### Papers y Recursos

1. **ReAct: Reasoning and Acting** (Yao et al., 2023)
   - Base teórica del loop pensamiento → acción → observación

2. **AutoGPT Architecture**
   - Sistema de objetivos y auto-supervisión

3. **LangChain Agents**
   - Inspiración para tool calling y state management

4. **Metasploit Framework**
   - Referencia para estructura de explotación automatizada

### Herramientas Utilizadas

- **FastAPI**: Backend asíncrono
- **SQLite**: Persistencia de estado
- **Shadcn/UI**: Componentes de React
- **OpenAI SDK**: Compatibilidad con múltiples LLMs
- **Docker**: Sandbox aislado (Kali Linux)

---

El sistema es **incremental**: puedes implementar Sprint 1 y ya tener valor funcional, luego ir añadiendo capas de sofisticación.

**Next Step**: Empezar por Sprint 1 - crear las tablas de BD y las tools básicas (`manage_mission` + `get_original_output`).
