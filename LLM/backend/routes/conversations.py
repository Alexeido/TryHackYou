"""
routes/conversations.py - CRUD de conversaciones y gestión del árbol.
"""

from fastapi import APIRouter, HTTPException
from typing import Optional

from models import (
    ConversationCreate,
    ConversationResponse,
    ConversationListResponse,
    ConversationListItem,
    ActiveLeafUpdate,
    ThreadResponse,
    TreeResponse,
    TreeNode,
    MessageResponse,
    ErrorResponse
)
import database as db

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.post("", response_model=ConversationResponse)
async def create_conversation(req: ConversationCreate):
    """
    Crea una nueva conversación con su system prompt como mensaje raíz.
    """
    try:
        result = db.create_conversation(
            title=req.title or "Nueva conversación",
            system_prompt=req.system_prompt
        )
        return ConversationResponse(
            id=result["id"],
            title=req.title or "Nueva conversación",
            system_message_id=result["system_message_id"],
            created_at=result["created_at"]
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"code": "DATABASE_ERROR", "message": str(e)}
        )


@router.get("", response_model=ConversationListResponse)
async def list_conversations(limit: int = 50, offset: int = 0):
    """
    Lista todas las conversaciones ordenadas por fecha de actualización.
    """
    try:
        result = db.list_conversations(limit=limit, offset=offset)
        
        conversations = [
            ConversationListItem(
                id=c["id"],
                title=c["title"],
                created_at=c["created_at"],
                updated_at=c["updated_at"],
                message_count=c["message_count"]
            )
            for c in result["conversations"]
        ]
        
        return ConversationListResponse(
            total=result["total"],
            conversations=conversations
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"code": "DATABASE_ERROR", "message": str(e)}
        )


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: str):
    """
    Obtiene los metadatos de una conversación.
    """
    conv = db.get_conversation(conversation_id)
    
    if not conv:
        raise HTTPException(
            status_code=404,
            detail={"code": "CONVERSATION_NOT_FOUND", "message": "Conversación no encontrada"}
        )
    
    return conv


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """
    Elimina una conversación y todos sus mensajes.
    """
    success = db.delete_conversation(conversation_id)
    
    if not success:
        raise HTTPException(
            status_code=404,
            detail={"code": "CONVERSATION_NOT_FOUND", "message": "Conversación no encontrada"}
        )
    
    return {"success": True, "deleted_id": conversation_id}


@router.get("/{conversation_id}/thread", response_model=ThreadResponse)
async def get_thread(conversation_id: str):
    """
    Obtiene la rama activa de una conversación.
    Reconstruye desde active_leaf_id hacia atrás.
    """
    conv = db.get_conversation(conversation_id)
    
    if not conv:
        raise HTTPException(
            status_code=404,
            detail={"code": "CONVERSATION_NOT_FOUND", "message": "Conversación no encontrada"}
        )
    
    if not conv["active_leaf_id"]:
        return ThreadResponse(conversation_id=conversation_id, messages=[])
    
    # Reconstruir thread
    thread = db.reconstruct_thread(conv["active_leaf_id"])
    
    messages = [
        MessageResponse(
            id=msg["id"],
            conversation_id=msg["conversation_id"],
            parent_id=msg["parent_id"],
            role=msg["role"],
            content=msg["content"],
            tool_calls=msg["tool_calls"],
            tool_call_id=msg["tool_call_id"],
            model_used=msg["model_used"],
            created_at=msg["created_at"]
        )
        for msg in thread
    ]
    
    return ThreadResponse(conversation_id=conversation_id, messages=messages)


@router.get("/{conversation_id}/tree", response_model=TreeResponse)
async def get_tree(conversation_id: str):
    """
    Obtiene la estructura completa del árbol para mostrar ramificaciones.
    """
    conv = db.get_conversation(conversation_id)
    
    if not conv:
        raise HTTPException(
            status_code=404,
            detail={"code": "CONVERSATION_NOT_FOUND", "message": "Conversación no encontrada"}
        )
    
    tree = db.get_tree_structure(conversation_id)
    
    nodes = [
        TreeNode(
            id=node["id"],
            parent_id=node["parent_id"],
            role=node["role"],
            content_preview=node.get("content_preview"),
            children_count=node["children_count"]
        )
        for node in tree["nodes"]
    ]
    
    return TreeResponse(nodes=nodes, active_leaf=tree["active_leaf"])


@router.patch("/{conversation_id}/active-leaf")
async def update_active_leaf(conversation_id: str, req: ActiveLeafUpdate):
    """
    Cambia la rama activa de una conversación.
    """
    # Verificar que el mensaje existe y pertenece a la conversación
    msg = db.get_message(req.leaf_id)
    
    if not msg:
        raise HTTPException(
            status_code=404,
            detail={"code": "MESSAGE_NOT_FOUND", "message": "Mensaje no encontrado"}
        )
    
    if msg["conversation_id"] != conversation_id:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_MESSAGE", "message": "El mensaje no pertenece a esta conversación"}
        )
    
    success = db.update_conversation_leaf(conversation_id, req.leaf_id)
    
    if not success:
        raise HTTPException(
            status_code=404,
            detail={"code": "CONVERSATION_NOT_FOUND", "message": "Conversación no encontrada"}
        )
    
    return {"success": True, "active_leaf_id": req.leaf_id}
