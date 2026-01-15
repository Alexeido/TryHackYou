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
                        except Exception as e:
                            print(f"⚠️ Error registrando job: {e}")
                
                if result.get("stdout"):
                    output_parts.append(f"STDOUT:\n{result['stdout']}")
                if result.get("stderr"):
                    output_parts.append(f"STDERR:\n{result['stderr']}")
                if result.get("return_code") is not None:
                    output_parts.append(f"EXIT CODE: {result['return_code']}")
                
                return "\n\n".join(output_parts) if output_parts else "Command executed (no output)"
                
            except httpx.TimeoutException as e:
                print(f"⏱️ Timeout ejecutando comando: {command[:100]}")
                return f"Error: Timeout ejecutando comando (más de 120s)"
            except httpx.ConnectError as e:
                print(f"🔌 Error de conexión al sandbox: {e}")
                return f"Error: No se pudo conectar al sandbox - {str(e)}"
            except httpx.HTTPStatusError as e:
                print(f"🚫 Error HTTP del sandbox: {e.response.status_code}")
                return f"Error HTTP {e.response.status_code} del sandbox: {str(e)}"
            except httpx.HTTPError as e:
                print(f"❌ Error HTTP genérico: {e}")
                return f"Error ejecutando comando: {str(e)}"
            except json.JSONDecodeError as e:
                print(f"📄 Error parseando respuesta JSON del sandbox: {e}")
                return f"Error: Respuesta inválida del sandbox (no es JSON válido)"
            except Exception as e:
                print(f"💥 Error inesperado ejecutando comando: {type(e).__name__}: {e}")
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
    max_tokens: Optional[int] = None
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
                    print(f"🔍 DEBUG chunk estructura: {json.dumps(chunk_raw, default=str)[:1000]}")
                except Exception as e:
                    print(f"🔍 DEBUG chunk error: {e}")
            
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
                    # Usar model_dump con mode='python' para obtener todos los campos
                    tc_dict = tc.model_dump(mode='python', exclude_unset=False) if hasattr(tc, 'model_dump') else dict(tc)
                    
                    # GEMINI 3 THOUGHT SIGNATURE: Capturar de múltiples formas posibles
                    # El SDK puede no incluirlo en model_dump(), así que intentamos acceso directo
                    if hasattr(tc, 'thought_signature') and tc.thought_signature:
                        tc_dict['thought_signature'] = tc.thought_signature
                    if hasattr(tc, 'thoughtSignature') and tc.thoughtSignature:
                        tc_dict['thought_signature'] = tc.thoughtSignature
                    # También verificar en extra_content (formato API OpenAI compatible de Google)
                    if hasattr(tc, 'extra_content') and tc.extra_content:
                        tc_dict['extra_content'] = tc.extra_content
                        if isinstance(tc.extra_content, dict) and 'google' in tc.extra_content:
                            google_data = tc.extra_content['google']
                            if isinstance(google_data, dict) and 'thought_signature' in google_data:
                                tc_dict['thought_signature'] = google_data['thought_signature']
                    # Acceso a __dict__ para campos que pydantic no expone
                    if hasattr(tc, '__dict__'):
                        for key in ['thought_signature', 'thoughtSignature', 'extra_content']:
                            if key in tc.__dict__ and tc.__dict__[key]:
                                tc_dict[key] = tc.__dict__[key]
                    
                    # Log para debug de campos extra (thought_signature)
                    extra_fields = {k: v for k, v in tc_dict.items() if k not in ['id', 'type', 'function', 'index']}
                    if extra_fields:
                        print(f"🔐 Tool call extra fields: {list(extra_fields.keys())}")
                    
                    tc_data = json.dumps({
                        "type": "tool_call",
                        "tool_call": tc_dict,
                        "done": False
                    })
                    yield f"event: tool_call\ndata: {tc_data}\n\n"
                    
                    # Acumular para guardar después (incluir todos los campos)
                    tool_calls_accumulator.append(tc_dict)
            
            # Capturar finish_reason
            if chunk_finish:
                finish_reason = chunk_finish
        
        # =======================================================================
        # GUARDAR MENSAJE COMPLETO AL FINALIZAR
        # =======================================================================
        
        tool_calls_json = json.dumps(tool_calls_accumulator) if tool_calls_accumulator else None
        
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
            print(f"🔧 Raw tool_calls_accumulator: {json.dumps(tool_calls_accumulator, indent=2)[:500]}")
            
            # Reconstruir tool_calls en formato completo
            # Algunos proveedores envían deltas (chunks), otros envían completo
            reconstructed_tool_calls = []
            current_tc = None
            
            for tc_delta in tool_calls_accumulator:
                # Verificar si ya es un tool_call completo (tiene id y function.name)
                tc_id = tc_delta.get('id')
                func_info = tc_delta.get('function', {})
                func_name = func_info.get('name', '')
                func_args = func_info.get('arguments', '')
                
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
                elif current_tc and func_args:
                    # Es un chunk de argumentos adicional, concatenar
                    current_tc['function']['arguments'] += func_args
            
            # No olvidar el último
            if current_tc:
                reconstructed_tool_calls.append(current_tc)
            
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
                
                # Guardar mensaje de tool
                tool_msg_id = db.add_message(
                    conversation_id=conversation_id,
                    role="tool",
                    content=result,
                    parent_id=assistant_msg_id,
                    tool_call_id=tc_id
                )
                
                # Enviar resultado completo al LLM (la primera vez necesita verlo todo)
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
            # CONTINUAR LA CONVERSACIÓN CON LOS RESULTADOS (LOOP)
            # =================================================================
            
            print(f"🔄 Continuando conversación con resultados de {len(tool_results)} tools...")
            
            # Reconstruir mensajes para el siguiente llamado
            # OPTIMIZACIÓN: Limitar el contexto para no exceder tokens
            MAX_MESSAGES_IN_LOOP = 30
            current_messages = messages.copy()
            
            # Debug: mostrar los tool_calls que vamos a enviar
            print(f"📤 Tool calls a enviar (con campos extra):")
            for tc in reconstructed_tool_calls:
                extra_keys = [k for k in tc.keys() if k not in ['id', 'type', 'function']]
                print(f"   - {tc.get('id')}: extra_fields={extra_keys}")
            
            current_messages.append({
                "role": "assistant",
                "content": full_content if full_content else None,
                "tool_calls": reconstructed_tool_calls
            })
            for tr in tool_results:
                current_messages.append(tr)
            
            # Limitar mensajes si hay demasiados
            if len(current_messages) > MAX_MESSAGES_IN_LOOP:
                # Preservar system prompt
                if current_messages and current_messages[0]['role'] == 'system':
                    system_msg = [current_messages[0]]
                    current_messages = system_msg + current_messages[-(MAX_MESSAGES_IN_LOOP - 1):]
                else:
                    current_messages = current_messages[-MAX_MESSAGES_IN_LOOP:]
                print(f"⚠️ Contexto del loop truncado a {len(current_messages)} mensajes")
            
            # Variables para el loop
            current_parent_id = tool_msg_id
            current_assistant_msg_id = assistant_msg_id
            max_iterations = 50  # Límite alto de seguridad (normalmente no debería llegar)
            iteration = 0
            
            while iteration < max_iterations:
                iteration += 1
                print(f"🔁 Iteración {iteration} del loop de tools...")
                
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
                loop_tool_calls = []
                
                loop_stream = await client.chat.completions.create(**loop_params)
                async for chunk in loop_stream:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    if delta.content:
                        loop_content += delta.content
                        event_data = json.dumps({
                            "type": "content",
                            "chunk": delta.content,
                            "done": False
                        })
                        yield f"event: message\ndata: {event_data}\n\n"
                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            tc_data = tc.model_dump() if hasattr(tc, 'model_dump') else dict(tc)
                            # GEMINI 3: Capturar thought_signature
                            if hasattr(tc, 'thought_signature') and tc.thought_signature:
                                tc_data['thought_signature'] = tc.thought_signature
                            if hasattr(tc, 'thoughtSignature') and tc.thoughtSignature:
                                tc_data['thought_signature'] = tc.thoughtSignature
                            if hasattr(tc, 'extra_content') and tc.extra_content:
                                tc_data['extra_content'] = tc.extra_content
                            if hasattr(tc, '__dict__'):
                                for key in ['thought_signature', 'thoughtSignature', 'extra_content']:
                                    if key in tc.__dict__ and tc.__dict__[key]:
                                        tc_data[key] = tc.__dict__[key]
                            loop_tool_calls.append(tc_data)
                            # Notificar tool call al frontend
                            tc_event = json.dumps({
                                "type": "tool_call",
                                "tool_call": tc_data,
                                "done": False
                            })
                            yield f"event: tool_call\ndata: {tc_event}\n\n"
                
                # Guardar respuesta del asistente de esta iteración
                loop_tool_calls_json = json.dumps(loop_tool_calls) if loop_tool_calls else None
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
                
                # Si no hay más tool calls, terminamos
                if not loop_tool_calls:
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
                    func_name = func_info.get('name', '')
                    func_args = func_info.get('arguments', '')
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
                    elif current_tc and func_args:
                        current_tc['function']['arguments'] += func_args
                if current_tc:
                    loop_reconstructed.append(current_tc)
                
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
                
                # Actualizar mensajes para la siguiente iteración
                current_messages.append({
                    "role": "assistant",
                    "content": loop_content if loop_content else None,
                    "tool_calls": loop_reconstructed
                })
                for tr in loop_tool_results:
                    current_messages.append(tr)
                
                # Limitar contexto para evitar exceder tokens
                if len(current_messages) > MAX_MESSAGES_IN_LOOP:
                    if current_messages and current_messages[0]['role'] == 'system':
                        system_msg = [current_messages[0]]
                        current_messages = system_msg + current_messages[-(MAX_MESSAGES_IN_LOOP - 1):]
                    else:
                        current_messages = current_messages[-MAX_MESSAGES_IN_LOOP:]
                    print(f"⚠️ Contexto del loop truncado a {len(current_messages)} mensajes (iteración {iteration})")
                
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
