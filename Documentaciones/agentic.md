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
    status TEXT DEFAULT 'PENDING',    -- PENDING | IN_PROGRESS | COMPLETED | FAILED | SKIPPED
    result_summary TEXT,              -- Resumen del resultado
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
    original_length INTEGER NOT NULL, -- Longitud del output original
    summary TEXT NOT NULL,            -- Resumen compacto
    compression_ratio REAL,           -- Ratio de compresión
    created_at TIMESTAMP,
    FOREIGN KEY (message_id) REFERENCES messages(id)
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
- Mantén IPs, puertos, versiones, CVEs
- Elimina líneas repetitivas o de progreso
- Máximo 15 líneas
- Formato conciso, bullets si es apropiado

OUTPUT:
{output[:10000]}  # Limitar a primeros 10k chars

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
  "status": "COMPLETED"  // o "FAILED" si no se logró
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

#### 4.2 Integración en el Chat

```typescript
// En Chat.tsx, detectar si hay misión activa

{activeMission && (
  <div className="sidebar-mission">
    <MissionProgress missionId={activeMission.id} />
  </div>
)}
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
    
    return {
        "active": True,
        "mission": mission,
        "objectives": db.get_objectives(mission["id"])
    }

@router.delete("/missions/{mission_id}")
async def cancel_mission(mission_id: str):
    """Cancela una misión en progreso"""
    db.complete_mission(mission_id, "CANCELLED")
    return {"status": "Mission cancelled"}
```

---

## 🚀 Plan de Rollout

### Sprint 1 (3-4 días): Foundation
- [ ] Crear tablas de BD (missions, objectives, tool_summaries)
- [ ] Implementar funciones CRUD de misiones en database.py
- [ ] Añadir tool `manage_mission` básica (create, update_objective)

### Sprint 2 (3-4 días): Tool Summarizer
- [ ] Endpoint `/summarize-tool-output`
- [ ] Integración en loop de tools con flag auto_summarize
- [ ] Testing con outputs largos (nmap, dirb, etc)

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

### Optimización de Contexto

**Problema**: Un nmap puede generar 5000 tokens, empujando la misión fuera del contexto.

**Solución Multi-Capa**:
1. **Resumen inmediato**: Outputs >1000 chars se resumen antes de pasar al LLM
2. **Estado explícito**: La misión y objetivos se reinyectan en cada turno (via tool calls)
3. **History compression**: Después de 10 turnos, resumir historial manteniendo solo:
   - Estado actual de la misión
   - Últimos 2-3 comandos
   - Hallazgos críticos

### Gestión de Fallos

El agente debe ser robusto ante:
- **Comandos que fallan**: Actualizar objetivo como FAILED y proponer alternativa
- **Timeouts**: Marcar como IN_PROGRESS y permitir reanudar
- **Conexión perdida**: Guardar estado en BD para retomar

### Seguridad

- **Validación de targets**: Verificar que IPs están en rangos autorizados
- **Rate limiting**: Evitar bucles infinitos de comandos
- **Auditoría**: Log completo de todos los comandos ejecutados en modo agéntico

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

El sistema es **incremental**: puedes implementar Fase 1 y ya tener un MVP funcional, luego añadir el summarizer, etc.

**Next Step**: Empezar por Sprint 1 - crear las tablas de BD y la tool básica de `manage_mission`.
