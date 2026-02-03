"""
routes/missions.py - Endpoints REST para gestión de misiones agénticas.

Sprint 1 del modo agéntico.
"""

from fastapi import APIRouter, HTTPException
from typing import Optional, List
from pydantic import BaseModel
import httpx
import json

import database as db

router = APIRouter(prefix="/missions", tags=["Missions"])

# URL del sandbox
SANDBOX_URL = "http://localhost:5000"


# =============================================================================
# MODELOS PYDANTIC
# =============================================================================

class MissionCreate(BaseModel):
    conversation_id: str
    goal: str
    objectives: List[str] = []
    metadata: Optional[dict] = None


class ObjectiveUpdate(BaseModel):
    status: str
    result: Optional[str] = None
    reflection: Optional[str] = None


class MissionPhaseUpdate(BaseModel):
    phase: str


class MissionComplete(BaseModel):
    status: str = "COMPLETED"


class ObjectiveModification(BaseModel):
    type: str  # insert, delete, update
    after_id: Optional[int] = None
    objective_id: Optional[int] = None
    task: Optional[str] = None
    new_task: Optional[str] = None


class ModifyObjectives(BaseModel):
    modifications: List[ObjectiveModification]


# =============================================================================
# ENDPOINTS DE MISIONES
# =============================================================================

@router.get("/{mission_id}")
async def get_mission_status(mission_id: str):
    """
    Obtiene el estado completo de una misión.
    Incluye objetivos y progreso.
    """
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


@router.post("")
async def create_mission(req: MissionCreate):
    """
    Crea una nueva misión con objetivos.
    """
    mission_id = db.create_mission(
        conversation_id=req.conversation_id,
        goal=req.goal,
        metadata=req.metadata
    )
    
    obj_ids = []
    if req.objectives:
        obj_ids = db.add_objectives(mission_id, req.objectives)
    
    # Cambiar estado a IN_PROGRESS
    db.update_mission_status(mission_id, "IN_PROGRESS")
    
    return {
        "mission_id": mission_id,
        "objective_ids": obj_ids,
        "status": "Mission created successfully"
    }


@router.patch("/{mission_id}/phase")
async def update_mission_phase(mission_id: str, req: MissionPhaseUpdate):
    """
    Actualiza la fase actual de una misión.
    """
    mission = db.get_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    
    db.update_mission_phase(mission_id, req.phase)
    
    return {"status": "Phase updated", "new_phase": req.phase}


@router.post("/{mission_id}/complete")
async def complete_mission(mission_id: str, req: MissionComplete):
    """
    Marca una misión como completada/fallida/cancelada.
    """
    mission = db.get_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    
    valid_statuses = ["COMPLETED", "FAILED", "CANCELLED"]
    if req.status not in valid_statuses:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid status. Valid: {valid_statuses}"
        )
    
    db.complete_mission(mission_id, req.status)
    progress = db.get_mission_progress(mission_id)
    
    return {
        "status": "Mission completed",
        "final_status": req.status,
        "progress": progress
    }


@router.delete("/{mission_id}")
async def cancel_mission(mission_id: str):
    """
    Cancela una misión en progreso.
    """
    mission = db.get_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    
    db.complete_mission(mission_id, "CANCELLED")
    
    return {"status": "Mission cancelled"}


@router.get("/{mission_id}/jobs")
async def get_mission_jobs(mission_id: str):
    """
    Obtiene todos los jobs asociados a una misión.
    """
    mission = db.get_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    
    jobs = db.get_mission_jobs(mission_id)
    
    return {
        "mission_id": mission_id,
        "jobs": jobs
    }


# =============================================================================
# ENDPOINTS DE OBJETIVOS
# =============================================================================

@router.get("/{mission_id}/objectives")
async def get_objectives(mission_id: str):
    """
    Obtiene todos los objetivos de una misión.
    """
    mission = db.get_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    
    objectives = db.get_objectives(mission_id)
    
    return {
        "mission_id": mission_id,
        "objectives": objectives
    }


@router.patch("/objectives/{objective_id}")
async def update_objective(objective_id: int, req: ObjectiveUpdate):
    """
    Actualiza el estado de un objetivo.
    """
    valid_statuses = ['PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'SKIPPED', 'AWAITING_AUTHORIZATION']
    if req.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Valid: {valid_statuses}"
        )
    
    success = db.update_objective_status(
        objective_id=objective_id,
        status=req.status,
        result=req.result,
        reflection=req.reflection
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Objective not found")
    
    objective = db.get_objective_by_id(objective_id)
    progress = db.get_mission_progress(objective['mission_id']) if objective else None
    
    return {
        "status": "Objective updated",
        "objective": objective,
        "progress": progress
    }


@router.post("/{mission_id}/objectives")
async def add_objectives(mission_id: str, objectives: List[str]):
    """
    Añade nuevos objetivos a una misión.
    """
    mission = db.get_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    
    obj_ids = db.add_objectives(mission_id, objectives)
    
    return {
        "status": "Objectives added",
        "new_objective_ids": obj_ids
    }


@router.post("/{mission_id}/modify-objectives")
async def modify_objectives(mission_id: str, req: ModifyObjectives):
    """
    Reorganiza los objetivos de una misión (insertar/eliminar/actualizar).
    """
    mission = db.get_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    
    results = []
    
    for mod in req.modifications:
        if mod.type == "insert" and mod.after_id and mod.task:
            try:
                new_id = db.insert_objective_after(mission_id, mod.after_id, mod.task)
                results.append({"type": "insert", "new_id": new_id, "task": mod.task})
            except ValueError as e:
                results.append({"type": "insert", "error": str(e)})
        
        elif mod.type == "delete" and mod.objective_id:
            db.delete_objective(mod.objective_id)
            results.append({"type": "delete", "objective_id": mod.objective_id})
        
        elif mod.type == "update" and mod.objective_id and mod.new_task:
            db.update_objective_task(mod.objective_id, mod.new_task)
            results.append({"type": "update", "objective_id": mod.objective_id})
    
    objectives = db.get_objectives(mission_id)
    
    return {
        "status": "Plan modified",
        "modifications": results,
        "updated_objectives": objectives
    }


# =============================================================================
# ENDPOINTS DE CONVERSACIÓN
# =============================================================================

@router.get("/conversation/{conversation_id}/active")
async def get_active_mission_for_conversation(conversation_id: str):
    """
    Obtiene la misión activa de una conversación.
    """
    mission = db.get_active_mission(conversation_id)
    
    if not mission:
        return {"active": False, "mission": None}
    
    objectives = db.get_objectives(mission['id'])
    progress = db.get_mission_progress(mission['id'])
    
    return {
        "active": True,
        "mission": mission,
        "objectives": objectives,
        "progress": progress
    }


# =============================================================================
# SPRINT 3: ENDPOINTS DE APROBACIÓN Y SEGURIDAD
# =============================================================================

class ApprovalRequest(BaseModel):
    """Request para aprobar/rechazar un comando."""
    approved: bool
    approved_by: str = "user"


class CommandAnalysisResponse(BaseModel):
    """Response del análisis de un comando."""
    risk_level: str
    requires_approval: bool
    matched_patterns: List[dict]
    reason: str


@router.get("/objectives/pending-approval")
async def get_pending_approvals(conversation_id: Optional[str] = None):
    """
    Obtiene todos los objetivos pendientes de aprobación.
    
    Útil para mostrar una lista de comandos que necesitan autorización.
    """
    pending = db.get_pending_approval_objectives(conversation_id)
    
    return {
        "count": len(pending),
        "pending_objectives": pending
    }


@router.post("/objectives/{objective_id}/approve")
async def approve_objective(objective_id: int, req: ApprovalRequest):
    """
    Aprueba o rechaza un comando pendiente de autorización.
    
    Si se aprueba:
    - El objetivo pasa a IN_PROGRESS
    - El comando SE EJECUTA INMEDIATAMENTE
    - Se devuelve el resultado para que el frontend pueda reanudar
    
    Si se rechaza:
    - El objetivo pasa a SKIPPED
    - El agente debe buscar alternativa o continuar
    """
    result = db.approve_objective_command(
        objective_id=objective_id,
        approved=req.approved,
        approved_by=req.approved_by
    )
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    # Actualizar el registro de auditoría correspondiente
    audit_log = db.get_audit_by_objective(objective_id)
    if audit_log:
        status = "APPROVED" if req.approved else "REJECTED"
        db.update_audit_log(
            audit_id=audit_log["id"],
            status=status,
            approved_by=req.approved_by
        )
    
    execution_result = None
    
    # SI SE APROBÓ, EJECUTAR EL COMANDO INMEDIATAMENTE
    if req.approved and result.get("command"):
        command = result["command"]
        conversation_id = result.get("conversation_id")
        
        print(f"🚀 Ejecutando comando aprobado: {command[:100]}...")
        
        try:
            # Actualizar auditoría a EXECUTING
            if audit_log:
                db.update_audit_log(audit_log["id"], "EXECUTING")
            
            # Ejecutar en el sandbox con tiempo de espera generoso para comandos aprobados
            # Los comandos críticos pueden tardar más (scripts complejos, conexiones de red, etc.)
            async with httpx.AsyncClient(timeout=180.0) as client:
                payload = {
                    "command": command,
                    "conversation_id": conversation_id,
                    "wait_time": 60  # Mayor tiempo para comandos aprobados (pueden ser complejos)
                }
                
                response = await client.post(f"{SANDBOX_URL}/execute", json=payload)
                response.raise_for_status()
                exec_result = response.json()
                
                print(f"📥 Sandbox response keys: {list(exec_result.keys())}")
                
                # Formatear salida - el sandbox devuelve stdout/stderr y return_code
                output_parts = []
                
                if exec_result.get("status") == "running" and exec_result.get("job_id"):
                    output_parts.append(f"JOB_ID: {exec_result['job_id']}")
                    output_parts.append(f"STATUS: running (background)")
                    output_parts.append("NOTE: Full output available when command completes.")
                
                # El sandbox devuelve stdout/stderr, no output
                if exec_result.get("stdout"):
                    output_parts.append(exec_result["stdout"])
                if exec_result.get("stderr"):
                    output_parts.append(f"STDERR: {exec_result['stderr']}")
                # Fallback para 'output' si existe
                if exec_result.get("output"):
                    output_parts.append(exec_result["output"])
                
                # El sandbox devuelve return_code, no exit_code
                exit_code = exec_result.get("return_code") or exec_result.get("exit_code")
                if exit_code is not None:
                    output_parts.append(f"EXIT_CODE: {exit_code}")
                
                execution_result = {
                    "success": True,
                    "output": "\n".join(output_parts) if output_parts else "Command executed (no output yet)",
                    "exit_code": exit_code,
                    "job_id": exec_result.get("job_id"),
                    "status": exec_result.get("status", "completed")
                }
                
                # Actualizar auditoría a EXECUTED
                if audit_log:
                    db.update_audit_log(audit_log["id"], "EXECUTED")
                
                print(f"✅ Comando ejecutado: exit_code={exit_code}, output_len={len(execution_result['output']) if execution_result['output'] else 0}")
                
                # =================================================================
                # IMPORTANTE: Actualizar el mensaje tool que tenía AWAITING_AUTHORIZATION
                # Esto permite que cuando se reanude el chat, el LLM reciba el resultado real
                # =================================================================
                if conversation_id:
                    tool_result_content = json.dumps({
                        "status": "EXECUTED",
                        "command": command,
                        "exit_code": exec_result.get("exit_code"),
                        "output": execution_result["output"],
                        "message": "Comando aprobado y ejecutado exitosamente"
                    })
                    
                    print(f"📝 Actualizando mensaje tool para objetivo {objective_id} en conv {conversation_id}")
                    updated = db.find_and_update_awaiting_tool_message(
                        conversation_id=conversation_id,
                        objective_id=objective_id,
                        new_content=tool_result_content
                    )
                    if not updated:
                        print(f"⚠️ No se pudo actualizar el mensaje tool - el LLM no recibirá el resultado")
                else:
                    print(f"⚠️ No hay conversation_id - no se puede actualizar mensaje tool")
                
        except httpx.HTTPStatusError as e:
            execution_result = {
                "success": False,
                "error": f"Sandbox error: {e.response.status_code}",
                "output": str(e)
            }
            if audit_log:
                db.update_audit_log(audit_log["id"], "FAILED")
            print(f"❌ Error HTTP ejecutando comando: {e}")
            
        except Exception as e:
            execution_result = {
                "success": False,
                "error": str(e),
                "output": f"Error: {str(e)}"
            }
            if audit_log:
                db.update_audit_log(audit_log["id"], "FAILED")
            print(f"❌ Error ejecutando comando: {e}")
    
    return {
        "success": True,
        "objective_id": objective_id,
        "approved": req.approved,
        "command": result.get("command"),
        "mission_id": result.get("mission_id"),
        "conversation_id": result.get("conversation_id"),
        "message": f"Comando {'aprobado y ejecutado' if req.approved else 'rechazado'}",
        "execution": execution_result  # Resultado de la ejecución (si se aprobó)
    }


@router.post("/analyze-command")
async def analyze_command_endpoint(command: str):
    """
    Analiza un comando para determinar su nivel de riesgo.
    
    No ejecuta el comando, solo lo analiza.
    Útil para preview antes de ejecución.
    """
    from security import analyze_command, get_approval_message
    
    analysis = analyze_command(command)
    
    response = {
        "command": command,
        **analysis
    }
    
    if analysis["requires_approval"]:
        response["approval_message"] = get_approval_message(command, analysis)
    
    return response


# =============================================================================
# ENDPOINTS DE AUDITORÍA
# =============================================================================

@router.get("/audit/logs")
async def get_audit_logs(
    conversation_id: Optional[str] = None,
    mission_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100
):
    """
    Obtiene los registros de auditoría de comandos.
    
    Filtros opcionales:
    - conversation_id: Filtrar por conversación
    - mission_id: Filtrar por misión
    - status: Filtrar por estado (PENDING, EXECUTED, APPROVED, REJECTED, FAILED)
    """
    logs = db.get_audit_logs(
        conversation_id=conversation_id,
        mission_id=mission_id,
        status=status,
        limit=limit
    )
    
    return {
        "count": len(logs),
        "logs": logs
    }


@router.get("/audit/statistics")
async def get_audit_statistics(conversation_id: Optional[str] = None):
    """
    Obtiene estadísticas de auditoría de comandos.
    
    Incluye:
    - Total de comandos ejecutados
    - Desglose por estado
    - Desglose por nivel de riesgo
    - Tasa de aprobación
    """
    stats = db.get_audit_statistics(conversation_id)
    
    return stats


@router.get("/audit/report")
async def get_audit_report(
    conversation_id: Optional[str] = None,
    mission_id: Optional[str] = None
):
    """
    Genera un reporte de auditoría en formato Markdown.
    
    Útil para documentación y revisión post-operación.
    """
    from security import format_audit_report
    
    logs = db.get_audit_logs(
        conversation_id=conversation_id,
        mission_id=mission_id,
        limit=500
    )
    
    report = format_audit_report(logs)
    
    return {
        "format": "markdown",
        "report": report
    }


# =============================================================================
# ENDPOINT DE REANUDACIÓN AUTÓNOMA
# =============================================================================

class ResumeRequest(BaseModel):
    """Request para reanudar el loop autónomo después de aprobar/rechazar."""
    objective_id: int
    command_result: Optional[str] = None
    was_approved: bool
    provider: str
    model_id: str
    api_key: str


@router.post("/resume-autonomous")
async def resume_autonomous_loop(req: ResumeRequest):
    """
    Reanuda el loop de autonomía después de una aprobación/rechazo.
    
    Este endpoint:
    1. Recupera el contexto de la conversación
    2. Añade el resultado del comando como mensaje del sistema
    3. Continúa llamando al LLM para que siga trabajando
    
    Returns:
        Información para que el frontend inicie un nuevo stream de chat
    """
    # Obtener información del objetivo
    objective = db.get_objective_by_id(req.objective_id)
    if not objective:
        raise HTTPException(status_code=404, detail="Objective not found")
    
    mission_id = objective["mission_id"]
    mission = db.get_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    
    conversation_id = mission["conversation_id"]
    
    # Construir mensaje de continuación
    if req.was_approved:
        resume_message = f"""[SISTEMA] El comando fue APROBADO y ejecutado.

**Resultado de la ejecución:**
```
{req.command_result or 'Comando ejecutado exitosamente'}
```

**Instrucciones:**
- Analiza el resultado del comando
- Actualiza el estado del objetivo según corresponda
- CONTINÚA con el siguiente paso del plan de ataque
- NO esperes confirmación del usuario, actúa de forma AUTÓNOMA"""
    else:
        resume_message = f"""[SISTEMA] El comando fue RECHAZADO por el usuario.

**Instrucciones:**
- El objetivo actual debe ser marcado como SKIPPED
- Busca una alternativa o continúa con el siguiente objetivo
- CONTINÚA con el plan de ataque de forma AUTÓNOMA
- NO esperes confirmación del usuario"""
    
    return {
        "success": True,
        "conversation_id": conversation_id,
        "mission_id": mission_id,
        "objective_id": req.objective_id,
        "resume_message": resume_message,
        "should_continue": True
    }
