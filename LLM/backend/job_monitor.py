"""
job_monitor.py - Background service para monitorear jobs del sandbox.

Este servicio:
1. Hace polling de los jobs pendientes registrados en la BD
2. Consulta el sandbox para ver si han terminado
3. Cuando terminan, guarda el resultado y notifica via WebSocket/SSE
"""

import asyncio
import httpx
from typing import Dict, Any, Callable, Optional
from datetime import datetime

import database as db

# URL del sandbox
SANDBOX_URL = "http://localhost:5000"

# Callbacks registrados para notificar resultados
# {conversation_id: callback_function}
_notification_callbacks: Dict[str, Callable] = {}


async def check_job_status(job_id: str) -> Dict[str, Any]:
    """
    Consulta el estado de un job en el sandbox.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{SANDBOX_URL}/status/{job_id}")
            if response.status_code == 200:
                return response.json()
            else:
                return {"status": "error", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}


def format_job_result(result: Dict[str, Any]) -> str:
    """
    Formatea el resultado de un job para guardarlo.
    """
    output_parts = []
    
    if result.get("stdout"):
        output_parts.append(f"STDOUT:\n{result['stdout']}")
    if result.get("stderr"):
        output_parts.append(f"STDERR:\n{result['stderr']}")
    if result.get("return_code") is not None:
        output_parts.append(f"EXIT CODE: {result['return_code']}")
    
    return "\n\n".join(output_parts) if output_parts else "(no output)"


async def poll_pending_jobs():
    """
    Revisa todos los jobs pendientes y actualiza su estado.
    Cuando un job termina:
    1. Guarda el resultado en pending_jobs
    2. Crea el mensaje tool en la conversación
    3. Actualiza mission_jobs si existe
    4. Notifica via callback
    """
    pending = db.get_pending_jobs()
    
    for job in pending:
        job_id = job['job_id']
        
        # Consultar estado en el sandbox
        result = await check_job_status(job_id)
        
        if result.get("status") == "finished":
            # Job completado - guardar resultado
            formatted_result = format_job_result(result)
            db.complete_pending_job(job_id, formatted_result)
            
            # SPRINT 2: Actualizar mission_job si existe
            return_code = result.get("return_code", 0)
            mission_job_status = "COMPLETED" if return_code == 0 else "FAILED"
            try:
                db.complete_mission_job(job_id, mission_job_status)
                print(f"🎯 Mission job {job_id[:8]} marcado como {mission_job_status}")
            except Exception as e:
                # Es normal que falle si no hay mission_job asociado
                pass
            
            conv_id = job['conversation_id']
            leaf_id = job['leaf_id']
            tool_call_id = job.get('tool_call_id')
            
            print(f"✅ Job {job_id[:8]} completado para conv {conv_id[:12]}")
            
            # IMPORTANTE: Crear el mensaje tool en la conversación
            # Esto permite que el LLM vea el resultado cuando se le envíe el contexto
            if tool_call_id:
                tool_msg_id = db.add_message(
                    conversation_id=conv_id,
                    role="tool",
                    content=formatted_result,
                    parent_id=leaf_id,
                    tool_call_id=tool_call_id
                )
                # Actualizar el leaf activo
                db.update_conversation_leaf(conv_id, tool_msg_id)
                print(f"📝 Mensaje tool creado (id={tool_msg_id}) para job {job_id[:8]}")
            
            # Notificar si hay callback registrado
            if conv_id in _notification_callbacks:
                try:
                    await _notification_callbacks[conv_id](job_id, formatted_result, leaf_id)
                except Exception as e:
                    print(f"❌ Error notificando job {job_id}: {e}")
        
        elif result.get("status") == "error":
            # Error consultando - puede ser que el job ya no exista
            error_msg = f"Error checking job: {result.get('error', 'unknown')}"
            db.complete_pending_job(job_id, error_msg)
            print(f"⚠️ Job {job_id[:8]} marcado como error: {error_msg}")


def register_notification_callback(conversation_id: str, callback: Callable):
    """
    Registra un callback para recibir notificaciones de jobs completados.
    """
    _notification_callbacks[conversation_id] = callback
    print(f"📡 Callback registrado para {conversation_id[:12]}")


def unregister_notification_callback(conversation_id: str):
    """
    Elimina el callback de una conversación.
    """
    if conversation_id in _notification_callbacks:
        del _notification_callbacks[conversation_id]
        print(f"📡 Callback eliminado para {conversation_id[:12]}")


async def job_monitor_loop(interval: float = 5.0):
    """
    Loop principal del monitor de jobs.
    Se ejecuta cada `interval` segundos.
    """
    print(f"🔄 Job monitor iniciado (interval={interval}s)")
    
    while True:
        try:
            await poll_pending_jobs()
        except Exception as e:
            print(f"❌ Error en job monitor: {e}")
        
        await asyncio.sleep(interval)


# Variable global para el task del monitor
_monitor_task: Optional[asyncio.Task] = None


def start_job_monitor(interval: float = 5.0):
    """
    Inicia el monitor de jobs en background.
    Debe llamarse desde un contexto async.
    """
    global _monitor_task
    
    if _monitor_task is not None and not _monitor_task.done():
        print("⚠️ Job monitor ya está corriendo")
        return
    
    _monitor_task = asyncio.create_task(job_monitor_loop(interval))


def stop_job_monitor():
    """
    Detiene el monitor de jobs.
    """
    global _monitor_task
    
    if _monitor_task is not None:
        _monitor_task.cancel()
        _monitor_task = None
        print("🛑 Job monitor detenido")
