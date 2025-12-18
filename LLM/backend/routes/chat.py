"""
routes/chat.py - Endpoint de chat con soporte para streaming.
"""

import json
import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from typing import Optional, List, Dict, Any

from models import ChatRequest, ChatResponse, ERROR_CODES
import database as db

router = APIRouter(tags=["Chat"])


def get_client(provider: str, api_key: str) -> AsyncOpenAI:
    """
    Factory: devuelve un cliente OpenAI configurado para el proveedor correcto.
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
    # 5. LLAMAR AL LLM
    # ==========================================================================
    
    try:
        client = get_client(req.provider, req.api_key)
        
        print(f"🤖 Chat con {req.provider} -> {req.model_id} (stream={req.stream})")
        
        if req.stream:
            # MODO STREAMING
            return StreamingResponse(
                stream_chat_response(
                    client=client,
                    model_id=req.model_id,
                    messages=messages_for_llm,
                    tools=req.tools,
                    conversation_id=conversation_id,
                    user_msg_id=user_msg_id,
                    temperature=req.temperature,
                    top_p=req.top_p,
                    max_tokens=req.max_tokens
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
                tools=req.tools,
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
    max_tokens: Optional[int] = None
):
    """
    Generador asíncrono para streaming con Server-Sent Events (SSE).
    """
    full_content = ""
    tool_calls_accumulator = []
    finish_reason = "stop"
    
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
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    tc_data = json.dumps({
                        "type": "tool_call",
                        "tool_call": tc.model_dump() if hasattr(tc, 'model_dump') else dict(tc),
                        "done": False
                    })
                    yield f"event: tool_call\ndata: {tc_data}\n\n"
                    
                    # Acumular para guardar después
                    tool_calls_accumulator.append(tc.model_dump() if hasattr(tc, 'model_dump') else dict(tc))
            
            # Capturar finish_reason
            if chunk_finish:
                finish_reason = chunk_finish
        
        # =======================================================================
        # GUARDAR MENSAJE COMPLETO AL FINALIZAR
        # =======================================================================
        
        tool_calls_json = json.dumps(tool_calls_accumulator) if tool_calls_accumulator else None
        
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
        
        # Enviar evento final
        done_data = json.dumps({
            "type": "done",
            "conversation_id": conversation_id,
            "user_message_id": user_msg_id,
            "assistant_message_id": assistant_msg_id,
            "finish_reason": finish_reason,
            "done": True
        })
        yield f"event: done\ndata: {done_data}\n\n"
        
        print(f"✅ Stream completado, mensaje guardado: {assistant_msg_id}")
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error en streaming: {error_msg}")
        
        # Determinar código de error
        if "401" in error_msg:
            code = "INVALID_API_KEY"
        elif "429" in error_msg:
            code = "RATE_LIMITED"
        else:
            code = "STREAM_ERROR"
        
        error_data = json.dumps({
            "type": "error",
            "code": code,
            "message": error_msg[:200],
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
