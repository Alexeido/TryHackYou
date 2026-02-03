"""
routes/chat.py - Endpoint de chat con soporte para streaming.
"""

import json
import asyncio
import httpx
import re
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from typing import Optional, List, Dict, Any

from models import ChatRequest, ChatResponse, ERROR_CODES
import database as db

router = APIRouter(tags=["Chat"])

# URL del sandbox para ejecutar comandos
SANDBOX_URL = "http://localhost:5000"

# =============================================================================
# MODO AGÉNTICO - DETECCIÓN Y SYSTEM PROMPT
# =============================================================================

# Palabras clave que indican intención agéntica
AGENTIC_KEYWORDS = [
    # Español
    r"de forma autónoma", r"automáticamente", r"autónomamente",
    r"hazlo completo", r"haz todo", r"realiza todo",
    r"pentesting completo", r"assessment completo", r"audit[ao]ría completa",
    r"desde cero hasta", r"de principio a fin",
    r"accede a root", r"consigue root", r"obtén root", r"logra root",
    r"compromete el sistema", r"explota el sistema",
    r"sin mi intervención", r"sin intervención",
    r"totalmente autónom[oa]",
    # Inglés
    r"autonomous(ly)?", r"automatically",
    r"full assessment", r"comprehensive (test|audit|scan)",
    r"start to finish", r"end.to.end",
    r"get root", r"achieve root", r"gain root",
    r"complete pentest", r"full pentest",
]

# Pattern compilado para eficiencia
AGENTIC_PATTERN = re.compile("|".join(AGENTIC_KEYWORDS), re.IGNORECASE)


def is_agentic_request(user_message: str) -> bool:
    """
    Detecta si el mensaje del usuario indica una intención agéntica.
    """
    return bool(AGENTIC_PATTERN.search(user_message))


# System prompt especializado para modo agéntico
AGENTIC_SYSTEM_PROMPT = """You are an **Autonomous Offensive Security Agent** running inside a specialized Kali Linux Docker sandbox. 
Your goal is to audit targets, identify vulnerabilities, and document your findings.

## 🔐 OPERATIONAL ENVIRONMENT
1. **Identity**: You are ROOT. You have full control over the sandbox.
2. **Privileges**: Do NOT use `sudo`. Do NOT ask for permission. Execute directly.
3. **Network**: You have access to a local lab network.
4. **Filesystem**: Your working directory is persistent.

## 📋 CRITICAL: AGENTIC MISSION PROTOCOL

When you receive a complex autonomous task, you MUST follow this protocol:

### STEP 1: CREATE A MISSION PLAN
Before ANY technical action, you MUST call `manage_mission` with action="create":

```json
{
  "action": "create",
  "goal": "Your high-level mission goal",
  "objectives": [
    "1. Reconnaissance - Network and service discovery",
    "2. Enumeration - Version detection and vulnerability scanning",
    "3. Exploitation - Identify and exploit vulnerabilities",
    "4. Post-exploitation - Privilege escalation and persistence",
    "5. Documentation - Report findings"
  ],
  "metadata": {"target": "10.x.x.x", "type": "autonomous_pentest"}
}
```

### STEP 2: EXECUTE WITH STATE TRACKING
For EACH objective:

a) **Mark IN_PROGRESS** before starting:
```json
{"action": "update_objective", "objective_id": 1, "status": "IN_PROGRESS"}
```

b) **Execute** the technical commands

c) **Mark COMPLETED/FAILED** immediately after with results:
```json
{
  "action": "update_objective",
  "objective_id": 1,
  "status": "COMPLETED",
  "result": "Port 80 open, Apache 2.4.49 vulnerable to CVE-2021-41773",
  "reflection": "Found critical path traversal vulnerability"
}
```

### STEP 3: ADAPT DYNAMICALLY
If you discover unexpected information, modify your plan:
```json
{
  "action": "modify_objectives",
  "mission_id": "...",
  "modifications": [
    {"type": "insert", "after_id": 2, "task": "Exploit PHP file upload vulnerability"}
  ]
}
```

### STEP 4: COMPLETE THE MISSION
When done:
```json
{"action": "complete", "mission_id": "...", "status": "COMPLETED"}
```

## 🛠️ TOOL PROTOCOL

1. **NON-INTERACTIVE ONLY**: No nano, vim, interactive shells.
2. **ASYNC AWARENESS**: Long commands return `job_id` + status `running`. Poll with `check_job_status`.
3. **ERROR RECOVERY**: Read stderr, fix syntax, retry. Don't apologize.

## ⚠️ CRITICAL RULES

1. **ALWAYS create a mission FIRST** - Never start technical work without a plan
2. **ALWAYS update objective status** - After each step, update the mission state
3. **NEVER mark complete without verification** - Only mark COMPLETED if you verified success
4. **ONE objective at a time** - Don't skip steps
5. **STATE = TRUTH** - Your mission state is the source of truth, not chat history

## 📝 RESPONSE FORMAT

For each action:
1. Show your reasoning briefly
2. Execute tool calls
3. Interpret results for the user (in Spanish)

Remember: The user is watching your mission progress in a panel. Keep it updated!"""


def build_mission_context(conversation_id: str) -> Optional[str]:
    """
    Construye el contexto de la misión activa para inyectar en el prompt.
    Incluye: estado de la misión, objetivos, progreso y SCRATCHPAD.
    Retorna None si no hay misión activa.
    """
    active_mission = db.get_active_mission(conversation_id)
    if not active_mission:
        return None
    
    mission_id = active_mission['id']
    objectives = db.get_objectives(mission_id)
    progress = db.get_mission_progress(mission_id)
    scratchpad = db.get_mission_scratchpad(mission_id)
    
    mission_context = f"""
## 🎯 ACTIVE MISSION STATE (CURRENT - DO NOT CREATE NEW MISSION)
- **Mission ID**: {mission_id}
- **Goal**: {active_mission['goal']}
- **Phase**: {active_mission.get('current_phase', 'Not set')}
- **Progress**: {progress['completed']}/{progress['total']} objectives

### Objectives:"""
    
    for obj in objectives:
        status_emoji = {
            'PENDING': '⏸️',
            'IN_PROGRESS': '🔄',
            'COMPLETED': '✅',
            'FAILED': '❌',
            'SKIPPED': '⏭️',
            'AWAITING_AUTHORIZATION': '🛑'
        }.get(obj['status'], '❓')
        mission_context += f"\n{status_emoji} [{obj['id']}] {obj['task']} - {obj['status']}"
        if obj.get('result_summary'):
            mission_context += f"\n   Result: {obj['result_summary'][:150]}..."
    
    # INCLUIR SCRATCHPAD - CRÍTICO para persistencia de hallazgos
    if scratchpad:
        mission_context += f"\n\n### 📝 Your Scratchpad (saved findings):\n```\n{scratchpad}\n```"
    else:
        mission_context += "\n\n### 📝 Your Scratchpad: (empty - use write_scratchpad to save important findings)"
    
    mission_context += "\n\n**⚠️ CRITICAL: A mission already exists! DO NOT call manage_mission(action='create'). CONTINUE from where you left off. Check the objectives above and proceed with the next PENDING or IN_PROGRESS item.**"
    
    return mission_context


def update_system_with_mission_context(messages: List[Dict], conversation_id: str) -> List[Dict]:
    """
    Actualiza el system prompt con el contexto de misión actual.
    Esto asegura que el modelo siempre sepa qué misión está activa aunque
    el historial se haya truncado.
    """
    mission_context = build_mission_context(conversation_id)
    if not mission_context:
        return messages
    
    # Buscar el system prompt
    if messages and messages[0].get('role') == 'system':
        current_system = messages[0].get('content', '')
        
        # Eliminar cualquier misión anterior del system prompt
        # (buscar desde "## 🎯 ACTIVE MISSION" hasta el siguiente "##" o fin)
        import re
        pattern = r'\n## 🎯 ACTIVE MISSION STATE.*?(?=\n## |\Z)'
        current_system = re.sub(pattern, '', current_system, flags=re.DOTALL)
        
        # Añadir el contexto de misión actualizado al final del system prompt
        messages[0]['content'] = current_system.rstrip() + "\n" + mission_context
        print(f"📋 System prompt actualizado con misión activa")
    
    return messages


async def execute_tool_call(tool_call: Dict[str, Any], conversation_id: str, leaf_id: Optional[int] = None) -> str:
    """
    Ejecuta una tool call en el sandbox y retorna el resultado.
    Si el comando queda en background (wait_time), registra el job para seguimiento.
    """
    function_name = tool_call.get("function", {}).get("name")
    function_args_str = tool_call.get("function", {}).get("arguments", "{}")
    tool_call_id = tool_call.get("id")  # ID del tool call para referencia
    
    print(f"🔧 Ejecutando tool: {function_name}")
    print(f"🔧 Argumentos raw: {function_args_str[:500]}{'...' if len(function_args_str) > 500 else ''}")
    
    try:
        function_args = json.loads(function_args_str)
    except json.JSONDecodeError as e:
        print(f"❌ Error parseando argumentos JSON: {e}")
        print(f"❌ Argumentos raw completos: {function_args_str}")
        return f"Error: argumentos inválidos (JSON malformado): {str(e)}"
    
    if function_name == "execute_command":
        command = function_args.get("command")
        wait_time = function_args.get("wait_time")
        exit_time = function_args.get("exit_time")
        
        print(f"🔧 Comando extraído: {command[:300] if command else 'None'}{'...' if command and len(command) > 300 else ''}")
        
        if not command:
            return "Error: comando no especificado"
        
        # ====================================================================
        # SPRINT 3: ANÁLISIS DE SEGURIDAD DEL COMANDO
        # ====================================================================
        from security import analyze_command, is_dangerous_command, get_approval_message
        
        analysis = analyze_command(command)
        
        # Obtener info de misión activa para tracking
        active_mission = db.get_active_mission(conversation_id)
        mission_id = active_mission['id'] if active_mission else None
        current_objective_id = None
        
        if active_mission:
            objectives = db.get_objectives(mission_id)
            current_obj = next(
                (obj for obj in objectives if obj['status'] == 'IN_PROGRESS'),
                objectives[0] if objectives else None
            )
            current_objective_id = current_obj['id'] if current_obj else None
        
        # Registrar en auditoría
        audit_id = db.add_audit_log(
            conversation_id=conversation_id,
            command=command,
            risk_level=analysis["risk_level"],
            requires_approval=analysis["requires_approval"],
            reason=analysis["reason"],
            mission_id=mission_id,
            objective_id=current_objective_id,
            status="PENDING" if analysis["requires_approval"] else "ALLOWED"
        )
        
        # Si requiere aprobación, NO ejecutar y marcar objetivo como pendiente
        if analysis["requires_approval"]:
            print(f"🛑 Comando BLOQUEADO - Requiere aprobación ({analysis['risk_level']})")
            
            # Marcar objetivo como esperando autorización
            if current_objective_id:
                db.update_objective_approval(
                    objective_id=current_objective_id,
                    requires_approval=True,
                    approval_status="AWAITING_AUTHORIZATION",
                    pending_command=command
                )
                db.update_objective_status(current_objective_id, "AWAITING_AUTHORIZATION")
            
            # Devolver mensaje al LLM explicando la situación
            return json.dumps({
                "status": "AWAITING_AUTHORIZATION",
                "risk_level": analysis["risk_level"],
                "command": command,
                "reason": analysis["reason"],
                "message": "Este comando requiere aprobación humana antes de ejecutarse.",
                "matched_patterns": [p["description"] for p in analysis["matched_patterns"]],
                "objective_id": current_objective_id,
                "audit_id": audit_id,
                "next_steps": [
                    "El usuario debe aprobar o rechazar el comando",
                    "Usa manage_mission para verificar el estado del objetivo",
                    "Si es rechazado, considera una alternativa o salta el objetivo"
                ]
            })
        
        # ====================================================================
        # COMANDO SEGURO - EJECUTAR NORMALMENTE
        # ====================================================================
        
        # Actualizar auditoría a EXECUTING
        db.update_audit_log(audit_id, "EXECUTING")
        
        # Log del comando que vamos a ejecutar
        print(f"📤 Enviando a sandbox: {command[:200]}{'...' if len(command) > 200 else ''}")
        
        # Ejecutar en el sandbox
        async with httpx.AsyncClient(timeout=120.0) as client:
            payload = {
                "command": command,
                "conversation_id": conversation_id,
            }
            if wait_time is not None:
                payload["wait_time"] = wait_time
            if exit_time is not None:
                payload["exit_time"] = exit_time
            
            try:
                print(f"📡 POST {SANDBOX_URL}/execute con payload de {len(json.dumps(payload))} bytes")
                response = await client.post(f"{SANDBOX_URL}/execute", json=payload)
                print(f"📥 Respuesta del sandbox: status={response.status_code}")
                response.raise_for_status()
                result = response.json()
                
                # Formatear salida
                output_parts = []
                
                # Incluir job_id si el proceso sigue corriendo (background)
                if result.get("status") == "running" and result.get("job_id"):
                    job_id = result['job_id']
                    output_parts.append(f"JOB_ID: {job_id}")
                    output_parts.append(f"STATUS: running (command executing in background)")
                    output_parts.append("NOTE: You will receive the full output automatically when the command completes.")
                    
                    # Registrar job para seguimiento automático
                    if leaf_id:
                        try:
                            db.add_pending_job(job_id, conversation_id, leaf_id, command, tool_call_id)
                            print(f"📋 Job {job_id[:8]} registrado para seguimiento (tool_call_id={tool_call_id})")
                            
                            # SPRINT 2: Registrar también en mission_jobs si hay misión activa
                            active_mission = db.get_active_mission(conversation_id)
                            if active_mission:
                                mission_id = active_mission['id']
                                # Obtener el objetivo actual en progreso
                                objectives = db.get_objectives(mission_id)
                                current_objective = next(
                                    (obj for obj in objectives if obj['status'] == 'IN_PROGRESS'),
                                    objectives[0] if objectives else None  # Fallback al primero
                                )
                                if current_objective:
                                    db.add_mission_job(job_id, mission_id, current_objective['id'], command)
                                    print(f"🎯 Job vinculado a misión {mission_id[:12]} objetivo {current_objective['id']}")
                        except Exception as e:
                            print(f"⚠️ Error registrando job: {e}")
                
                if result.get("stdout"):
                    output_parts.append(f"STDOUT:\n{result['stdout']}")
                if result.get("stderr"):
                    output_parts.append(f"STDERR:\n{result['stderr']}")
                if result.get("return_code") is not None:
                    output_parts.append(f"EXIT CODE: {result['return_code']}")
                
                final_output = "\n\n".join(output_parts) if output_parts else "Command executed (no output)"
                
                # Actualizar auditoría con resultado
                result_summary = f"Exit code: {result.get('return_code', 'N/A')}"
                if result.get("status") == "running":
                    result_summary = f"Job running: {result.get('job_id', 'unknown')[:12]}"
                db.update_audit_log(audit_id, "COMPLETED", result_summary)
                
                return final_output
                
            except httpx.TimeoutException as e:
                print(f"⏱️ Timeout ejecutando comando: {command[:100]}")
                db.update_audit_log(audit_id, "FAILED", "Timeout (>120s)")
                return f"Error: Timeout ejecutando comando (más de 120s)"
            except httpx.ConnectError as e:
                print(f"🔌 Error de conexión al sandbox: {e}")
                db.update_audit_log(audit_id, "FAILED", f"Connection error: {str(e)[:100]}")
                return f"Error: No se pudo conectar al sandbox - {str(e)}"
            except httpx.HTTPStatusError as e:
                print(f"🚫 Error HTTP del sandbox: {e.response.status_code}")
                db.update_audit_log(audit_id, "FAILED", f"HTTP {e.response.status_code}")
                return f"Error HTTP {e.response.status_code} del sandbox: {str(e)}"
            except httpx.HTTPError as e:
                print(f"❌ Error HTTP genérico: {e}")
                db.update_audit_log(audit_id, "FAILED", f"HTTP error: {str(e)[:100]}")
                return f"Error ejecutando comando: {str(e)}"
            except json.JSONDecodeError as e:
                print(f"📄 Error parseando respuesta JSON del sandbox: {e}")
                db.update_audit_log(audit_id, "FAILED", "Invalid JSON response")
                return f"Error: Respuesta inválida del sandbox (no es JSON válido)"
            except Exception as e:
                print(f"💥 Error inesperado ejecutando comando: {type(e).__name__}: {e}")
                db.update_audit_log(audit_id, "FAILED", f"{type(e).__name__}: {str(e)[:80]}")
                return f"Error inesperado: {type(e).__name__}: {str(e)}"
    
    elif function_name == "check_job_status":
        job_id = function_args.get("job_id")
        wait = function_args.get("wait", 0)
        
        if not job_id:
            return "Error: job_id no especificado"
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                url = f"{SANDBOX_URL}/status/{job_id}"
                if wait:
                    url += f"?wait={wait}"
                
                response = await client.get(url)
                response.raise_for_status()
                result = response.json()
                
                # Formatear resultado
                output_parts = []
                output_parts.append(f"JOB_ID: {job_id}")
                output_parts.append(f"STATUS: {result.get('status', 'unknown')}")
                
                if result.get("stdout"):
                    output_parts.append(f"STDOUT:\n{result['stdout']}")
                if result.get("stderr"):
                    output_parts.append(f"STDERR:\n{result['stderr']}")
                if result.get("return_code") is not None:
                    output_parts.append(f"EXIT CODE: {result['return_code']}")
                
                return "\n".join(output_parts)
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return f"JOB_ID: {job_id}\nSTATUS: not_found\nERROR: El job ya no existe. Puede que haya finalizado y sido eliminado del sistema."
                return f"JOB_ID: {job_id}\nSTATUS: error\nERROR: Error HTTP {e.response.status_code} consultando el job"
            except httpx.HTTPError as e:
                return f"JOB_ID: {job_id}\nSTATUS: error\nERROR: No se pudo conectar con el sandbox"
    
    elif function_name == "stop_job":
        """
        Detiene un job en background que está corriendo en el sandbox.
        Útil cuando un comando está tardando mucho o no es útil.
        """
        job_id = function_args.get("job_id")
        
        if not job_id:
            return json.dumps({"error": "job_id no especificado"})
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Llamar al endpoint del sandbox para detener el job
                response = await client.post(f"{SANDBOX_URL}/stop/{job_id}")
                response.raise_for_status()
                result = response.json()
                
                print(f"🛑 Job {job_id[:8]} detenido exitosamente")
                
                return json.dumps({
                    "status": "success",
                    "message": f"Job {job_id} detenido exitosamente",
                    "job_id": job_id,
                    "sandbox_response": result
                })
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return json.dumps({
                        "status": "not_found",
                        "message": f"Job {job_id} no existe o ya terminó",
                        "job_id": job_id
                    })
                return json.dumps({
                    "status": "error",
                    "message": f"Error HTTP {e.response.status_code} al detener job",
                    "job_id": job_id
                })
            except httpx.HTTPError as e:
                return json.dumps({
                    "status": "error",
                    "message": f"Error de conexión: {str(e)}",
                    "job_id": job_id
                })
            except Exception as e:
                return json.dumps({
                    "status": "error",
                    "message": f"Error inesperado: {str(e)}",
                    "job_id": job_id
                })
    
    # ==========================================================================
    # TOOLS AGÉNTICAS - GESTIÓN DE MISIONES
    # ==========================================================================
    
    elif function_name == "manage_mission":
        """
        Tool para que el LLM gestione su propia misión autónoma.
        
        Actions:
            - create: Crea una nueva misión con objetivos
            - update_objective: Actualiza estado de un objetivo
            - update_phase: Cambia la fase actual de la misión
            - complete: Finaliza la misión
            - get_status: Consulta el estado actual
            - modify_objectives: Reorganiza el plan (insertar/borrar/actualizar)
        """
        action = function_args.get("action")
        
        if action == "create":
            goal = function_args.get("goal")
            objectives_list = function_args.get("objectives", [])
            metadata = function_args.get("metadata")
            
            if not goal:
                return json.dumps({"error": "Se requiere 'goal' para crear una misión"})
            
            # Crear misión
            mission_id = db.create_mission(conversation_id, goal, metadata)
            
            # Añadir objetivos
            obj_ids = []
            if objectives_list:
                obj_ids = db.add_objectives(mission_id, objectives_list)
            
            # Actualizar estado a IN_PROGRESS
            db.update_mission_status(mission_id, "IN_PROGRESS")
            
            return json.dumps({
                "status": "success",
                "message": f"✅ Misión creada exitosamente. Mission ID: {mission_id}",
                "mission_id": mission_id,
                "objective_ids": obj_ids,
                "objectives_count": len(obj_ids),
                "CRITICAL_INSTRUCTION": f"⚠️ ALWAYS use mission_id='{mission_id}' in ALL subsequent manage_mission calls. First objective ID is {obj_ids[0] if obj_ids else 'N/A'}.",
                "NEXT_ACTION": f"Now execute: manage_mission(action='update_objective', mission_id='{mission_id}', objective_id={obj_ids[0] if obj_ids else 1}, status='IN_PROGRESS') and then execute_command for the first task."
            })
        
        elif action == "update_objective":
            objective_id = function_args.get("objective_id")
            status = function_args.get("status")
            result = function_args.get("result")
            reflection = function_args.get("reflection")
            
            if not objective_id or not status:
                return json.dumps({"error": "Se requiere 'objective_id' y 'status'"})
            
            # Validar status
            valid_statuses = ['PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'SKIPPED', 'AWAITING_AUTHORIZATION']
            if status not in valid_statuses:
                return json.dumps({"error": f"Status inválido. Válidos: {valid_statuses}"})
            
            # Actualizar
            success = db.update_objective_status(objective_id, status, result, reflection)
            
            if not success:
                return json.dumps({"error": f"Objetivo {objective_id} no encontrado"})
            
            # Obtener progreso actualizado
            objective = db.get_objective_by_id(objective_id)
            if objective:
                progress = db.get_mission_progress(objective['mission_id'])
                
                # Determinar siguiente acción según el estado
                next_action = ""
                if status == "COMPLETED":
                    if progress['pending'] > 0 or progress['in_progress'] < progress['total']:
                        next_action = "CONTINÚA: Pasa al siguiente objetivo pendiente de la misión."
                    else:
                        next_action = "MISIÓN CASI COMPLETA: Usa manage_mission con action='complete' para finalizar."
                elif status == "IN_PROGRESS":
                    next_action = "CONTINÚA: Ejecuta los comandos necesarios para completar este objetivo."
                elif status == "FAILED" or status == "SKIPPED":
                    next_action = "CONTINÚA: Pasa al siguiente objetivo disponible."
                
                return json.dumps({
                    "status": "success",
                    "message": f"Objetivo {objective_id} actualizado a {status}",
                    "progress": progress,
                    "NEXT_ACTION": next_action
                })
            
            return json.dumps({
                "status": "success", 
                "message": f"Objetivo {objective_id} actualizado",
                "NEXT_ACTION": "CONTINÚA: Verifica el estado de la misión y continúa con el siguiente paso."
            })
        
        elif action == "update_phase":
            mission_id = function_args.get("mission_id")
            phase = function_args.get("phase")
            
            if not mission_id or not phase:
                return json.dumps({"error": "Se requiere 'mission_id' y 'phase'"})
            
            db.update_mission_phase(mission_id, phase)
            
            # Obtener siguiente objetivo pendiente para dar contexto
            objectives = db.get_objectives(mission_id)
            next_pending = next((obj for obj in objectives if obj['status'] in ['PENDING', 'IN_PROGRESS']), None)
            next_task = next_pending['task'] if next_pending else "Verificar estado final"
            
            return json.dumps({
                "status": "success",
                "message": f"Fase actualizada a: {phase}",
                "new_phase": phase,
                "NEXT_ACTION": f"CONTINÚA INMEDIATAMENTE: Ejecuta la siguiente tarea - {next_task}"
            })
        
        elif action == "complete":
            mission_id = function_args.get("mission_id")
            final_status = function_args.get("status", "COMPLETED")
            
            if not mission_id:
                return json.dumps({"error": "Se requiere 'mission_id'"})
            
            # Validar status
            if final_status not in ['COMPLETED', 'FAILED', 'CANCELLED']:
                final_status = 'COMPLETED'
            
            db.complete_mission(mission_id, final_status)
            
            # Obtener resumen final
            progress = db.get_mission_progress(mission_id)
            
            return json.dumps({
                "status": "success",
                "message": f"Misión finalizada con estado: {final_status}",
                "final_progress": progress,
                "MISSION_COMPLETED": True,  # Flag para NO forzar continuación
                "NEXT_ACTION": "STOP: La misión ha finalizado. Presenta el informe final al usuario y espera instrucciones."
            })
        
        elif action == "get_status":
            mission_id = function_args.get("mission_id")
            
            # Si no se proporciona mission_id, buscar la activa de esta conversación
            if not mission_id:
                active_mission = db.get_active_mission(conversation_id)
                if not active_mission:
                    return json.dumps({
                        "status": "no_active_mission",
                        "message": "No hay misión activa en esta conversación"
                    })
                mission_id = active_mission['id']
            
            mission = db.get_mission(mission_id)
            if not mission:
                return json.dumps({"error": f"Misión {mission_id} no encontrada"})
            
            objectives = db.get_objectives(mission_id)
            progress = db.get_mission_progress(mission_id)
            
            # Obtener scratchpad para incluir en el status
            scratchpad = db.get_mission_scratchpad(mission_id)
            
            return json.dumps({
                "status": "success",
                "mission": {
                    "id": mission['id'],
                    "goal": mission['goal'],
                    "current_phase": mission['current_phase'],
                    "status": mission['status']
                },
                "objectives": [
                    {
                        "id": obj['id'],
                        "order": obj['order_index'],
                        "task": obj['task'],
                        "status": obj['status'],
                        "result": obj['result_summary']
                    }
                    for obj in objectives
                ],
                "progress": progress,
                "scratchpad": scratchpad if scratchpad else "(empty - use write_scratchpad to save important findings)"
            })
        
        elif action == "modify_objectives":
            mission_id = function_args.get("mission_id")
            modifications = function_args.get("modifications", [])
            
            if not mission_id:
                # Buscar misión activa
                active_mission = db.get_active_mission(conversation_id)
                if not active_mission:
                    return json.dumps({"error": "No hay misión activa y no se proporcionó mission_id"})
                mission_id = active_mission['id']
            
            results = []
            for mod in modifications:
                mod_type = mod.get("type")
                
                if mod_type == "insert":
                    after_id = mod.get("after_id")
                    task = mod.get("task")
                    if after_id and task:
                        try:
                            new_id = db.insert_objective_after(mission_id, after_id, task)
                            results.append({"type": "insert", "new_id": new_id, "task": task})
                        except ValueError as e:
                            results.append({"type": "insert", "error": str(e)})
                
                elif mod_type == "delete":
                    obj_id = mod.get("objective_id")
                    if obj_id:
                        db.delete_objective(obj_id)
                        results.append({"type": "delete", "objective_id": obj_id})
                
                elif mod_type == "update":
                    obj_id = mod.get("objective_id")
                    new_task = mod.get("new_task")
                    if obj_id and new_task:
                        db.update_objective_task(obj_id, new_task)
                        results.append({"type": "update", "objective_id": obj_id, "new_task": new_task})
            
            # Obtener objetivos actualizados
            objectives = db.get_objectives(mission_id)
            
            return json.dumps({
                "status": "success",
                "message": f"Plan reorganizado con {len(results)} modificaciones",
                "modifications": results,
                "updated_objectives": [
                    {"id": obj['id'], "order": obj['order_index'], "task": obj['task'], "status": obj['status']}
                    for obj in objectives
                ]
            })
        
        # ======================================================================
        # SCRATCHPAD / MEMORIA DEL AGENTE
        # ======================================================================
        
        elif action == "write_scratchpad":
            content = function_args.get("scratchpad_content", "")
            mode = function_args.get("scratchpad_mode", "append")  # append por defecto
            mission_id = function_args.get("mission_id")
            
            if not content:
                return json.dumps({"error": "Se requiere 'scratchpad_content' para escribir"})
            
            # Buscar misión activa si no se proporciona
            if not mission_id:
                active_mission = db.get_active_mission(conversation_id)
                if not active_mission:
                    return json.dumps({"error": "No hay misión activa. Crea una misión primero."})
                mission_id = active_mission['id']
            
            success = db.update_mission_scratchpad(mission_id, content, mode)
            
            if success:
                return json.dumps({
                    "status": "success",
                    "message": f"Notas guardadas en scratchpad (modo: {mode})",
                    "saved_content": content[:100] + "..." if len(content) > 100 else content
                })
            else:
                return json.dumps({"error": "No se pudo actualizar el scratchpad"})
        
        elif action == "read_scratchpad":
            mission_id = function_args.get("mission_id")
            
            # Buscar misión activa si no se proporciona
            if not mission_id:
                active_mission = db.get_active_mission(conversation_id)
                if not active_mission:
                    return json.dumps({
                        "status": "no_scratchpad",
                        "message": "No hay misión activa con scratchpad"
                    })
                mission_id = active_mission['id']
            
            content = db.get_mission_scratchpad(mission_id)
            
            if content:
                return json.dumps({
                    "status": "success",
                    "scratchpad": content,
                    "length": len(content)
                })
            else:
                return json.dumps({
                    "status": "empty",
                    "message": "El scratchpad está vacío. Usa write_scratchpad para guardar notas."
                })
        
        elif action == "clear_scratchpad":
            mission_id = function_args.get("mission_id")
            
            if not mission_id:
                active_mission = db.get_active_mission(conversation_id)
                if not active_mission:
                    return json.dumps({"error": "No hay misión activa"})
                mission_id = active_mission['id']
            
            success = db.clear_mission_scratchpad(mission_id)
            
            return json.dumps({
                "status": "success" if success else "error",
                "message": "Scratchpad limpiado" if success else "Error al limpiar scratchpad"
            })
        
        else:
            return json.dumps({
                "error": f"Action '{action}' no reconocida",
                "valid_actions": ["create", "update_objective", "update_phase", "complete", "get_status", "modify_objectives", "write_scratchpad", "read_scratchpad", "clear_scratchpad"]
            })
    
    # ==========================================================================
    # TOOLS AGÉNTICAS - RECUPERACIÓN DE OUTPUTS ORIGINALES (ZOOM IN)
    # ==========================================================================
    
    elif function_name == "get_original_output":
        """
        Recupera el output original completo de un tool_call anterior.
        Útil cuando el resumen no contiene suficiente información.
        
        Args:
            tool_call_id: ID del tool_call cuyo output original se necesita
        """
        tool_call_id_to_find = function_args.get("tool_call_id")
        
        if not tool_call_id_to_find:
            return json.dumps({"error": "Se requiere 'tool_call_id'"})
        
        # Buscar en la tabla de summaries
        summary_entry = db.get_tool_summary_entry(tool_call_id_to_find)
        
        if not summary_entry:
            return json.dumps({
                "error": "No se encontró el output original",
                "tool_call_id": tool_call_id_to_find,
                "note": "El output puede no haber sido resumido o el ID es incorrecto"
            })
        
        original = summary_entry['original_output']
        
        return json.dumps({
            "status": "success",
            "tool_call_id": tool_call_id_to_find,
            "original_length": len(original),
            "summary_length": len(summary_entry['summary']),
            "output": original,
            "note": "Este es el output COMPLETO sin resumir. Analiza el detalle que necesitabas."
        })
    
    return f"Error: tool '{function_name}' no implementada"


# Cache para capacidades de modelos Ollama (evitar consultas repetidas)
_ollama_capabilities_cache: Dict[str, Dict] = {}


async def check_ollama_model_capabilities(ollama_url: str, model_id: str) -> Dict[str, bool]:
    """
    Consulta las capacidades de un modelo Ollama via /api/show.
    Retorna dict con las capacidades (ej: {"tools": True, "completion": True})
    """
    cache_key = f"{ollama_url}:{model_id}"
    
    # Verificar cache
    if cache_key in _ollama_capabilities_cache:
        return _ollama_capabilities_cache[cache_key]
    
    capabilities = {"tools": False, "completion": False, "vision": False}
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Ollama /api/show devuelve info del modelo incluyendo capabilities
            response = await client.post(
                f"{ollama_url.rstrip('/')}/api/show",
                json={"name": model_id}
            )
            response.raise_for_status()
            data = response.json()
            
            # Las capacidades vienen en data.get("capabilities", [])
            # Ejemplo: ["completion", "tools"]
            model_capabilities = data.get("capabilities", [])
            
            for cap in model_capabilities:
                if cap in capabilities:
                    capabilities[cap] = True
            
            print(f"🔍 Ollama model '{model_id}' capabilities: {model_capabilities}")
            
    except Exception as e:
        print(f"⚠️ No se pudieron obtener capacidades de '{model_id}': {e}")
        # Por defecto asumimos que NO soporta tools (más seguro)
        capabilities["completion"] = True
    
    # Guardar en cache
    _ollama_capabilities_cache[cache_key] = capabilities
    return capabilities


def clear_ollama_capabilities_cache(ollama_url: str = None, model_id: str = None):
    """Limpia la cache de capacidades (útil si se actualiza un modelo)"""
    global _ollama_capabilities_cache
    if ollama_url and model_id:
        cache_key = f"{ollama_url}:{model_id}"
        _ollama_capabilities_cache.pop(cache_key, None)
    else:
        _ollama_capabilities_cache = {}


def get_client(provider: str, api_key: str) -> AsyncOpenAI:
    """
    Factory: devuelve un cliente OpenAI configurado para el proveedor correcto.
    Para Ollama, api_key es la URL del servidor (ej: http://localhost:11434)
    """
    if provider == "openai":
        return AsyncOpenAI(api_key=api_key)
    
    elif provider == "google":
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
    
    elif provider == "ollama":
        # Para Ollama, api_key contiene la URL del servidor
        # Ollama expone una API compatible con OpenAI en /v1
        base_url = api_key.rstrip('/') + '/v1'
        return AsyncOpenAI(
            api_key="ollama",  # Ollama no requiere API key real
            base_url=base_url
        )
    
    else:
        raise ValueError(f"Proveedor '{provider}' no soportado")


@router.post("/chat")
async def chat_completion(req: ChatRequest):
    """
    Endpoint universal de chat con soporte para streaming.
    
    Si stream=False: devuelve ChatResponse
    Si stream=True: devuelve StreamingResponse con SSE
    """
    
    # ==========================================================================
    # 1. CREAR O OBTENER CONVERSACIÓN
    # ==========================================================================
    
    if req.conversation_id:
        # Verificar que existe
        conv = db.get_conversation(req.conversation_id)
        if not conv:
            raise HTTPException(
                status_code=404,
                detail={"code": "CONVERSATION_NOT_FOUND", "message": "Conversación no encontrada"}
            )
        conversation_id = req.conversation_id
    else:
        # Crear nueva conversación
        title = req.user_message[:50] + "..." if len(req.user_message) > 50 else req.user_message
        result = db.create_conversation(
            title=title,
            system_prompt=req.system_prompt
        )
        conversation_id = result["id"]
        print(f"📝 Nueva conversación creada: {conversation_id}")
    
    # ==========================================================================
    # 2. DETERMINAR MENSAJE PADRE
    # ==========================================================================
    
    if req.parent_message_id:
        parent_id = req.parent_message_id
    else:
        # Usar active_leaf como padre
        parent_id = db.get_last_message_id(conversation_id)
    
    # ==========================================================================
    # 3. GUARDAR MENSAJE DEL USUARIO (o usar existente si es regeneración)
    # ==========================================================================
    
    print(f"🔍 DEBUG - regenerate={req.regenerate}, parent_message_id={req.parent_message_id}")
    
    if req.regenerate and req.parent_message_id:
        # Regeneración: usar el mensaje de usuario existente como padre
        user_msg_id = req.parent_message_id
        print(f"🔄 Regenerando respuesta para mensaje: {user_msg_id}")
    else:
        # Nuevo mensaje: guardar mensaje del usuario
        user_msg_id = db.add_message(
            conversation_id=conversation_id,
            role="user",
            content=req.user_message,
            parent_id=parent_id
        )
        print(f"💬 Mensaje de usuario guardado: {user_msg_id}")
    
    # ==========================================================================
    # 4. RECONSTRUIR CONTEXTO PARA EL LLM
    # ==========================================================================
    
    messages_for_llm = db.get_conversation_for_llm(user_msg_id)
    
    # ==========================================================================
    # 4.5 DETECCIÓN DE MODO AGÉNTICO
    # ==========================================================================
    
    is_agentic = is_agentic_request(req.user_message)
    
    if is_agentic:
        print("🤖 MODO AGÉNTICO DETECTADO - Inyectando system prompt especializado")
        
        # Modificar el system prompt (primer mensaje) para incluir instrucciones agénticas
        if messages_for_llm and messages_for_llm[0].get("role") == "system":
            # Combinar el prompt original con el agéntico
            original_prompt = messages_for_llm[0].get("content", "")
            messages_for_llm[0]["content"] = AGENTIC_SYSTEM_PROMPT + "\n\n---\nADDITIONAL CONTEXT:\n" + original_prompt
        else:
            # Si no hay system prompt, insertar uno nuevo
            messages_for_llm.insert(0, {
                "role": "system",
                "content": AGENTIC_SYSTEM_PROMPT
            })
        
        # Inyectar contexto de misión activa EN EL SYSTEM PROMPT (no como mensaje separado)
        # Esto asegura que NO se pierda cuando el historial se trunca
        messages_for_llm = update_system_with_mission_context(messages_for_llm, conversation_id)
    
    # ==========================================================================
    # 5. LLAMAR AL LLM
    # ==========================================================================
    
    try:
        client = get_client(req.provider, req.api_key)
        
        print(f"🤖 Chat con {req.provider} -> {req.model_id} (stream={req.stream})")
        
        # Verificar capacidades de tools para Ollama
        tools_to_send = req.tools
        if req.provider == "ollama" and req.tools:
            # Para Ollama, verificar si el modelo soporta tools
            ollama_url = req.api_key  # En Ollama, api_key contiene la URL
            capabilities = await check_ollama_model_capabilities(ollama_url, req.model_id)
            
            if not capabilities.get("tools", False):
                print(f"⚠️ Modelo '{req.model_id}' no soporta tools, deshabilitando...")
                tools_to_send = None
        
        if req.stream:
            # MODO STREAMING
            return StreamingResponse(
                stream_chat_response(
                    client=client,
                    model_id=req.model_id,
                    messages=messages_for_llm,
                    tools=tools_to_send,
                    conversation_id=conversation_id,
                    user_msg_id=user_msg_id,
                    temperature=req.temperature,
                    top_p=req.top_p,
                    max_tokens=req.max_tokens,
                    auto_summarize=req.auto_summarize,
                    summarizer_model=req.summarizer_model
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"  # Para nginx
                }
            )
        else:
            # MODO NORMAL
            return await normal_chat_response(
                client=client,
                model_id=req.model_id,
                messages=messages_for_llm,
                tools=tools_to_send,
                conversation_id=conversation_id,
                user_msg_id=user_msg_id,
                temperature=req.temperature,
                top_p=req.top_p,
                max_tokens=req.max_tokens
            )
    
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error en chat: {error_msg}")
        
        # Detectar tipo de error
        if "401" in error_msg or "authentication" in error_msg.lower():
            raise HTTPException(
                status_code=401,
                detail={"code": "INVALID_API_KEY", "message": "API Key inválida", "provider": req.provider}
            )
        elif "429" in error_msg:
            raise HTTPException(
                status_code=429,
                detail={"code": "RATE_LIMITED", "message": "Rate limit excedido"}
            )
        elif "404" in error_msg:
            raise HTTPException(
                status_code=404,
                detail={"code": "MODEL_NOT_FOUND", "message": f"Modelo {req.model_id} no encontrado"}
            )
        else:
            raise HTTPException(
                status_code=500,
                detail={"code": "PROVIDER_ERROR", "message": error_msg[:200]}
            )


async def normal_chat_response(
    client: AsyncOpenAI,
    model_id: str,
    messages: List[Dict],
    tools: Optional[List[Dict]],
    conversation_id: str,
    user_msg_id: int,
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
    max_tokens: Optional[int] = None
) -> ChatResponse:
    """
    Procesa la respuesta del LLM en modo normal (sin streaming).
    """
    params = {
        "model": model_id,
        "messages": messages,
        "tools": tools if tools else None,
        "tool_choice": "auto" if tools else None,
    }
    
    # Añadir parámetros opcionales solo si se especifican
    if temperature is not None:
        params["temperature"] = temperature
    if top_p is not None:
        params["top_p"] = top_p
    if max_tokens is not None:
        params["max_tokens"] = max_tokens
    
    response = await client.chat.completions.create(**params)
    
    msg = response.choices[0].message
    finish_reason = response.choices[0].finish_reason
    
    # Procesar tool_calls si existen
    tool_calls_json = None
    if msg.tool_calls:
        tool_calls_json = json.dumps([t.model_dump() for t in msg.tool_calls])
    
    # Guardar respuesta del asistente
    assistant_msg_id = db.add_message(
        conversation_id=conversation_id,
        role="assistant",
        content=msg.content,
        parent_id=user_msg_id,
        tool_calls=tool_calls_json,
        model_used=model_id
    )
    
    # Actualizar active_leaf y timestamp
    db.update_conversation_leaf(conversation_id, assistant_msg_id)
    db.update_conversation_timestamp(conversation_id)
    
    print(f"✅ Respuesta guardada: {assistant_msg_id}")
    
    return ChatResponse(
        conversation_id=conversation_id,
        user_message_id=user_msg_id,
        assistant_message_id=assistant_msg_id,
        role="assistant",
        content=msg.content,
        tool_calls=[t.model_dump() for t in msg.tool_calls] if msg.tool_calls else None,
        finish_reason=finish_reason
    )


async def stream_chat_response(
    client: AsyncOpenAI,
    model_id: str,
    messages: List[Dict],
    tools: Optional[List[Dict]],
    conversation_id: str,
    user_msg_id: int,
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
    max_tokens: Optional[int] = None,
    # Parámetros de auto-summarize (Sprint 2)
    auto_summarize: bool = True,
    summarizer_model: Optional[str] = None
):
    """
    Generador asíncrono para streaming con Server-Sent Events (SSE).
    """
    import time
    stream_start = time.time()
    stream_id = f"{conversation_id}_{user_msg_id}_{int(stream_start)}"
    print(f"🌊 STREAM INICIADO [{stream_id}] - conv={conversation_id}, user_msg={user_msg_id}")
    
    full_content = ""
    tool_calls_accumulator = []
    finish_reason = "stop"
    reasoning_content = ""  # DeepSeek reasoning mode
    
    # SANITIZACIÓN PRE-ENVÍO: Asegurar que ningún mensaje tenga content=null
    # DeepSeek y otros proveedores no aceptan null, solo string vacío
    for msg in messages:
        if msg.get('content') is None:
            msg['content'] = ""
    
    try:
        params = {
            "model": model_id,
            "messages": messages,
            "tools": tools if tools else None,
            "tool_choice": "auto" if tools else None,
            "stream": True
        }
        
        # Añadir parámetros opcionales solo si se especifican
        if temperature is not None:
            params["temperature"] = temperature
        if top_p is not None:
            params["top_p"] = top_p
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        
        stream = await client.chat.completions.create(**params)
        
        async for chunk in stream:
            if not chunk.choices:
                continue
                
            delta = chunk.choices[0].delta
            chunk_finish = chunk.choices[0].finish_reason
            
            # DEBUG: Ver estructura completa del chunk para Gemini 3
            if delta.tool_calls and len(tool_calls_accumulator) == 0:
                # Solo logear el primer tool_call para no saturar
                try:
                    chunk_raw = chunk.model_dump() if hasattr(chunk, 'model_dump') else str(chunk)
                    #print(f"🔍 DEBUG chunk estructura: {json.dumps(chunk_raw, default=str)[:1000]}")
                except Exception as e:
                    print(f"🔍 DEBUG chunk error: {e}")
            
            # DEEPSEEK REASONING MODE: Capturar reasoning_content si existe
            # El modelo razonador envía su "pensamiento" en este campo
            if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                reasoning_content += delta.reasoning_content
                # Opcional: enviar al frontend como evento especial
                reasoning_event = json.dumps({
                    "type": "reasoning",
                    "chunk": delta.reasoning_content,
                    "done": False
                })
                yield f"event: reasoning\ndata: {reasoning_event}\n\n"
            
            # Procesar contenido de texto
            if delta.content:
                full_content += delta.content
                event_data = json.dumps({
                    "type": "content",
                    "chunk": delta.content,
                    "done": False
                })
                yield f"event: message\ndata: {event_data}\n\n"
            
            # Procesar tool calls (si vienen en streaming)
            # IMPORTANTE: En streaming, los tool_calls vienen como DELTAS incrementales
            # Cada delta tiene un 'index' que indica qué tool_call se está continuando
            # Debemos FUSIONAR los deltas, no acumularlos como elementos separados
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    tc_dict = tc.model_dump(mode='python', exclude_unset=False) if hasattr(tc, 'model_dump') else dict(tc)
                    tc_index = tc_dict.get('index', 0)
                    
                    # DEBUG: Log detallado de cada delta
                    tc_id = tc_dict.get('id')
                    func = tc_dict.get('function', {})
                    func_name = func.get('name') if func else None
                    func_args = func.get('arguments', '') if func else ''
                    #print(f"🔧 TC Delta: index={tc_index}, id={tc_id}, name={func_name}, args_chunk='{func_args[:50] if func_args else ''}...'")
                    
                    # Buscar si ya existe un tool_call con este index
                    existing_tc = None
                    for existing in tool_calls_accumulator:
                        if existing.get('index') == tc_index:
                            existing_tc = existing
                            break
                    
                    if existing_tc is None:
                        # Nuevo tool_call - añadir al acumulador
                        # Asegurar que tiene estructura completa
                        if 'function' not in tc_dict:
                            tc_dict['function'] = {'name': None, 'arguments': ''}
                        if tc_dict['function'] is None:
                            tc_dict['function'] = {'name': None, 'arguments': ''}
                        
                        # GEMINI thought_signature: Capturar de múltiples formas posibles
                        if hasattr(tc, 'thought_signature') and tc.thought_signature:
                            tc_dict['thought_signature'] = tc.thought_signature
                        if hasattr(tc, 'thoughtSignature') and tc.thoughtSignature:
                            tc_dict['thought_signature'] = tc.thoughtSignature
                        if hasattr(tc, '__dict__'):
                            for key in ['thought_signature', 'thoughtSignature']:
                                if key in tc.__dict__ and tc.__dict__[key]:
                                    tc_dict[key] = tc.__dict__[key]
                        
                        tool_calls_accumulator.append(tc_dict)
                        #print(f"   ➕ Nuevo TC[{tc_index}]: id={tc_id}, name={func_name}")
                    else:
                        # Delta de un tool_call existente - FUSIONAR
                        # Actualizar id si viene (solo el primer chunk lo tiene)
                        if tc_id:
                            existing_tc['id'] = tc_id
                        
                        # Actualizar function.name si viene
                        if func_name:
                            if 'function' not in existing_tc or existing_tc['function'] is None:
                                existing_tc['function'] = {'name': None, 'arguments': ''}
                            existing_tc['function']['name'] = func_name
                        
                        # CONCATENAR arguments (esto es un delta incremental)
                        if func_args:
                            if 'function' not in existing_tc or existing_tc['function'] is None:
                                existing_tc['function'] = {'name': None, 'arguments': ''}
                            current_args = existing_tc['function'].get('arguments') or ''
                            existing_tc['function']['arguments'] = current_args + func_args
                        
                        #print(f"   🔄 Merge TC[{tc_index}]: args ahora tiene {len(existing_tc['function'].get('arguments', ''))} chars")
                    
                    # Enviar evento al frontend (para UI en tiempo real)
                    tc_data = json.dumps({
                        "type": "tool_call",
                        "tool_call": tc_dict,
                        "done": False
                    })
                    yield f"event: tool_call\ndata: {tc_data}\n\n"
            
            # Capturar finish_reason
            if chunk_finish:
                finish_reason = chunk_finish
        
        # =======================================================================
        # GUARDAR MENSAJE COMPLETO AL FINALIZAR
        # =======================================================================
        
        # Incluir reasoning_content como metadata si existe (DeepSeek reasoning mode)
        # Lo guardamos en el JSON de tool_calls para no modificar la BD
        tool_calls_data = tool_calls_accumulator.copy() if tool_calls_accumulator else []
        if reasoning_content:
            # Guardar reasoning_content como primer elemento especial del array
            tool_calls_data.insert(0, {
                "_metadata": {
                    "reasoning_content": reasoning_content
                }
            })
            print(f"🧠 DeepSeek reasoning capturado: {len(reasoning_content)} chars")
        
        tool_calls_json = json.dumps(tool_calls_data) if tool_calls_data else None
        
        # Log para debug
        print(f"📊 Stream finalizado: finish_reason={finish_reason}, tool_calls={len(tool_calls_accumulator)}, content_len={len(full_content)}")
        
        assistant_msg_id = db.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=full_content if full_content else None,
            parent_id=user_msg_id,
            tool_calls=tool_calls_json,
            model_used=model_id
        )
        
        # Actualizar active_leaf y timestamp
        db.update_conversation_leaf(conversation_id, assistant_msg_id)
        db.update_conversation_timestamp(conversation_id)
        
        # =======================================================================
        # EJECUTAR TOOL CALLS AUTOMÁTICAMENTE Y CONTINUAR LOOP
        # =======================================================================
        
        # Detectar tool calls: verificar tanto finish_reason como la existencia de tool_calls
        # Algunos proveedores (Google/Gemini) pueden usar finish_reason diferente
        has_tool_calls = len(tool_calls_accumulator) > 0
        should_execute_tools = (finish_reason in ("tool_calls", "function_call", "stop") and has_tool_calls) or \
                               (has_tool_calls and not full_content)  # Si hay tools y no hay contenido
        
        print(f"🔍 Decisión de tools: should_execute={should_execute_tools}, finish_reason={finish_reason}, has_tools={has_tool_calls}")
        print(f"🔍 tool_calls_accumulator tiene {len(tool_calls_accumulator)} elementos")
        
        if should_execute_tools:
            print(f"🔧 Ejecutando {len(tool_calls_accumulator)} tool calls automáticamente...")
            #print(f"🔧 Raw tool_calls_accumulator: {json.dumps(tool_calls_accumulator, indent=2)[:500]}")
            
            # Reconstruir tool_calls en formato completo
            # Algunos proveedores envían deltas (chunks), otros envían completo
            reconstructed_tool_calls = []
            current_tc = None
            
            for tc_delta in tool_calls_accumulator:
                # Verificar si ya es un tool_call completo (tiene id y function.name)
                tc_id = tc_delta.get('id')
                func_info = tc_delta.get('function', {})
                func_name = func_info.get('name', '') or ''
                func_args = func_info.get('arguments', '') or ''
                
                # Limpiar saltos de línea en nombres de función (bug de Gemini 2.5)
                func_name = func_name.replace('\n', '').replace('\r', '').strip()
                
                # Si tiene ID, es un nuevo tool_call o uno completo
                if tc_id:
                    # Guardar el anterior si existe
                    if current_tc:
                        reconstructed_tool_calls.append(current_tc)
                    
                    # Iniciar nuevo
                    current_tc = {
                        'id': tc_id,
                        'type': tc_delta.get('type', 'function'),
                        'function': {
                            'name': func_name,
                            'arguments': func_args
                        }
                    }
                elif current_tc:
                    # Es un chunk adicional, concatenar nombre y/o argumentos
                    if func_name:
                        current_tc['function']['name'] += func_name
                    if func_args:
                        current_tc['function']['arguments'] += func_args
            
            # No olvidar el último
            if current_tc:
                reconstructed_tool_calls.append(current_tc)
            
            # ================================================================
            # VALIDACIÓN Y LIMPIEZA DE TOOL CALLS (Fix para Gemini 2.5 Pro)
            # ================================================================
            valid_tool_calls = []
            valid_tools = ['execute_command', 'manage_mission', 'check_job_status', 'stop_job', 'get_original_output']
            
            for tc in reconstructed_tool_calls:
                func_name = tc.get('function', {}).get('name', '').strip()
                func_args_str = tc.get('function', {}).get('arguments', '{}')
                
                # Limpiar nombre de función de caracteres extraños
                func_name = func_name.replace('\n', '').replace('\r', '').strip()
                tc['function']['name'] = func_name
                
                # Validar que el nombre de función sea válido
                if not func_name or func_name not in valid_tools:
                    print(f"⚠️ Tool call ignorado: nombre de función inválido '{func_name}'")
                    continue
                
                # Validar argumentos JSON
                try:
                    args = json.loads(func_args_str)
                    
                    # Detectar argumentos malformados (Gemini 2.5 a veces envía results en vez de args)
                    if 'results' in args and len(args) == 1:
                        print(f"⚠️ Tool call ignorado: argumentos malformados (solo contiene 'results')")
                        continue
                    
                    # Validación específica para manage_mission
                    if func_name == 'manage_mission':
                        action = args.get('action')
                        if not action:
                            print(f"⚠️ Tool call ignorado: manage_mission sin 'action'")
                            continue
                    
                    # Validación específica para check_job_status
                    if func_name == 'check_job_status':
                        job_id = args.get('job_id')
                        if not job_id:
                            # Si solo tiene 'results', es un error de Gemini
                            if 'results' in args:
                                print(f"⚠️ Tool call ignorado: check_job_status con 'results' en vez de 'job_id'")
                                continue
                    
                    # Validación específica para execute_command
                    if func_name == 'execute_command':
                        # Si tiene 'results' pero no 'command', es un error
                        if 'results' in args and 'command' not in args and 'job_id' not in args:
                            print(f"⚠️ Tool call ignorado: execute_command con 'results' en vez de argumentos válidos")
                            continue
                    
                    valid_tool_calls.append(tc)
                    
                except json.JSONDecodeError as e:
                    print(f"⚠️ Tool call ignorado: JSON inválido en argumentos - {e}")
                    continue
            
            reconstructed_tool_calls = valid_tool_calls
            print(f"🔧 Tool calls válidos después de filtrado: {len(reconstructed_tool_calls)}")
            
            # ================================================================
            
            print(f"🔧 Reconstructed tool_calls: {len(reconstructed_tool_calls)}")
            for i, tc in enumerate(reconstructed_tool_calls):
                print(f"   [{i}] {tc.get('function', {}).get('name', 'unknown')} - args: {tc.get('function', {}).get('arguments', '')[:100]}")
            
            # Preservar campos extra (thought_signature para Google Gemini 3, u otros)
            # Mapear por ID para poder encontrar todos los campos extra originales
            extra_fields_map = {}
            for tc_delta in tool_calls_accumulator:
                tc_id = tc_delta.get('id')
                if tc_id:
                    # Guardar todos los campos que no son los estándar
                    extra_fields = {k: v for k, v in tc_delta.items() 
                                   if k not in ['id', 'type', 'function', 'index'] and v is not None}
                    if extra_fields:
                        extra_fields_map[tc_id] = extra_fields
                        print(f"   🔐 Campos extra encontrados para {tc_id}: {list(extra_fields.keys())}")
            
            # Añadir campos extra a los tool_calls reconstruidos
            for tc in reconstructed_tool_calls:
                tc_id = tc.get('id')
                if tc_id and tc_id in extra_fields_map:
                    for key, value in extra_fields_map[tc_id].items():
                        tc[key] = value
                    print(f"   ✅ Preservando campos extra para {tc_id}: {list(extra_fields_map[tc_id].keys())}")
            
            # GEMINI 3 WORKAROUND: Si no hay thought_signature y es Google, añadir el skip validator
            # El SDK de OpenAI no expone correctamente extra_content de Gemini
            # Formato: extra_content.google.thought_signature para API OpenAI compatible
            if model_id.startswith('gemini-3') or model_id.startswith('gemini-2.5'):
                for i, tc in enumerate(reconstructed_tool_calls):
                    has_signature = ('thought_signature' in tc or 
                                    'thoughtSignature' in tc or 
                                    ('extra_content' in tc and tc.get('extra_content', {}).get('google', {}).get('thought_signature')))
                    if not has_signature and i == 0:  # Solo el primer tool_call necesita firma
                        tc['extra_content'] = {
                            'google': {
                                'thought_signature': 'skip_thought_signature_validator'
                            }
                        }
                        print(f"   ⚠️ Añadiendo thought_signature workaround para Gemini 3 ({tc.get('id')})")
            
            # Si no se pudo reconstruir ningún tool_call, enviar done sin ejecutar
            if not reconstructed_tool_calls:
                print(f"⚠️ No se pudieron reconstruir tool_calls. Raw: {tool_calls_accumulator}")
                done_data = json.dumps({
                    "type": "done",
                    "conversation_id": conversation_id,
                    "user_message_id": user_msg_id,
                    "assistant_message_id": assistant_msg_id,
                    "finish_reason": finish_reason,
                    "had_tool_calls": False,
                    "error": "No se pudieron reconstruir las tool_calls",
                    "done": True
                })
                yield f"event: done\ndata: {done_data}\n\n"
                return
            
            # Ejecutar cada tool call y guardar resultados
            tool_results = []
            has_awaiting_authorization_first = False  # Track si hay comando pendiente de aprobación
            has_mission_state_change_first = False  # Track si hubo cambio de estado de misión
            
            for tc in reconstructed_tool_calls:
                tc_id = tc['id']
                func_name = tc['function']['name']
                func_args = tc['function']['arguments']
                
                print(f"  ▶ Ejecutando: {func_name}({func_args[:100]}...)")
                
                # Notificar al frontend que estamos ejecutando
                exec_event = json.dumps({
                    "type": "tool_executing",
                    "tool_call_id": tc_id,
                    "function_name": func_name,
                    "done": False
                })
                yield f"event: tool_executing\ndata: {exec_event}\n\n"
                
                # Ejecutar la tool (pasamos assistant_msg_id como leaf_id para tracking)
                try:
                    result = await execute_tool_call(tc, conversation_id, leaf_id=assistant_msg_id)
                except Exception as e:
                    print(f"💥 Excepción en execute_tool_call: {type(e).__name__}: {e}")
                    result = f"Error ejecutando herramienta: {type(e).__name__}: {str(e)}"
                
                # Detectar si el comando requiere aprobación
                if "AWAITING_AUTHORIZATION" in result:
                    has_awaiting_authorization_first = True
                    print(f"🛑 Detectado AWAITING_AUTHORIZATION - pausando después del primer bloque")
                
                # Detectar si fue una operación de manage_mission
                # PERO NO forzar continuación si la misión se completó
                if func_name == "manage_mission":
                    if "MISSION_COMPLETED" in result:
                        print(f"🏁 Misión completada - NO forzar continuación")
                        # No setear has_mission_state_change_first para que termine el loop
                    else:
                        has_mission_state_change_first = True
                        print(f"📋 Detectado manage_mission - forzar continuación después del primer bloque")
                
                # ============================================================
                # AUTO-SUMMARIZE: Resumir outputs largos automáticamente
                # ============================================================
                result_for_llm = result
                was_summarized = False
                
                # Solo resumir si:
                # 1. auto_summarize está activo
                # 2. El resultado es lo suficientemente largo
                # 3. Es un comando de ejecución (no manage_mission u otras tools internas)
                should_summarize = (
                    auto_summarize and 
                    len(result) > SUMMARIZE_THRESHOLD and
                    func_name == "execute_command"
                )
                
                if should_summarize:
                    print(f"📦 Auto-resumiendo output de {len(result)} chars...")
                    
                    # Notificar al frontend que estamos resumiendo
                    summarize_event = json.dumps({
                        "type": "tool_summarizing",
                        "tool_call_id": tc_id,
                        "original_length": len(result),
                        "done": False
                    })
                    yield f"event: tool_summarizing\ndata: {summarize_event}\n\n"
                    
                    # Usar summarizer_model si se especificó, sino el mismo modelo
                    summary_model = summarizer_model if summarizer_model else model_id
                    
                    try:
                        summary_result = await summarize_tool_output(
                            output=result,
                            client=client,
                            model_id=summary_model
                        )
                        
                        if summary_result["compressed"]:
                            result_for_llm = summary_result["summary"]
                            was_summarized = True
                            
                            print(f"✅ Comprimido: {len(result)} → {len(result_for_llm)} chars ({summary_result['compression_ratio']:.1%})")
                            
                    except Exception as e:
                        print(f"⚠️ Error al resumir, usando original: {e}")
                        result_for_llm = result
                
                # Guardar mensaje de tool (siempre el resultado original)
                tool_msg_id = db.add_message(
                    conversation_id=conversation_id,
                    role="tool",
                    content=result,  # Guardamos el ORIGINAL completo
                    parent_id=assistant_msg_id,
                    tool_call_id=tc_id
                )
                
                # Si se resumió, guardar en tool_summaries para zoom-in
                if was_summarized:
                    try:
                        db.save_tool_summary(
                            message_id=tool_msg_id,
                            tool_call_id=tc_id,
                            original=result,
                            summary=result_for_llm
                        )
                    except Exception as e:
                        print(f"⚠️ Error guardando summary: {e}")
                
                # Para el LLM usamos el resumen si existe
                tool_results.append({
                    "tool_call_id": tc_id,
                    "role": "tool",
                    "content": result_for_llm
                })
                
                # Notificar al frontend del resultado
                result_event = json.dumps({
                    "type": "tool_result",
                    "tool_call_id": tc_id,
                    "result": result[:500],  # Truncar para el evento (siempre original)
                    "result_summarized": was_summarized,
                    "summary_length": len(result_for_llm) if was_summarized else None,
                    "tool_message_id": tool_msg_id,
                    "done": False
                })
                yield f"event: tool_result\ndata: {result_event}\n\n"
            
            # Actualizar active_leaf al último mensaje de tool
            db.update_conversation_leaf(conversation_id, tool_msg_id)
            
            # =================================================================
            # VERIFICAR SI DEBEMOS PAUSAR O CONTINUAR
            # =================================================================
            
            # Si hay un comando esperando aprobación, PAUSAR antes de iniciar el loop
            if has_awaiting_authorization_first:
                print(f"⏸️ Loop pausado (primer bloque) esperando aprobación humana")
                done_data = json.dumps({
                    "type": "awaiting_approval",  # Evento especial
                    "conversation_id": conversation_id,
                    "user_message_id": user_msg_id,
                    "assistant_message_id": assistant_msg_id,
                    "finish_reason": "awaiting_approval",
                    "had_tool_calls": True,
                    "message": "El loop está pausado esperando aprobación del comando",
                    "done": True
                })
                yield f"event: done\ndata: {done_data}\n\n"
                print(f"⏸️ Loop de tools pausado [{stream_id}] - esperando aprobación")
                return
            
            # =================================================================
            # CONTINUAR LA CONVERSACIÓN CON LOS RESULTADOS (LOOP)
            # =================================================================
            
            print(f"🔄 Continuando conversación con resultados de {len(tool_results)} tools...")
            
            # Reconstruir mensajes para el siguiente llamado
            # OPTIMIZACIÓN: Limitar el contexto pero con margen suficiente para loops agénticos
            # 50 mensajes permite ~15-20 iteraciones de tool calls antes de truncar
            MAX_MESSAGES_IN_LOOP = 50
            current_messages = messages.copy()
            
            # Debug: mostrar los tool_calls que vamos a enviar
            print(f"📤 Tool calls a enviar (con campos extra):")
            for tc in reconstructed_tool_calls:
                extra_keys = [k for k in tc.keys() if k not in ['id', 'type', 'function']]
                print(f"   - {tc.get('id')}: extra_fields={extra_keys}")
            
            # Construir mensaje assistant con tool_calls
            assistant_message = {
                "role": "assistant",
                "content": full_content if full_content else None,
                "tool_calls": reconstructed_tool_calls
            }
            # DEEPSEEK REASONING MODE: Incluir reasoning_content si existe
            if reasoning_content:
                assistant_message['reasoning_content'] = reasoning_content
                print(f"🧠 reasoning_content incluido en mensaje assistant ({len(reasoning_content)} chars)")
            
            current_messages.append(assistant_message)
            for tr in tool_results:
                current_messages.append(tr)
            
            # Usar truncado inteligente que preserva pares tool_call/tool_response
            if len(current_messages) > MAX_MESSAGES_IN_LOOP:
                original_len = len(current_messages)
                current_messages = db.smart_truncate_messages(current_messages, MAX_MESSAGES_IN_LOOP)
                print(f"⚠️ Contexto del loop truncado inteligente: {original_len} -> {len(current_messages)} mensajes")
            
            # Variables para el loop
            current_parent_id = tool_msg_id
            current_assistant_msg_id = assistant_msg_id
            max_iterations = 100  # Límite alto - el agente debe ser autónomo
            iteration = 0
            last_was_mission_state_change = has_mission_state_change_first  # Heredar del primer bloque
            last_had_terminal_error = False  # Track de errores de terminal
            
            while iteration < max_iterations:
                iteration += 1
                print(f"🔁 Iteración {iteration} del loop de tools...")
                
                # ============================================================
                # CRÍTICO: Actualizar el system prompt con la misión activa
                # Esto asegura que el modelo SIEMPRE sepa qué misión existe,
                # incluso si el historial se truncó
                # ============================================================
                current_messages = update_system_with_mission_context(current_messages, conversation_id)
                
                # VALIDACIÓN PRE-ENVÍO: Asegurar secuencia válida para Gemini
                # Aplicar validación de secuencia SIEMPRE antes de enviar
                current_messages = db.ensure_valid_message_sequence(current_messages)
                
                # SANITIZACIÓN EXTRA: Forzar content="" si es null (para DeepSeek)
                for msg in current_messages:
                    if msg.get('content') is None:
                        msg['content'] = ""
                
                # Debug: mostrar secuencia de roles
                roles_seq = [m.get('role', '?') for m in current_messages[:5]]
                roles_seq_end = [m.get('role', '?') for m in current_messages[-3:]]
                print(f"📋 Secuencia de mensajes: inicio={roles_seq}... fin=...{roles_seq_end} (total={len(current_messages)})")
                
                # Llamar al LLM con los resultados
                loop_params = {
                    "model": model_id,
                    "messages": current_messages,
                    "tools": tools if tools else None,
                    "tool_choice": "auto" if tools else None,
                    "stream": True
                }
                if temperature is not None:
                    loop_params["temperature"] = temperature
                if top_p is not None:
                    loop_params["top_p"] = top_p
                if max_tokens is not None:
                    loop_params["max_tokens"] = max_tokens
                
                # Streaming de esta iteración
                loop_content = ""
                loop_tool_calls = []  # Acumulador con fusión por índice
                loop_reasoning_content = ""  # DeepSeek reasoning mode
                
                loop_stream = await client.chat.completions.create(**loop_params)
                async for chunk in loop_stream:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    
                    # DEEPSEEK REASONING MODE: Capturar reasoning_content
                    if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                        loop_reasoning_content += delta.reasoning_content
                    
                    if delta.content:
                        loop_content += delta.content
                        event_data = json.dumps({
                            "type": "content",
                            "chunk": delta.content,
                            "done": False
                        })
                        yield f"event: message\ndata: {event_data}\n\n"
                    
                    # Tool calls con fusión por índice (DeepSeek streaming)
                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            tc_data = tc.model_dump() if hasattr(tc, 'model_dump') else dict(tc)
                            tc_index = tc_data.get('index', 0)
                            tc_id = tc_data.get('id')
                            func = tc_data.get('function', {})
                            func_name = func.get('name') if func else None
                            func_args = func.get('arguments', '') if func else ''
                            
                            # Buscar si ya existe un tool_call con este index
                            existing_tc = None
                            for existing in loop_tool_calls:
                                if existing.get('index') == tc_index:
                                    existing_tc = existing
                                    break
                            
                            if existing_tc is None:
                                # Nuevo tool_call
                                if 'function' not in tc_data or tc_data['function'] is None:
                                    tc_data['function'] = {'name': None, 'arguments': ''}
                                # GEMINI 3: Capturar thought_signature
                                if hasattr(tc, 'thought_signature') and tc.thought_signature:
                                    tc_data['thought_signature'] = tc.thought_signature
                                if hasattr(tc, 'thoughtSignature') and tc.thoughtSignature:
                                    tc_data['thought_signature'] = tc.thoughtSignature
                                if hasattr(tc, '__dict__'):
                                    for key in ['thought_signature', 'thoughtSignature']:
                                        if key in tc.__dict__ and tc.__dict__[key]:
                                            tc_data[key] = tc.__dict__[key]
                                loop_tool_calls.append(tc_data)
                            else:
                                # Fusionar delta
                                if tc_id:
                                    existing_tc['id'] = tc_id
                                if func_name:
                                    if 'function' not in existing_tc or existing_tc['function'] is None:
                                        existing_tc['function'] = {'name': None, 'arguments': ''}
                                    existing_tc['function']['name'] = func_name
                                if func_args:
                                    if 'function' not in existing_tc or existing_tc['function'] is None:
                                        existing_tc['function'] = {'name': None, 'arguments': ''}
                                    current_args = existing_tc['function'].get('arguments') or ''
                                    existing_tc['function']['arguments'] = current_args + func_args
                            
                            # Notificar tool call al frontend
                            tc_event = json.dumps({
                                "type": "tool_call",
                                "tool_call": tc_data,
                                "done": False
                            })
                            yield f"event: tool_call\ndata: {tc_event}\n\n"
                
                # Guardar reasoning_content con tool_calls si existe
                loop_tool_calls_data = loop_tool_calls.copy() if loop_tool_calls else []
                if loop_reasoning_content:
                    loop_tool_calls_data.insert(0, {"_metadata": {"reasoning_content": loop_reasoning_content}})
                    print(f"🧠 Loop iteration {iteration}: reasoning capturado ({len(loop_reasoning_content)} chars)")
                
                # Guardar respuesta del asistente de esta iteración
                loop_tool_calls_json = json.dumps(loop_tool_calls_data) if loop_tool_calls_data else None
                loop_assistant_msg_id = db.add_message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=loop_content if loop_content else None,
                    parent_id=current_parent_id,
                    tool_calls=loop_tool_calls_json,
                    model_used=model_id
                )
                db.update_conversation_leaf(conversation_id, loop_assistant_msg_id)
                
                print(f"📊 Iteración {iteration}: content_len={len(loop_content)}, tool_calls={len(loop_tool_calls)}")
                
                # Si no hay más tool calls, verificar si debemos forzar continuación
                if not loop_tool_calls:
                    should_continue = False
                    continuation_msg = ""
                    
                    # Caso 1: manage_mission sin acción siguiente
                    if last_was_mission_state_change and len(loop_content.strip()) < 50:
                        should_continue = True
                        continuation_msg = "[SISTEMA] Estado actualizado. CONTINÚA INMEDIATAMENTE con la siguiente acción del plan. Ejecuta el siguiente comando necesario."
                        print(f"🔄 manage_mission detectado sin acción siguiente")
                    
                    # Caso 2: Error de terminal - forzar que el LLM intente corregir
                    elif last_had_terminal_error and len(loop_content.strip()) < 100:
                        should_continue = True
                        continuation_msg = "[SISTEMA] El comando anterior falló con error. ANALIZA el error y CORRIGE el comando o intenta una alternativa. NO te detengas, continúa con el plan."
                        print(f"🔄 Error de terminal detectado sin corrección")
                    
                    if should_continue:
                        # Añadir mensaje de usuario que fuerce continuación
                        current_messages.append({
                            "role": "user",
                            "content": continuation_msg
                        })
                        
                        # Guardar este mensaje de continuación
                        continuation_msg_id = db.add_message(
                            conversation_id=conversation_id,
                            role="user",
                            content=continuation_msg,
                            parent_id=loop_assistant_msg_id
                        )
                        current_parent_id = continuation_msg_id
                        db.update_conversation_leaf(conversation_id, continuation_msg_id)
                        
                        # Reset flags y continuar el loop
                        last_was_mission_state_change = False
                        last_had_terminal_error = False
                        print(f"🔄 Mensaje de continuación inyectado, continuando loop...")
                        continue  # Continuar con la siguiente iteración
                    
                    print(f"✅ Loop terminado: LLM no pidió más tools")
                    done_data = json.dumps({
                        "type": "done",
                        "conversation_id": conversation_id,
                        "user_message_id": user_msg_id,
                        "assistant_message_id": loop_assistant_msg_id,
                        "finish_reason": "stop",
                        "had_tool_calls": True,
                        "done": True
                    })
                    yield f"event: done\ndata: {done_data}\n\n"
                    print(f"✅ Loop de tools completado [{stream_id}], mensaje final: {loop_assistant_msg_id}")
                    return
                
                # Reconstruir tool_calls para ejecutar
                print(f"🔧 Ejecutando {len(loop_tool_calls)} tool calls adicionales...")
                loop_reconstructed = []
                current_tc = None
                # Mapa para preservar campos extra (thought_signature)
                loop_extra_fields_map = {}
                for tc_delta in loop_tool_calls:
                    tc_id = tc_delta.get('id')
                    func_info = tc_delta.get('function', {})
                    func_name = (func_info.get('name', '') or '').replace('\n', '').replace('\r', '').strip()
                    func_args = func_info.get('arguments', '') or ''
                    # Capturar campos extra
                    if tc_id:
                        extra = {k: v for k, v in tc_delta.items() 
                                if k not in ['id', 'type', 'function', 'index'] and v is not None}
                        if extra:
                            loop_extra_fields_map[tc_id] = extra
                    if tc_id:
                        if current_tc:
                            loop_reconstructed.append(current_tc)
                        current_tc = {
                            'id': tc_id,
                            'type': tc_delta.get('type', 'function'),
                            'function': {'name': func_name, 'arguments': func_args}
                        }
                    elif current_tc:
                        # Concatenar nombre y argumentos si vienen en chunks
                        if func_name:
                            current_tc['function']['name'] += func_name
                        if func_args:
                            current_tc['function']['arguments'] += func_args
                if current_tc:
                    loop_reconstructed.append(current_tc)
                
                # ================================================================
                # VALIDACIÓN DE TOOL CALLS EN LOOP (Fix para Gemini 2.5 Pro)
                # ================================================================
                valid_loop_tools = []
                valid_tool_names = ['execute_command', 'manage_mission', 'check_job_status', 'stop_job', 'get_original_output']
                
                for tc in loop_reconstructed:
                    func_name = (tc.get('function', {}).get('name', '') or '').replace('\n', '').replace('\r', '').strip()
                    func_args_str = tc.get('function', {}).get('arguments', '{}')
                    tc['function']['name'] = func_name  # Guardar nombre limpio
                    
                    if not func_name or func_name not in valid_tool_names:
                        print(f"⚠️ Loop: tool call ignorado - nombre inválido '{func_name}'")
                        continue
                    
                    try:
                        args = json.loads(func_args_str)
                        
                        # Detectar argumentos malformados
                        if 'results' in args and len(args) == 1:
                            print(f"⚠️ Loop: tool call ignorado - solo contiene 'results'")
                            continue
                        
                        if func_name == 'manage_mission' and not args.get('action'):
                            print(f"⚠️ Loop: manage_mission sin 'action'")
                            continue
                        
                        if func_name == 'check_job_status' and not args.get('job_id') and 'results' in args:
                            print(f"⚠️ Loop: check_job_status con 'results' en vez de 'job_id'")
                            continue
                        
                        if func_name == 'execute_command' and 'results' in args and 'command' not in args and 'job_id' not in args:
                            print(f"⚠️ Loop: execute_command con 'results' en vez de argumentos válidos")
                            continue
                        
                        valid_loop_tools.append(tc)
                    except json.JSONDecodeError as e:
                        print(f"⚠️ Loop: JSON inválido en argumentos - {e}")
                        continue
                
                loop_reconstructed = valid_loop_tools
                print(f"🔧 Loop: {len(loop_reconstructed)} tool calls válidos")
                
                # Si no hay tool calls válidos después del filtrado, terminar esta iteración
                if not loop_reconstructed:
                    print(f"⚠️ Loop: no hay tool calls válidos, continuando sin ejecutar")
                    continue
                # ================================================================
                
                # Añadir campos extra a los tool_calls reconstruidos (thought_signature)
                for tc in loop_reconstructed:
                    tc_id = tc.get('id')
                    if tc_id and tc_id in loop_extra_fields_map:
                        for key, value in loop_extra_fields_map[tc_id].items():
                            tc[key] = value
                
                # GEMINI 3 WORKAROUND: Añadir skip validator si es necesario
                if model_id.startswith('gemini-3') or model_id.startswith('gemini-2.5'):
                    for i, tc in enumerate(loop_reconstructed):
                        has_signature = ('thought_signature' in tc or 
                                        'thoughtSignature' in tc or 
                                        ('extra_content' in tc and tc.get('extra_content', {}).get('google', {}).get('thought_signature')))
                        if not has_signature and i == 0:
                            tc['extra_content'] = {
                                'google': {
                                    'thought_signature': 'skip_thought_signature_validator'
                                }
                            }
                
                # Ejecutar tools de esta iteración
                loop_tool_results = []
                loop_tool_msg_id = None
                has_awaiting_authorization = False  # Track si hay comando pendiente de aprobación
                has_mission_state_change = False  # Track si hubo cambio de estado de misión
                has_terminal_error = False  # Track si hubo error en comando de terminal
                
                for tc in loop_reconstructed:
                    tc_id = tc['id']
                    func_name = tc['function']['name']
                    func_args = tc['function']['arguments']
                    
                    print(f"  ▶ Ejecutando: {func_name}({func_args[:100]}...)")
                    
                    exec_event = json.dumps({
                        "type": "tool_executing",
                        "tool_call_id": tc_id,
                        "function_name": func_name,
                        "done": False
                    })
                    yield f"event: tool_executing\ndata: {exec_event}\n\n"
                    
                    try:
                        result = await execute_tool_call(tc, conversation_id, leaf_id=loop_assistant_msg_id)
                    except Exception as e:
                        print(f"💥 Excepción en execute_tool_call: {type(e).__name__}: {e}")
                        result = f"Error ejecutando herramienta: {type(e).__name__}: {str(e)}"
                    
                    # Detectar si el comando requiere aprobación
                    if "AWAITING_AUTHORIZATION" in result:
                        has_awaiting_authorization = True
                        print(f"🛑 Detectado AWAITING_AUTHORIZATION - pausando loop")
                    
                    # Detectar si fue una operación de manage_mission
                    # PERO NO forzar continuación si la misión se completó
                    if func_name == "manage_mission":
                        if "MISSION_COMPLETED" in result:
                            print(f"🏁 Misión completada en loop - NO forzar continuación")
                            # No setear has_mission_state_change para que termine
                        else:
                            has_mission_state_change = True
                            print(f"📋 Detectado manage_mission - forzar continuación")
                    
                    # Detectar errores de terminal (exit code != 0)
                    if func_name == "execute_command" and "EXIT CODE:" in result:
                        try:
                            exit_code_line = [l for l in result.split('\n') if 'EXIT CODE:' in l][0]
                            exit_code = int(exit_code_line.split(':')[1].strip())
                            if exit_code != 0:
                                has_terminal_error = True
                                print(f"⚠️ Detectado error de terminal (exit code: {exit_code})")
                        except:
                            pass
                    
                    loop_tool_msg_id = db.add_message(
                        conversation_id=conversation_id,
                        role="tool",
                        content=result,
                        parent_id=loop_assistant_msg_id,
                        tool_call_id=tc_id
                    )
                    
                    # Enviar resultado completo al LLM (la primera vez necesita verlo todo)
                    loop_tool_results.append({
                        "tool_call_id": tc_id,
                        "role": "tool",
                        "content": result
                    })
                    
                    result_event = json.dumps({
                        "type": "tool_result",
                        "tool_call_id": tc_id,
                        "result": result[:500],
                        "tool_message_id": loop_tool_msg_id,
                        "done": False
                    })
                    yield f"event: tool_result\ndata: {result_event}\n\n"
                
                # Si hay un comando esperando aprobación, PAUSAR el loop
                if has_awaiting_authorization:
                    print(f"⏸️ Loop pausado esperando aprobación humana")
                    done_data = json.dumps({
                        "type": "awaiting_approval",  # Evento especial
                        "conversation_id": conversation_id,
                        "user_message_id": user_msg_id,
                        "assistant_message_id": loop_assistant_msg_id,
                        "finish_reason": "awaiting_approval",
                        "had_tool_calls": True,
                        "message": "El loop está pausado esperando aprobación del comando",
                        "done": True
                    })
                    yield f"event: done\ndata: {done_data}\n\n"
                    print(f"⏸️ Loop de tools pausado [{stream_id}] - esperando aprobación")
                    return
                
                # Actualizar flag de estado de misión para la siguiente iteración
                last_was_mission_state_change = has_mission_state_change
                
                # Track de error de terminal para forzar continuación si LLM se detiene
                last_had_terminal_error = has_terminal_error
                
                # Actualizar mensajes para la siguiente iteración
                loop_assistant_message = {
                    "role": "assistant",
                    "content": loop_content if loop_content else None,
                    "tool_calls": loop_reconstructed
                }
                # DEEPSEEK REASONING MODE: Incluir reasoning_content si existe
                if loop_reasoning_content:
                    loop_assistant_message['reasoning_content'] = loop_reasoning_content
                    print(f"🧠 Loop iter {iteration}: reasoning_content incluido ({len(loop_reasoning_content)} chars)")
                
                current_messages.append(loop_assistant_message)
                for tr in loop_tool_results:
                    current_messages.append(tr)
                
                # Usar truncado inteligente para evitar romper pares tool_call/tool_response
                if len(current_messages) > MAX_MESSAGES_IN_LOOP:
                    original_len = len(current_messages)
                    current_messages = db.smart_truncate_messages(current_messages, MAX_MESSAGES_IN_LOOP)
                    print(f"⚠️ Contexto truncado inteligente (iter {iteration}): {original_len} -> {len(current_messages)} msgs")
                
                current_parent_id = loop_tool_msg_id
                db.update_conversation_leaf(conversation_id, loop_tool_msg_id)
            
            # Si llegamos aquí, excedimos el límite de iteraciones
            print(f"⚠️ Límite de iteraciones alcanzado ({max_iterations})")
            done_data = json.dumps({
                "type": "done",
                "conversation_id": conversation_id,
                "user_message_id": user_msg_id,
                "assistant_message_id": current_assistant_msg_id,
                "finish_reason": "max_iterations",
                "had_tool_calls": True,
                "done": True
            })
            yield f"event: done\ndata: {done_data}\n\n"
            return
        
        # Enviar evento final (sin tool calls)
        done_data = json.dumps({
            "type": "done",
            "conversation_id": conversation_id,
            "user_message_id": user_msg_id,
            "assistant_message_id": assistant_msg_id,
            "finish_reason": finish_reason,
            "done": True
        })
        yield f"event: done\ndata: {done_data}\n\n"
        
        print(f"✅ Stream completado [{stream_id}], mensaje guardado: {assistant_msg_id}")
        
    except asyncio.CancelledError:
        print(f"⚠️ STREAM CANCELADO [{stream_id}] - Cliente cerró la conexión")
        raise  # Re-lanzar para que FastAPI lo maneje correctamente
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error en streaming [{stream_id}]: {error_msg}")
        
        # Determinar código de error más específico
        if "401" in error_msg:
            code = "INVALID_API_KEY"
            friendly_msg = "API Key inválida o expirada"
        elif "429" in error_msg:
            code = "RATE_LIMITED"
            friendly_msg = "Has alcanzado el límite de peticiones. Espera unos segundos."
        elif "400" in error_msg:
            code = "INVALID_REQUEST"
            # LOG DETALLADO PARA DEBUG DE MENSAJES
            print("=" * 80)
            print("🔴 ERROR 400 - DUMP DE MENSAJES ENVIADOS:")
            print("=" * 80)
            for i, msg in enumerate(messages):
                role = msg.get('role', '?')
                content = msg.get('content')
                tool_calls = msg.get('tool_calls')
                tc_id = msg.get('tool_call_id', '')
                reasoning = msg.get('reasoning_content')
                
                content_preview = "None" if content is None else f"'{content[:80]}...'" if len(str(content)) > 80 else f"'{content}'"
                print(f"  [{i}] role={role}, content={content_preview}")
                
                # Mostrar reasoning_content (DeepSeek)
                if reasoning:
                    print(f"      🧠 reasoning_content={len(reasoning)} chars")
                elif role == 'assistant' and tool_calls:
                    print(f"      ⚠️ ASSISTANT CON TOOL_CALLS PERO SIN reasoning_content!")
                
                # Mostrar tool_calls en detalle
                if tool_calls:
                    print(f"      🔧 tool_calls ({len(tool_calls)} calls):")
                    for j, tc in enumerate(tool_calls):
                        tc_id_inner = tc.get('id', 'NO_ID')
                        func = tc.get('function', {})
                        func_name = func.get('name', 'NO_NAME')
                        func_args = func.get('arguments', 'NO_ARGS')
                        
                        # Detectar nulls
                        if tc_id_inner is None:
                            print(f"         ⚠️ [{j}] ID ES NULL!")
                        if func_name is None:
                            print(f"         ⚠️ [{j}] FUNCTION NAME ES NULL!")
                        if func_args is None:
                            print(f"         ⚠️ [{j}] FUNCTION ARGUMENTS ES NULL!")
                        
                        args_preview = str(func_args)[:60] if func_args else "null"
                        print(f"         [{j}] id={tc_id_inner}, name={func_name}, args={args_preview}...")
                
                if tc_id:
                    print(f"      tool_call_id={tc_id}")
                
                # Detectar content null
                if content is None:
                    print(f"      ⚠️ ¡CONTENT ES NULL!")
            print("=" * 80)
            
            # Detectar errores específicos de formato
            if "Name cannot be empty" in error_msg or "function_response" in error_msg:
                friendly_msg = "Error de formato en respuesta de herramienta. Intenta de nuevo o inicia nueva conversación."
            elif "INVALID_ARGUMENT" in error_msg:
                friendly_msg = "Argumento inválido en la petición al modelo."
            elif "null" in error_msg.lower() and "string" in error_msg.lower():
                friendly_msg = "Error: Un mensaje tiene contenido null. Inicia nueva conversación."
            else:
                friendly_msg = f"Petición malformada: {error_msg[:100]}"
        elif "500" in error_msg or "503" in error_msg:
            code = "PROVIDER_ERROR"
            friendly_msg = "Error del proveedor (Google/OpenAI). Intenta de nuevo en unos segundos."
        else:
            code = "STREAM_ERROR"
            friendly_msg = error_msg[:150]
        
        error_data = json.dumps({
            "type": "error",
            "code": code,
            "message": friendly_msg,
            "technical_details": error_msg[:300],
            "done": True
        })
        yield f"event: error\ndata: {error_data}\n\n"


# =============================================================================
# ENDPOINT PARA ENVIAR RESPUESTA DE TOOL
# =============================================================================

@router.post("/chat/tool-response")
async def tool_response(
    conversation_id: str,
    parent_message_id: int,  # ID del mensaje assistant que pidió la tool
    tool_call_id: str,
    tool_name: str,
    tool_result: str
):
    """
    Guarda la respuesta de una tool y devuelve el ID del mensaje.
    Después de esto, el frontend debería llamar a /chat para continuar.
    """
    # Verificar conversación
    conv = db.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(
            status_code=404,
            detail={"code": "CONVERSATION_NOT_FOUND", "message": "Conversación no encontrada"}
        )
    
    # Guardar mensaje de tool
    tool_msg_id = db.add_message(
        conversation_id=conversation_id,
        role="tool",
        content=tool_result,
        parent_id=parent_message_id,
        tool_call_id=tool_call_id
    )
    
    # Actualizar active_leaf
    db.update_conversation_leaf(conversation_id, tool_msg_id)
    
    return {
        "success": True,
        "tool_message_id": tool_msg_id,
        "conversation_id": conversation_id
    }


# =============================================================================
# TOOL SUMMARIZER - OPTIMIZACIÓN DE CONTEXTO (Sprint 2)
# =============================================================================

# Configuración del summarizer
SUMMARIZE_THRESHOLD = 800  # Caracteres mínimos para activar resumido
SUMMARIZE_MAX_LINES = 20   # Máximo de líneas en el resumen

SUMMARY_PROMPT_TEMPLATE = """Resume este output técnico de herramienta de ciberseguridad.

**REGLAS CRÍTICAS** (el Agente depende de esta información):
1. PRESERVAR OBLIGATORIAMENTE:
   - Direcciones IP, puertos, hosts
   - Versiones de servicios (ej: "Apache 2.4.49", "OpenSSH 7.9")
   - CVEs, vulnerabilidades nombradas
   - Credenciales, tokens, cookies, hashes
   - Rutas de archivos, URLs descubiertas
   - Nombres de usuario, dominios
   - Cualquier dato que parezca una credencial o secreto

2. ELIMINAR:
   - Líneas de progreso repetitivas ("Scanning...", "Progress: 50%")
   - Banners y ASCII art
   - Timestamps redundantes
   - Advertencias genéricas de herramientas
   - Explicaciones de uso de la herramienta

3. FORMATO:
   - Máximo {max_lines} líneas
   - Bullets para listar hallazgos
   - Una línea de resumen al inicio
   - Si hay muchos puertos/hosts, agrupar por relevancia

OUTPUT A RESUMIR:
```
{output}
```

RESUMEN (conciso, técnico, preservando datos críticos):"""


from pydantic import BaseModel

class SummarizeRequest(BaseModel):
    """Request para el endpoint de summarize."""
    output: str
    provider: str
    api_key: str
    model_id: str
    max_lines: int = SUMMARIZE_MAX_LINES


class SummarizeResponse(BaseModel):
    """Response del endpoint de summarize."""
    summary: str
    compressed: bool
    original_length: int
    summary_length: int
    compression_ratio: float


async def summarize_tool_output(
    output: str,
    client: AsyncOpenAI,
    model_id: str,
    max_lines: int = SUMMARIZE_MAX_LINES
) -> dict:
    """
    Resume un output largo de herramienta de forma inteligente.
    
    Args:
        output: Output original de la herramienta
        client: Cliente AsyncOpenAI configurado
        model_id: ID del modelo a usar para resumir
        max_lines: Máximo de líneas en el resumen
    
    Returns:
        dict con summary, compressed, compression_ratio, etc.
    """
    # Si es corto, no resumir
    if len(output) < SUMMARIZE_THRESHOLD:
        return {
            "summary": output,
            "compressed": False,
            "original_length": len(output),
            "summary_length": len(output),
            "compression_ratio": 1.0
        }
    
    # Generar prompt de resumen
    prompt = SUMMARY_PROMPT_TEMPLATE.format(
        output=output,
        max_lines=max_lines
    )
    
    try:
        response = await client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": prompt}],
            stream=False,
            temperature=0.2,  # Baja temperatura para respuestas deterministas
            max_tokens=800    # Suficiente para un resumen extenso
        )
        
        summary = response.choices[0].message.content.strip()
        compression_ratio = len(summary) / len(output) if len(output) > 0 else 1.0
        
        return {
            "summary": summary,
            "compressed": True,
            "original_length": len(output),
            "summary_length": len(summary),
            "compression_ratio": compression_ratio
        }
        
    except Exception as e:
        print(f"⚠️ Error al resumir output: {e}")
        # En caso de error, devolver el original truncado
        truncated = output[:2000] + "\n\n[... output truncado por error de resumen ...]"
        return {
            "summary": truncated,
            "compressed": False,
            "original_length": len(output),
            "summary_length": len(truncated),
            "compression_ratio": len(truncated) / len(output),
            "error": str(e)
        }


@router.post("/summarize-tool-output", response_model=SummarizeResponse)
async def summarize_tool_output_endpoint(req: SummarizeRequest):
    """
    Endpoint para resumir outputs largos de herramientas.
    
    Útil para:
    - Outputs de nmap extensos
    - Resultados de fuzzing (ffuf, gobuster)
    - Escaneos de vulnerabilidades (nuclei, nikto)
    
    El resumen preserva información crítica (IPs, puertos, CVEs)
    mientras elimina ruido y líneas repetitivas.
    """
    # Crear cliente para el proveedor
    client = get_client_for_provider(req.provider, req.api_key)
    
    result = await summarize_tool_output(
        output=req.output,
        client=client,
        model_id=req.model_id,
        max_lines=req.max_lines
    )
    
    return SummarizeResponse(**result)


def get_client_for_provider(provider: str, api_key: str) -> AsyncOpenAI:
    """
    Crea un cliente AsyncOpenAI configurado para el proveedor.
    Reutiliza la lógica del chat pero como función standalone.
    """
    PROVIDER_CONFIG = {
        "openai": {"base_url": None},
        "google": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai/"},
        "deepseek": {"base_url": "https://api.deepseek.com/v1"},
        "openrouter": {"base_url": "https://openrouter.ai/api/v1"},
        "anthropic": {"base_url": "https://api.anthropic.com/v1"},
    }
    
    config = PROVIDER_CONFIG.get(provider, {})
    base_url = config.get("base_url")
    
    # Caso especial: Ollama (extraer URL del api_key o usar default)
    if provider == "ollama":
        # El api_key para Ollama puede contener la URL: "http://localhost:11434|dummy"
        if "|" in api_key:
            base_url, api_key = api_key.split("|", 1)
            base_url = f"{base_url.rstrip('/')}/v1"
        else:
            base_url = "http://localhost:11434/v1"
            api_key = "ollama"  # Ollama no requiere key real
    
    return AsyncOpenAI(
        api_key=api_key,
        base_url=base_url
    )
