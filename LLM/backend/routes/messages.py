"""
routes/messages.py - Endpoints para edición y gestión de mensajes individuales.
"""

from fastapi import APIRouter, HTTPException

from models import MessageEdit, MessageEditResponse, MessageResponse
import database as db

router = APIRouter(prefix="/messages", tags=["Messages"])


@router.get("/{message_id}", response_model=MessageResponse)
async def get_message(message_id: int):
    """
    Obtiene un mensaje por su ID.
    """
    msg = db.get_message(message_id)
    
    if not msg:
        raise HTTPException(
            status_code=404,
            detail={"code": "MESSAGE_NOT_FOUND", "message": "Mensaje no encontrado"}
        )
    
    return MessageResponse(
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


@router.patch("/{message_id}", response_model=MessageEditResponse)
async def edit_message(message_id: int, req: MessageEdit):
    """
    Edita un mensaje.
    
    Si create_branch=True (recomendado):
        - Crea un nuevo mensaje con el mismo parent_id pero contenido editado
        - No modifica el mensaje original
        - Actualiza active_leaf_id al nuevo mensaje
    
    Si create_branch=False (destructivo):
        - Edita el contenido del mensaje in-place
        - ELIMINA todos los descendientes (hijos, nietos, etc.)
    """
    # Obtener mensaje original
    msg = db.get_message(message_id)
    
    if not msg:
        raise HTTPException(
            status_code=404,
            detail={"code": "MESSAGE_NOT_FOUND", "message": "Mensaje no encontrado"}
        )
    
    # No permitir editar mensajes de system o assistant
    if msg["role"] not in ["user"]:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_EDIT",
                "message": f"No se puede editar mensajes con rol '{msg['role']}'. Solo se pueden editar mensajes de usuario."
            }
        )
    
    conversation_id = msg["conversation_id"]
    parent_id = msg["parent_id"]
    
    if req.create_branch:
        # MODO BRANCH: Crear nuevo mensaje con mismo padre
        new_msg_id = db.add_message(
            conversation_id=conversation_id,
            role="user",
            content=req.content,
            parent_id=parent_id
        )
        
        # Actualizar active_leaf al nuevo mensaje
        db.update_conversation_leaf(conversation_id, new_msg_id)
        db.update_conversation_timestamp(conversation_id)
        
        return MessageEditResponse(
            message_id=new_msg_id,
            conversation_id=conversation_id,
            is_new_branch=True,
            parent_id=parent_id
        )
    
    else:
        # MODO DESTRUCTIVO: Editar in-place y eliminar descendientes
        
        # 1. Eliminar todos los descendientes
        deleted_count = db.delete_descendants(message_id)
        print(f"🗑️ Eliminados {deleted_count} mensajes descendientes")
        
        # 2. Actualizar contenido
        db.update_message_content(message_id, req.content)
        
        # 3. Actualizar active_leaf al mensaje editado
        db.update_conversation_leaf(conversation_id, message_id)
        db.update_conversation_timestamp(conversation_id)
        
        return MessageEditResponse(
            message_id=message_id,
            conversation_id=conversation_id,
            is_new_branch=False,
            parent_id=parent_id
        )


@router.delete("/{message_id}")
async def delete_message(message_id: int):
    """
    Elimina un mensaje y todos sus descendientes.
    
    CUIDADO: Esta operación es destructiva y elimina toda la rama.
    """
    msg = db.get_message(message_id)
    
    if not msg:
        raise HTTPException(
            status_code=404,
            detail={"code": "MESSAGE_NOT_FOUND", "message": "Mensaje no encontrado"}
        )
    
    # No permitir eliminar el system prompt
    if msg["role"] == "system" and msg["parent_id"] is None:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "CANNOT_DELETE_SYSTEM",
                "message": "No se puede eliminar el mensaje de sistema"
            }
        )
    
    conversation_id = msg["conversation_id"]
    parent_id = msg["parent_id"]
    
    # Eliminar descendientes primero
    deleted_descendants = db.delete_descendants(message_id)
    
    # Eliminar el mensaje
    with db.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM messages WHERE id = ?", (message_id,))
        conn.commit()
    
    # Actualizar active_leaf al padre si es necesario
    conv = db.get_conversation(conversation_id)
    if conv and conv["active_leaf_id"] == message_id:
        db.update_conversation_leaf(conversation_id, parent_id)
    
    return {
        "success": True,
        "deleted_message_id": message_id,
        "deleted_descendants_count": deleted_descendants,
        "new_active_leaf": parent_id
    }
