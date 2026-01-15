"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { MessageBubble } from "./MessageBubble";
import { 
  useChatStore, 
  useConfigStore, 
  useModelsStore,
  useUIStore,
  useConversationsStore,
  useTerminalStore,
  Message,
  ToolCall
} from "@/store/useStore";
import { 
  sendMessage, 
  sendMessageStream, 
  createConversation,
  getConversationThread,
  getConversationTree,
  subscribeToJobNotifications,
  markJobNotified,
  getCompletedJobs,
  type JobCompletedEvent
} from "@/services/api";
import {
  initTerminalSession,
  createCheckpoint,
  switchBranch,
  checkTerminalHealth,
} from "@/services/terminal";
import { getToolsForAPI } from "@/services/tools";
import { 
  Send, 
  Loader2, 
  StopCircle,
  Sparkles,
  AlertCircle
} from "lucide-react";
import { cn } from "@/lib/utils";

// Función para hacer los mensajes de error más legibles
function parseErrorMessage(error: string): string {
  // Primero: Detectar códigos de error específicos del backend
  // INVALID_REQUEST - Error de formato/validación (400)
  if (error.includes('INVALID_REQUEST') || error.includes('INVALID_ARGUMENT')) {
    return '🔧 Error de formato en la petición. Intenta de nuevo o reinicia la conversación.';
  }
  
  // PROVIDER_ERROR - Error del proveedor (500/503)
  if (error.includes('PROVIDER_ERROR') || error.includes('503') || error.includes('500')) {
    return '🔄 El proveedor de IA está experimentando problemas. Intenta de nuevo en unos segundos.';
  }
  
  // MAX_ITERATIONS - Límite de iteraciones alcanzado
  if (error.includes('MAX_ITERATIONS')) {
    return '🔄 Se alcanzó el límite de iteraciones. La tarea es muy compleja o el agente entró en un bucle.';
  }
  
  // OpenRouter - No endpoints / Data policy
  if (error.includes('No endpoints found') || error.includes('data policy')) {
    return '⚠️ Este modelo requiere configuración adicional en OpenRouter. Configura tu política de datos en https://openrouter.ai/settings/privacy o prueba con otro modelo.';
  }
  
  // Rate limit - Solo código 429 explícito (no "rate" genérico que podría ser "generate")
  if (error.includes('429') || error.toLowerCase().includes('rate limit') || error.toLowerCase().includes('rate_limit')) {
    return '⏳ Has alcanzado el límite de peticiones. Espera unos segundos antes de intentarlo de nuevo.';
  }
  
  // API key inválida - Solo 401 y "API key" explícito
  if (error.includes('401') || error.includes('API key invalid') || error.includes('Unauthorized')) {
    return '🔑 API key inválida o expirada. Verifica tu configuración en el panel de ajustes.';
  }
  
  // Sin créditos
  if (error.includes('402') || error.includes('credit') || error.includes('quota') || error.includes('billing')) {
    return '💳 Sin créditos disponibles. Recarga tu cuenta del proveedor para continuar.';
  }
  
  // Modelo no disponible - Solo 404 explícito
  if (error.includes('404') || error.includes('model not found') || error.includes('Model not found')) {
    return '🚫 Modelo no disponible. Puede estar en mantenimiento o haber sido descontinuado. Prueba con otro modelo.';
  }
  
  // Error de contexto
  if (error.includes('context') || error.includes('token') || error.includes('length')) {
    return '📏 El mensaje es demasiado largo para este modelo. Intenta con un mensaje más corto o un modelo con mayor contexto.';
  }
  
  // Timeout
  if (error.includes('timeout') || error.includes('Timeout')) {
    return '⏱️ La petición tardó demasiado. Intenta de nuevo.';
  }
  
  // Error genérico con el mensaje original
  return `❌ Error: ${error}`;
}

// Detectar si el error es por parámetros no soportados
function isUnsupportedParamError(error: string): boolean {
  return error.includes('Unsupported value') || 
         error.includes('does not support') ||
         error.includes('temperature') ||
         error.includes('top_p') ||
         error.includes('max_tokens');
}

export function ChatArea() {
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [paramErrorModel, setParamErrorModel] = useState<string | null>(null);  // Modelo que falló por params
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<(() => void) | null>(null);
  const prevLeafIdRef = useRef<number | null>(null);  // Para detectar cambios de branch
  
  const { 
    conversationId, 
    messages, 
    isLoading, 
    isStreaming,
    currentChunk,
    setConversation,
    setMessages,
    addMessage,
    updateMessage,
    setLoading,
    setStreaming,
    appendChunk,
    clearChunk,
    setActiveLeafId,
    setFullTree,
    activeLeafId,
    addStreamingToolCall,
    updateStreamingToolCall,
    clearStreamingToolCalls
  } = useChatStore();
  
  const { apiKeys, systemPrompt, backendUrl } = useConfigStore();
  const { selectedModel, advancedParams, modelsUsingDefaults, addModelToDefaults } = useModelsStore();
  const { setTerminalOpen } = useUIStore();
  const { addConversation, updateConversation } = useConversationsStore();
  const { 
    sessions, 
    initSession, 
    updateSessionLeaf,
    setConnected,
    setError: setTerminalError 
  } = useTerminalStore();

  // Verificar conexión con el sandbox al montar
  useEffect(() => {
    const checkConnection = async () => {
      try {
        await checkTerminalHealth();
        setConnected(true);
      } catch (err) {
        setConnected(false);
        console.log('[Terminal] Sandbox no disponible:', err);
      }
    };
    checkConnection();
    // Re-check cada 30 segundos
    const interval = setInterval(checkConnection, 30000);
    return () => clearInterval(interval);
  }, [setConnected]);

  // Inicializar sesión de terminal cuando cambia la conversación
  useEffect(() => {
    if (!conversationId) return;
    
    // Si ya está inicializada, no hacer nada
    if (sessions[conversationId]?.initialized) {
      console.log(`[Terminal] Sesión ya inicializada para ${conversationId}`);
      return;
    }
    
    const initSession_ = async () => {
      try {
        console.log(`[Terminal] Inicializando sesión para ${conversationId}`);
        const result = await initTerminalSession(conversationId);
        initSession(conversationId, result.repo_path);
        console.log(`[Terminal] Sesión inicializada: ${result.repo_path}`);
      } catch (err) {
        console.log('[Terminal] Error inicializando sesión:', err);
        // No es crítico, el sandbox puede no estar disponible
      }
    };
    
    initSession_();
  }, [conversationId, sessions, initSession]);

  // Detectar cambios de branch (navegación en el árbol)
  useEffect(() => {
    if (!conversationId || !activeLeafId) return;
    
    // Si es la primera vez, solo guardar la referencia
    if (prevLeafIdRef.current === null) {
      prevLeafIdRef.current = activeLeafId;
      return;
    }
    
    // Si cambió el leaf, es navegación en el árbol
    if (prevLeafIdRef.current !== activeLeafId) {
      const prevLeaf = prevLeafIdRef.current;
      prevLeafIdRef.current = activeLeafId;
      
      // Si la sesión está inicializada, hacer switch
      if (sessions[conversationId]?.initialized) {
        console.log(`[Terminal] Cambio de branch: ${prevLeaf} -> ${activeLeafId}`);
        switchBranch(conversationId, activeLeafId)
          .then((result) => {
            updateSessionLeaf(conversationId, activeLeafId);
            console.log(`[Terminal] Branch cambiado a leaf ${activeLeafId}`);
          })
          .catch((err) => {
            console.log('[Terminal] Error cambiando branch:', err);
          });
      }
    }
  }, [conversationId, activeLeafId, sessions, updateSessionLeaf]);

  // Auto-scroll al final cuando llegan nuevos mensajes
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, currentChunk]);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [input]);

  const getApiKey = useCallback(() => {
    if (!selectedModel) return null;
    const provider = selectedModel.provider;
    return apiKeys[provider] || null;
  }, [selectedModel, apiKeys]);

  // Obtener parámetros avanzados para el modelo actual
  const getAdvancedParamsForModel = useCallback(() => {
    if (!selectedModel) return {};
    // Si el modelo está en la lista de defaults, no enviar parámetros
    if (modelsUsingDefaults.includes(selectedModel.id)) {
      return {};
    }
    // Si no, enviar los parámetros configurados
    return {
      temperature: advancedParams.temperature,
      top_p: advancedParams.top_p,
      max_tokens: advancedParams.max_tokens,
    };
  }, [selectedModel, advancedParams, modelsUsingDefaults]);

  // Suscribirse al stream de jobs completados para notificaciones automáticas
  useEffect(() => {
    if (!conversationId) return;
    
    console.log(`[Jobs] Suscribiendo a notificaciones para ${conversationId}`);
    
    const handleJobCompleted = async (event: JobCompletedEvent) => {
      console.log(`[Jobs] Job completado: ${event.job_id}, leaf del job: ${event.leaf_id}, leaf actual: ${activeLeafId}`);
      
      // Procesar el resultado - el job_monitor ya creó el mensaje tool en la BD
      // No necesitamos verificar el leaf porque el mensaje tool ya está guardado
      console.log('[Jobs] Procesando resultado automáticamente');
      
      try {
        // Recargar el thread para ver los mensajes actualizados (incluye el nuevo mensaje tool)
        const threadData = await getConversationThread(conversationId);
        setMessages(threadData.messages);
        setActiveLeafId(threadData.active_leaf_id);
        
        // Marcar como notificado
        await markJobNotified(event.job_id);
        
        // Mostrar panel de terminal
        setTerminalOpen(true);
        
        // IMPORTANTE: Enviar automáticamente al LLM para que procese el resultado
        // Solo si tenemos modelo y API key configurados
        const apiKey = getApiKey();
        if (apiKey && selectedModel && !isLoading && !isStreaming) {
          console.log('[Jobs] Enviando resultado al LLM automáticamente...');
          
          // Enviar al LLM para que procese (el contexto ya incluye el tool result)
          setLoading(true);
          setStreaming(true);
          clearChunk();
          
          // Agregar mensaje temporal del asistente para streaming
          const tempAssistantId = Date.now();
          addMessage({
            id: tempAssistantId,
            conversation_id: conversationId,
            parent_id: threadData.active_leaf_id,
            role: 'assistant',
            content: null,
            tool_calls: null,
            tool_call_id: null,
            model_used: selectedModel.id,
            created_at: new Date().toISOString(),
          });
          
          const advParams = getAdvancedParamsForModel();
          
          // Mensaje especial indicando que continue procesando el resultado del tool
          const continueMessage = "[BACKGROUND_JOB_COMPLETED] The background command has finished and the output has been added to the conversation context. Please analyze the result and provide your response to the user.";
          
          abortRef.current = sendMessageStream(
            {
              provider: selectedModel.provider,
              api_key: apiKey,
              model_id: selectedModel.id,
              conversation_id: conversationId,
              user_message: continueMessage,
              tools: getToolsForAPI(),
              ...advParams,
            },
            {
              onMessage: (chunk) => appendChunk(chunk),
              onToolCall: () => setTerminalOpen(true),
              onDone: async (data) => {
                setStreaming(false);
                setLoading(false);
                abortRef.current = null;
                
                // Recargar para obtener los mensajes reales de la BD
                const finalThread = await getConversationThread(conversationId);
                setMessages(finalThread.messages);
                setActiveLeafId(finalThread.active_leaf_id);
                
                // Actualizar árbol
                const treeData = await getConversationTree(conversationId);
                setFullTree(treeData.nodes);
              },
              onError: (err) => {
                setStreaming(false);
                setLoading(false);
                console.error('[Jobs] Error enviando al LLM:', err);
              },
            }
          );
        } else {
          console.log('[Jobs] No se puede enviar al LLM:', { 
            hasApiKey: !!apiKey, 
            hasModel: !!selectedModel, 
            isLoading, 
            isStreaming 
          });
        }
      } catch (err) {
        console.error('[Jobs] Error procesando job completado:', err);
      }
    };
    
    const unsubscribe = subscribeToJobNotifications(conversationId, {
      onConnected: () => console.log('[Jobs] Conectado al stream de notificaciones'),
      onJobCompleted: handleJobCompleted,
      onError: (err) => console.log('[Jobs] Error en stream:', err),
    });
    
    return () => {
      console.log(`[Jobs] Desuscribiendo de ${conversationId}`);
      unsubscribe();
    };
  }, [conversationId, activeLeafId, setMessages, setActiveLeafId, setTerminalOpen, getApiKey, selectedModel, isLoading, isStreaming, setLoading, setStreaming, clearChunk, addMessage, getAdvancedParamsForModel, appendChunk, setFullTree]);

  const handleSend = async () => {
    if (!input.trim() || isLoading || isStreaming) return;
    
    const apiKey = getApiKey();
    if (!apiKey) {
      setError("No hay API key configurada para el proveedor seleccionado");
      return;
    }
    
    if (!selectedModel) {
      setError("Selecciona un modelo primero");
      return;
    }

    setError(null);
    const userMessage = input.trim();
    setInput("");
    
    // Si textarea tenía altura extra, resetear
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }

    try {
      let currentConversationId = conversationId;
      
      // Si no hay conversación, crear una nueva
      if (!currentConversationId) {
        setLoading(true);
        const newConv = await createConversation({
          title: userMessage.slice(0, 50),
          system_prompt: systemPrompt,
        });
        currentConversationId = newConv.id;
        setConversation(newConv.id);
        
        // Agregar a la lista de conversaciones
        addConversation({
          id: newConv.id,
          title: userMessage.slice(0, 50),
          system_prompt: systemPrompt,
          active_leaf_id: newConv.system_message_id,
          message_count: 1,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        });
        
        // Cargar el thread inicial (con el system message)
        const thread = await getConversationThread(newConv.id);
        setMessages(thread.messages);
        setActiveLeafId(thread.active_leaf_id);
        setLoading(false);
      }

      // Agregar mensaje del usuario temporalmente a la UI
      const tempUserMsg: Message = {
        id: Date.now(),
        conversation_id: currentConversationId,
        parent_id: activeLeafId,
        role: 'user',
        content: userMessage,
        created_at: new Date().toISOString(),
      };
      addMessage(tempUserMsg);

      // Usar streaming
      setStreaming(true);
      clearChunk();
      
      // Agregar mensaje vacío del asistente para mostrar streaming
      const tempAssistantMsg: Message = {
        id: Date.now() + 1,
        conversation_id: currentConversationId,
        parent_id: tempUserMsg.id,
        role: 'assistant',
        content: '',
        created_at: new Date().toISOString(),
      };
      addMessage(tempAssistantMsg);

      const advParams = getAdvancedParamsForModel();
      const abort = sendMessageStream(
        {
          provider: selectedModel.provider,
          api_key: apiKey,
          model_id: selectedModel.id,
          conversation_id: currentConversationId,
          parent_message_id: activeLeafId || undefined,
          user_message: userMessage,
          stream: true,
          tools: getToolsForAPI(),
          ...advParams,
        },
        {
          onMessage: (chunk) => {
            appendChunk(chunk);
          },
          onToolCall: (toolCall) => {
            // Abrir terminal si hay tool calls
            setTerminalOpen(true);
            console.log("Tool call:", toolCall);
            
            // Extraer datos del toolCall con tipos seguros
            const tcId = toolCall.id as string | undefined;
            const tcFunction = toolCall.function as { name?: string; arguments?: string } | undefined;
            const tcFuncName = tcFunction?.name || '';
            const tcFuncArgs = tcFunction?.arguments || '{}';
            
            // Agregar tool call al estado de streaming para visualización en tiempo real
            if (tcId) {
              // Nuevo tool call con ID
              addStreamingToolCall({
                id: tcId,
                type: 'function',
                function: {
                  name: tcFuncName,
                  arguments: tcFuncArgs
                }
              });
            } else if (tcFuncArgs) {
              // Es un delta de argumentos sin ID, actualizar el último
              // Necesitamos acceder al último tool call agregado
              updateStreamingToolCall('__LAST__', tcFuncArgs);
            }
            
            // También mantener actualizado el mensaje del assistant para persistencia
            const assistantMsg = messages.find(m => m.id === tempAssistantMsg.id);
            if (assistantMsg) {
              const existingToolCalls = assistantMsg.tool_calls || [];
              
              // Solo agregar si tiene ID (no es un delta parcial)
              if (tcId) {
                const newToolCall: ToolCall = {
                  id: tcId,
                  type: 'function',
                  function: {
                    name: tcFuncName,
                    arguments: tcFuncArgs
                  }
                };
                updateMessage(tempAssistantMsg.id, {
                  tool_calls: [...existingToolCalls, newToolCall]
                });
              } else if (existingToolCalls.length > 0 && tcFuncArgs) {
                // Es un delta de argumentos, actualizar el último tool_call
                const lastTC = existingToolCalls[existingToolCalls.length - 1];
                const updatedTC = {
                  ...lastTC,
                  function: {
                    ...lastTC.function,
                    arguments: lastTC.function.arguments + tcFuncArgs
                  }
                };
                updateMessage(tempAssistantMsg.id, {
                  tool_calls: [...existingToolCalls.slice(0, -1), updatedTC]
                });
              }
            }
          },
          onToolExecuting: (data) => {
            // Tool está siendo ejecutada en el backend
            console.log("🔧 Ejecutando tool:", data.function_name);
          },
          onToolResult: (data) => {
            // Resultado de la tool recibido - agregar al store para tiempo real
            console.log("✅ Tool result:", data.result?.substring(0, 100));
            
            // Agregar mensaje tool al store para que TerminalPanel lo muestre inmediatamente
            if (data.tool_message_id && data.result) {
              const toolMessage: Message = {
                id: data.tool_message_id,
                conversation_id: currentConversationId!,
                parent_id: null, // Se actualizará al recargar
                role: 'tool',
                content: data.result,
                tool_call_id: data.tool_call_id,
                created_at: new Date().toISOString(),
              };
              addMessage(toolMessage);
            }
          },
          onDone: async (data) => {
            setStreaming(false);
            clearChunk();
            clearStreamingToolCalls(); // Limpiar tool calls de streaming
            
            // Recargar el thread real desde el backend
            const thread = await getConversationThread(currentConversationId!);
            setMessages(thread.messages);
            setActiveLeafId(thread.active_leaf_id);
            
            // Actualizar árbol
            const tree = await getConversationTree(currentConversationId!);
            setFullTree(tree.nodes);
            
            // Actualizar conversación en la lista
            updateConversation(currentConversationId!, {
              updated_at: new Date().toISOString(),
              message_count: thread.messages.length,
            });
            
            // Crear checkpoint en el sandbox después de la respuesta
            if (thread.active_leaf_id && sessions[currentConversationId!]?.initialized) {
              try {
                const checkpoint = await createCheckpoint(
                  currentConversationId!,
                  thread.active_leaf_id,
                  activeLeafId
                );
                updateSessionLeaf(currentConversationId!, thread.active_leaf_id);
                console.log(`[Terminal] Checkpoint creado: ${checkpoint.tag}`);
              } catch (err) {
                console.log('[Terminal] Error creando checkpoint:', err);
              }
            }
          },
          onError: (err) => {
            setStreaming(false);
            clearChunk();
            
            // Detectar si es error de parámetros no soportados
            if (isUnsupportedParamError(err) && selectedModel) {
              setParamErrorModel(selectedModel.id);
            }
            
            // Parsear mensaje de error para hacerlo más legible
            const errorMsg = parseErrorMessage(err);
            setError(errorMsg);
            // Remover mensajes temporales
            setMessages(messages);
          },
        }
      );
      
      abortRef.current = abort;

    } catch (err) {
      setLoading(false);
      setStreaming(false);
      const errorMsg = err instanceof Error ? err.message : "Error desconocido";
      setError(parseErrorMessage(errorMsg));
    }
  };

  const handleStop = () => {
    if (abortRef.current) {
      abortRef.current();
      abortRef.current = null;
    }
    setStreaming(false);
    clearChunk();
  };

  // Handler para regenerar respuesta del asistente
  const handleRegenerateMessage = async (assistantMessageId: number) => {
    const apiKey = getApiKey();
    if (!apiKey || !selectedModel || !conversationId) return;

    // Encontrar el mensaje assistant para obtener su parent (el mensaje user)
    const assistantMessage = messages.find(m => m.id === assistantMessageId);
    if (!assistantMessage || assistantMessage.role !== 'assistant') return;

    // Encontrar el mensaje user padre
    const userMessage = messages.find(m => m.id === assistantMessage.parent_id);
    if (!userMessage || !userMessage.content) return;

    setError(null);
    
    try {
      // Enviar el mismo mensaje user de nuevo (crea nueva branch en assistant)
      setStreaming(true);
      clearChunk();
      
      // Agregar mensaje vacío del asistente para streaming
      const tempAssistantMsg: Message = {
        id: Date.now(),
        conversation_id: conversationId,
        parent_id: userMessage.id, // Mismo parent = nueva rama de respuesta
        role: 'assistant',
        content: '',
        created_at: new Date().toISOString(),
      };
      addMessage(tempAssistantMsg);

      const advParams = getAdvancedParamsForModel();
      const abort = sendMessageStream(
        {
          provider: selectedModel.provider,
          api_key: apiKey,
          model_id: selectedModel.id,
          conversation_id: conversationId,
          parent_message_id: userMessage.id,
          user_message: userMessage.content,
          regenerate: true,  // No crear nuevo mensaje de usuario
          stream: true,
          tools: getToolsForAPI(),
          ...advParams,
        },
        {
          onMessage: (chunk) => {
            appendChunk(chunk);
          },
          onToolCall: (toolCall) => {
            setTerminalOpen(true);
            console.log("Tool call:", toolCall);
            
            const tcId = toolCall.id as string | undefined;
            const tcFunction = toolCall.function as { name?: string; arguments?: string } | undefined;
            const tcFuncName = tcFunction?.name || '';
            const tcFuncArgs = tcFunction?.arguments || '{}';
            
            if (tcId) {
              addStreamingToolCall({
                id: tcId,
                type: 'function',
                function: { name: tcFuncName, arguments: tcFuncArgs }
              });
            } else if (tcFuncArgs) {
              updateStreamingToolCall('__LAST__', tcFuncArgs);
            }
          },
          onToolExecuting: (data) => {
            console.log("🔧 Ejecutando tool:", data.function_name);
          },
          onToolResult: (data) => {
            console.log("✅ Tool result:", data.result?.substring(0, 100));
          },
          onDone: async (data) => {
            setStreaming(false);
            clearChunk();
            clearStreamingToolCalls();
            
            // Recargar el thread real desde el backend
            const thread = await getConversationThread(conversationId!);
            setMessages(thread.messages);
            setActiveLeafId(thread.active_leaf_id);
            
            // Actualizar árbol
            const tree = await getConversationTree(conversationId!);
            setFullTree(tree.nodes);
            
            // Actualizar conversación en la lista
            updateConversation(conversationId!, {
              updated_at: new Date().toISOString(),
              message_count: thread.messages.length,
            });
            
            // Crear checkpoint en el sandbox después de regenerar
            if (thread.active_leaf_id && sessions[conversationId!]?.initialized) {
              try {
                const checkpoint = await createCheckpoint(
                  conversationId!,
                  thread.active_leaf_id,
                  userMessage.id  // Parent es el mensaje de usuario
                );
                updateSessionLeaf(conversationId!, thread.active_leaf_id);
                console.log(`[Terminal] Checkpoint (regenerate) creado: ${checkpoint.tag}`);
              } catch (err) {
                console.log('[Terminal] Error creando checkpoint:', err);
              }
            }
          },
          onError: (err) => {
            setStreaming(false);
            clearChunk();
            const errorMsg = parseErrorMessage(err);
            setError(errorMsg);
            // Remover mensaje temporal
            setMessages(messages);
          },
        }
      );
      
      abortRef.current = abort;

    } catch (err) {
      setStreaming(false);
      const errorMsg = err instanceof Error ? err.message : "Error desconocido";
      setError(parseErrorMessage(errorMsg));
    }
  };

  // Handler para editar un mensaje del usuario (crea una nueva branch)
  const handleEditMessage = async (messageId: number, newContent: string) => {
    const apiKey = getApiKey();
    if (!apiKey || !selectedModel || !conversationId) return;

    // Buscar el mensaje original para obtener su parent_id
    const originalMessage = messages.find(m => m.id === messageId);
    if (!originalMessage) return;

    setError(null);
    
    try {
      // Agregar nuevo mensaje del usuario (branch)
      const tempUserMsg: Message = {
        id: Date.now(),
        conversation_id: conversationId,
        parent_id: originalMessage.parent_id, // Mismo parent = nueva branch
        role: 'user',
        content: newContent,
        created_at: new Date().toISOString(),
      };
      
      // Reemplazar mensajes desde este punto
      const parentIndex = messages.findIndex(m => m.id === originalMessage.parent_id);
      const messagesBeforeBranch = messages.slice(0, parentIndex + 1);
      setMessages([...messagesBeforeBranch, tempUserMsg]);

      setStreaming(true);
      clearChunk();
      
      // Agregar mensaje vacío del asistente para streaming
      const tempAssistantMsg: Message = {
        id: Date.now() + 1,
        conversation_id: conversationId,
        parent_id: tempUserMsg.id,
        role: 'assistant',
        content: '',
        created_at: new Date().toISOString(),
      };
      addMessage(tempAssistantMsg);

      const abort = sendMessageStream(
        {
          provider: selectedModel.provider,
          api_key: apiKey,
          model_id: selectedModel.id,
          conversation_id: conversationId,
          parent_message_id: originalMessage.parent_id || undefined,
          user_message: newContent,
          stream: true,
          tools: getToolsForAPI(),
        },
        {
          onMessage: (chunk) => {
            appendChunk(chunk);
          },
          onToolCall: (toolCall) => {
            setTerminalOpen(true);
            console.log("Tool call:", toolCall);
            
            const tcId = toolCall.id as string | undefined;
            const tcFunction = toolCall.function as { name?: string; arguments?: string } | undefined;
            const tcFuncName = tcFunction?.name || '';
            const tcFuncArgs = tcFunction?.arguments || '{}';
            
            if (tcId) {
              addStreamingToolCall({
                id: tcId,
                type: 'function',
                function: { name: tcFuncName, arguments: tcFuncArgs }
              });
            } else if (tcFuncArgs) {
              updateStreamingToolCall('__LAST__', tcFuncArgs);
            }
          },
          onToolExecuting: (data) => {
            console.log("🔧 Ejecutando tool:", data.function_name);
          },
          onToolResult: (data) => {
            console.log("✅ Tool result:", data.result?.substring(0, 100));
          },
          onDone: async () => {
            setStreaming(false);
            clearChunk();
            clearStreamingToolCalls();
            
            const thread = await getConversationThread(conversationId);
            setMessages(thread.messages);
            setActiveLeafId(thread.active_leaf_id);
            
            const tree = await getConversationTree(conversationId);
            setFullTree(tree.nodes);
            
            updateConversation(conversationId, {
              updated_at: new Date().toISOString(),
              message_count: thread.messages.length,
            });
            
            // Crear checkpoint en el sandbox después de editar
            if (thread.active_leaf_id && sessions[conversationId]?.initialized) {
              try {
                const checkpoint = await createCheckpoint(
                  conversationId,
                  thread.active_leaf_id,
                  originalMessage.parent_id  // El nuevo parent después de la edición
                );
                updateSessionLeaf(conversationId, thread.active_leaf_id);
                console.log(`[Terminal] Checkpoint (edit) creado: ${checkpoint.tag}`);
              } catch (err) {
                console.log('[Terminal] Error creando checkpoint:', err);
              }
            }
          },
          onError: (err) => {
            setStreaming(false);
            clearChunk();
            setError(err);
          },
        }
      );
      
      abortRef.current = abort;
    } catch (err) {
      setStreaming(false);
      setError(err instanceof Error ? err.message : "Error al editar mensaje");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Filtrar solo mensajes no-system para mostrar
  const visibleMessages = messages.filter(m => m.role !== 'system');

  // Encontrar el mensaje que está en streaming (último assistant sin contenido)
  const streamingMessage = isStreaming 
    ? [...visibleMessages].reverse().find(m => m.role === 'assistant' && !m.content)
    : null;

  return (
    <div className="h-full flex flex-col bg-background">
      {/* Área de mensajes */}
      <div className="flex-1 overflow-y-auto px-4" ref={scrollRef}>
        <div className="max-w-3xl mx-auto py-6 space-y-1">
          {visibleMessages.length === 0 && !isLoading && (
            <div className="flex flex-col items-center justify-center h-[60vh] text-center">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center mb-6">
                <Sparkles className="h-8 w-8 text-primary" />
              </div>
              <h2 className="text-2xl font-semibold mb-2">
                ¿En qué puedo ayudarte?
              </h2>
              <p className="text-muted-foreground max-w-md">
                Soy tu asistente de ciberseguridad. Puedo ayudarte con escaneos de red, 
                análisis de vulnerabilidades, scripts y mucho más.
              </p>
            </div>
          )}
          
          {visibleMessages.map((message, index) => {
            // Verificar si el siguiente mensaje es un tool response para este mensaje
            const nextMessage = visibleMessages[index + 1];
            const toolResponseContent = nextMessage?.role === 'tool' ? (nextMessage.content || undefined) : undefined;
            
            return (
              <MessageBubble 
                key={message.id} 
                message={message}
                isStreaming={streamingMessage?.id === message.id}
                streamContent={streamingMessage?.id === message.id ? currentChunk : undefined}
                toolResponseContent={toolResponseContent}
                onEdit={handleEditMessage}
                onRegenerate={handleRegenerateMessage}
              />
            );
          })}
          
          {isLoading && visibleMessages.length === 0 && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          )}
        </div>
      </div>

      {/* Barra de error mejorada */}
      {error && (
        <div className="px-4 py-3 bg-destructive/10 border-t border-destructive/20">
          <div className="max-w-3xl mx-auto">
            <div className="flex items-start gap-3 text-sm">
              <AlertCircle className="h-5 w-5 shrink-0 text-destructive mt-0.5" />
              <div className="flex-1 space-y-2">
                <p className="text-destructive font-medium">{error}</p>
                <p className="text-muted-foreground text-xs">
                  Cambia de modelo y pulsa &quot;Regenerar&quot; en el mensaje del asistente para reintentar.
                </p>
              </div>
              <Button 
                variant="ghost" 
                size="sm" 
                className="shrink-0 h-7 text-xs text-muted-foreground hover:text-foreground"
                onClick={() => setError(null)}
              >
                Cerrar
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Diálogo de parámetros no soportados */}
      {paramErrorModel && (
        <div className="px-4 py-3 bg-amber-500/10 border-t border-amber-500/30">
          <div className="max-w-3xl mx-auto">
            <div className="flex items-center gap-3 text-sm">
              <span className="text-lg">⚠️</span>
              <div className="flex-1">
                <p className="text-amber-600 dark:text-amber-400 font-medium">
                  Este modelo no soporta parámetros avanzados personalizados
                </p>
                <p className="text-muted-foreground text-xs">
                  ¿Usar valores por defecto del proveedor para este modelo?
                </p>
              </div>
              <div className="flex gap-2">
                <Button 
                  variant="outline" 
                  size="sm" 
                  className="h-7 text-xs"
                  onClick={() => {
                    addModelToDefaults(paramErrorModel);
                    setParamErrorModel(null);
                    setError(null);
                  }}
                >
                  Sí, siempre
                </Button>
                <Button 
                  variant="ghost" 
                  size="sm" 
                  className="h-7 text-xs text-muted-foreground"
                  onClick={() => setParamErrorModel(null)}
                >
                  Solo esta vez
                </Button>
                <Button 
                  variant="ghost" 
                  size="icon" 
                  className="h-7 w-7 text-muted-foreground"
                  onClick={() => setParamErrorModel(null)}
                >
                  ×
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Input area */}
      <div className="border-t bg-background/80 backdrop-blur-sm p-4">
        <div className="max-w-3xl mx-auto">
          <div className="relative flex items-end gap-2">
            <div className="flex-1 relative">
              <Textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={selectedModel 
                  ? `Escribe tu mensaje... (${selectedModel.name})`
                  : "Selecciona un modelo para empezar"
                }
                disabled={isLoading || !selectedModel}
                className={cn(
                  "min-h-[52px] max-h-[200px] resize-none pr-12",
                  "rounded-2xl border-2 focus-visible:ring-1",
                  "transition-all duration-200"
                )}
                rows={1}
              />
            </div>
            
            {isStreaming ? (
              <Button
                onClick={handleStop}
                size="icon"
                variant="destructive"
                className="h-[52px] w-[52px] rounded-2xl shrink-0"
              >
                <StopCircle className="h-5 w-5" />
              </Button>
            ) : (
              <Button
                onClick={handleSend}
                disabled={!input.trim() || isLoading || !selectedModel}
                size="icon"
                className="h-[52px] w-[52px] rounded-2xl shrink-0"
              >
                {isLoading ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                  <Send className="h-5 w-5" />
                )}
              </Button>
            )}
          </div>
          
          <p className="text-xs text-muted-foreground text-center mt-2">
            Presiona Enter para enviar, Shift+Enter para nueva línea
          </p>
        </div>
      </div>
    </div>
  );
}
