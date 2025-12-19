"""
routes/chat.py - Endpoint de chat con soporte para streaming.
"""

import json
import asyncio
import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from typing import Optional, List, Dict, Any

from models import ChatRequest, ChatResponse, ERROR_CODES
import database as db

router = APIRouter(tags=["Chat"])

# URL del sandbox para ejecutar comandos
SANDBOX_URL = "http://localhost:5000"


async def execute_tool_call(tool_call: Dict[str, Any], conversation_id: str) -> str:
    """
    Ejecuta una tool call en el sandbox y retorna el resultado.
    """
    function_name = tool_call.get("function", {}).get("name")
    function_args_str = tool_call.get("function", {}).get("arguments", "{}")
    
    print(f"🔧 Ejecutando tool: {function_name}")
    
    try:
        function_args = json.loads(function_args_str)
    except json.JSONDecodeError:
        return f"Error: argumentos inválidos: {function_args_str}"
    
    if function_name == "execute_command":
        command = function_args.get("command")
        wait_time = function_args.get("wait_time", 5)
        exit_time = function_args.get("exit_time")
        
        if not command:
            return "Error: comando no especificado"
        
        # Ejecutar en el sandbox
        async with httpx.AsyncClient(timeout=120.0) as client:
            payload = {
                "command": command,
                "conversation_id": conversation_id,
                "wait_time": wait_time
            }
            if exit_time:
                payload["exit_time"] = exit_time
            
            try:
                response = await client.post(f"{SANDBOX_URL}/execute", json=payload)
                response.raise_for_status()
                result = response.json()
                
                # Formatear salida
                output_parts = []
                if result.get("stdout"):
                    output_parts.append(f"STDOUT:\n{result['stdout']}")
                if result.get("stderr"):
                    output_parts.append(f"STDERR:\n{result['stderr']}")
                if result.get("return_code") is not None:
                    output_parts.append(f"EXIT CODE: {result['return_code']}")
                
                return "\n\n".join(output_parts) if output_parts else "Command executed (no output)"
                
            except httpx.HTTPError as e:
                return f"Error ejecutando comando: {str(e)}"
    
    return f"Error: tool '{function_name}' no implementada"


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
        
        # =======================================================================
        # EJECUTAR TOOL CALLS AUTOMÁTICAMENTE Y CONTINUAR LOOP
        # =======================================================================
        
        if finish_reason == "tool_calls" and tool_calls_accumulator:
            print(f"🔧 Ejecutando {len(tool_calls_accumulator)} tool calls automáticamente...")
            
            # Reconstruir tool_calls en formato completo
            reconstructed_tool_calls = []
            current_tc = None
            for tc_delta in tool_calls_accumulator:
                idx = tc_delta.get('index', 0)
                if tc_delta.get('id'):
                    if current_tc:
                        reconstructed_tool_calls.append(current_tc)
                    current_tc = {
                        'id': tc_delta['id'],
                        'type': tc_delta.get('type', 'function'),
                        'function': {
                            'name': tc_delta.get('function', {}).get('name', ''),
                            'arguments': tc_delta.get('function', {}).get('arguments', '')
                        }
                    }
                elif current_tc:
                    # Concatenar argumentos
                    current_tc['function']['arguments'] += tc_delta.get('function', {}).get('arguments', '')
            
            if current_tc:
                reconstructed_tool_calls.append(current_tc)
            
            # Ejecutar cada tool call y guardar resultados
            tool_results = []
            for tc in reconstructed_tool_calls:
                tc_id = tc['id']
                func_name = tc['function']['name']
                func_args = tc['function']['arguments']
                
                print(f"  ▶ Ejecutando: {func_name}({func_args[:50]}...)")
                
                # Notificar al frontend que estamos ejecutando
                exec_event = json.dumps({
                    "type": "tool_executing",
                    "tool_call_id": tc_id,
                    "function_name": func_name,
                    "done": False
                })
                yield f"event: tool_executing\ndata: {exec_event}\n\n"
                
                # Ejecutar la tool
                result = await execute_tool_call(tc, conversation_id)
                
                # Guardar mensaje de tool
                tool_msg_id = db.add_message(
                    conversation_id=conversation_id,
                    role="tool",
                    content=result,
                    parent_id=assistant_msg_id,
                    tool_call_id=tc_id
                )
                
                tool_results.append({
                    "tool_call_id": tc_id,
                    "role": "tool",
                    "content": result
                })
                
                # Notificar al frontend del resultado
                result_event = json.dumps({
                    "type": "tool_result",
                    "tool_call_id": tc_id,
                    "result": result[:500],  # Truncar para el evento
                    "tool_message_id": tool_msg_id,
                    "done": False
                })
                yield f"event: tool_result\ndata: {result_event}\n\n"
            
            # Actualizar active_leaf al último mensaje de tool
            db.update_conversation_leaf(conversation_id, tool_msg_id)
            
            # =================================================================
            # CONTINUAR LA CONVERSACIÓN CON LOS RESULTADOS
            # =================================================================
            
            print(f"🔄 Continuando conversación con resultados de {len(tool_results)} tools...")
            
            # Reconstruir mensajes para el siguiente llamado
            new_messages = messages.copy()
            new_messages.append({
                "role": "assistant",
                "content": full_content if full_content else None,
                "tool_calls": reconstructed_tool_calls
            })
            for tr in tool_results:
                new_messages.append(tr)
            
            # Llamar al LLM de nuevo con los resultados
            params2 = {
                "model": model_id,
                "messages": new_messages,
                "tools": tools if tools else None,
                "tool_choice": "auto" if tools else None,
                "stream": True
            }
            if temperature is not None:
                params2["temperature"] = temperature
            if top_p is not None:
                params2["top_p"] = top_p
            if max_tokens is not None:
                params2["max_tokens"] = max_tokens
            
            # Segunda ronda de streaming
            full_content_2 = ""
            tool_calls_2 = []
            
            stream2 = await client.chat.completions.create(**params2)
            async for chunk in stream2:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta.content:
                    full_content_2 += delta.content
                    event_data = json.dumps({
                        "type": "content",
                        "chunk": delta.content,
                        "done": False
                    })
                    yield f"event: message\ndata: {event_data}\n\n"
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        tool_calls_2.append(tc.model_dump() if hasattr(tc, 'model_dump') else dict(tc))
            
            # Guardar segunda respuesta del asistente
            tool_calls_json_2 = json.dumps(tool_calls_2) if tool_calls_2 else None
            assistant_msg_id_2 = db.add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=full_content_2 if full_content_2 else None,
                parent_id=tool_msg_id,  # Hijo del último tool message
                tool_calls=tool_calls_json_2,
                model_used=model_id
            )
            db.update_conversation_leaf(conversation_id, assistant_msg_id_2)
            db.update_conversation_timestamp(conversation_id)
            
            # Evento done con el ID final
            done_data = json.dumps({
                "type": "done",
                "conversation_id": conversation_id,
                "user_message_id": user_msg_id,
                "assistant_message_id": assistant_msg_id_2,
                "finish_reason": "stop",
                "had_tool_calls": True,
                "done": True
            })
            yield f"event: done\ndata: {done_data}\n\n"
            print(f"✅ Loop de tools completado, mensaje final: {assistant_msg_id_2}")
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
