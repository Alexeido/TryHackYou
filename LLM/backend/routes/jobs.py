"""
routes/jobs.py - Endpoints para gestión de background jobs.

Permite al frontend:
1. Consultar jobs pendientes de una conversación
2. Obtener jobs completados no notificados
3. SSE para recibir notificaciones de jobs completados en tiempo real
"""

import json
import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

import database as db
from job_monitor import register_notification_callback, unregister_notification_callback

router = APIRouter(prefix="/jobs", tags=["Jobs"])


class JobCompletedEvent(BaseModel):
    job_id: str
    conversation_id: str
    leaf_id: int
    command: str
    result: str


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/{conversation_id}/pending")
async def get_pending_jobs(conversation_id: str) -> List[Dict[str, Any]]:
    """
    Obtiene los jobs en ejecución para una conversación.
    """
    jobs = db.get_pending_jobs(conversation_id)
    return jobs


@router.get("/{conversation_id}/completed")
async def get_completed_jobs(conversation_id: str, leaf_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Obtiene jobs completados no notificados para una rama específica.
    
    Si no se especifica leaf_id, devuelve todos los completados de la conversación.
    """
    if leaf_id:
        jobs = db.get_unnotified_completed_jobs(conversation_id, leaf_id)
    else:
        # Devolver todos los completados no notificados
        with db.get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM pending_jobs 
                WHERE conversation_id = ? AND status = 'completed' AND notified = 0
                ORDER BY completed_at ASC
            """, (conversation_id,))
            jobs = [dict(row) for row in cursor.fetchall()]
    
    return jobs


@router.post("/{job_id}/mark-notified")
async def mark_job_notified(job_id: str):
    """
    Marca un job como notificado al LLM.
    """
    success = db.mark_job_notified(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"status": "ok", "job_id": job_id}


@router.get("/{conversation_id}/stream")
async def job_notifications_stream(conversation_id: str):
    """
    SSE stream para recibir notificaciones de jobs completados en tiempo real.
    
    El frontend debe conectarse a este endpoint cuando está en una conversación
    para recibir notificaciones cuando los jobs en background terminan.
    """
    
    async def event_generator():
        queue = asyncio.Queue()
        
        async def on_job_complete(job_id: str, result: str, leaf_id: int):
            await queue.put({
                "job_id": job_id,
                "result": result,
                "leaf_id": leaf_id
            })
        
        # Registrar callback
        register_notification_callback(conversation_id, on_job_complete)
        
        try:
            # Enviar heartbeat inicial
            yield f"event: connected\ndata: {json.dumps({'conversation_id': conversation_id})}\n\n"
            
            while True:
                try:
                    # Esperar evento con timeout para heartbeat
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    
                    yield f"event: job_completed\ndata: {json.dumps(event)}\n\n"
                    
                except asyncio.TimeoutError:
                    # Enviar heartbeat cada 30s para mantener conexión
                    yield f"event: heartbeat\ndata: {json.dumps({'ts': 'ping'})}\n\n"
                    
        except asyncio.CancelledError:
            pass
        finally:
            unregister_notification_callback(conversation_id)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
