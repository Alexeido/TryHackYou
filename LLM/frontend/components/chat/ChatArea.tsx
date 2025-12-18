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
  Message 
} from "@/store/useStore";
import { 
  sendMessage, 
  sendMessageStream, 
  createConversation,
  getConversationThread,
  getConversationTree 
} from "@/services/api";
import { 
  Send, 
  Loader2, 
  StopCircle,
  Sparkles,
  AlertCircle
} from "lucide-react";
import { cn } from "@/lib/utils";

export function ChatArea() {
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<(() => void) | null>(null);
  
  const { 
    conversationId, 
    messages, 
    isLoading, 
    isStreaming,
    currentChunk,
    setConversation,
    setMessages,
    addMessage,
    setLoading,
    setStreaming,
    appendChunk,
    clearChunk,
    setActiveLeafId,
    setFullTree,
    activeLeafId
  } = useChatStore();
  
  const { apiKeys, systemPrompt, backendUrl } = useConfigStore();
  const { selectedModel } = useModelsStore();
  const { setTerminalOpen } = useUIStore();
  const { addConversation, updateConversation } = useConversationsStore();

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

      const abort = sendMessageStream(
        {
          provider: selectedModel.provider,
          api_key: apiKey,
          model_id: selectedModel.id,
          conversation_id: currentConversationId,
          parent_message_id: activeLeafId || undefined,
          user_message: userMessage,
          stream: true,
        },
        {
          onMessage: (chunk) => {
            appendChunk(chunk);
          },
          onToolCall: (toolCall) => {
            // Abrir terminal si hay tool calls
            setTerminalOpen(true);
            console.log("Tool call:", toolCall);
          },
          onDone: async (data) => {
            setStreaming(false);
            clearChunk();
            
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
          },
          onError: (err) => {
            setStreaming(false);
            clearChunk();
            setError(err);
            // Remover mensajes temporales
            setMessages(messages);
          },
        }
      );
      
      abortRef.current = abort;

    } catch (err) {
      setLoading(false);
      setStreaming(false);
      setError(err instanceof Error ? err.message : "Error desconocido");
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
        },
        {
          onMessage: (chunk) => {
            appendChunk(chunk);
          },
          onToolCall: (toolCall) => {
            setTerminalOpen(true);
            console.log("Tool call:", toolCall);
          },
          onDone: async () => {
            setStreaming(false);
            clearChunk();
            
            const thread = await getConversationThread(conversationId);
            setMessages(thread.messages);
            setActiveLeafId(thread.active_leaf_id);
            
            const tree = await getConversationTree(conversationId);
            setFullTree(tree.nodes);
            
            updateConversation(conversationId, {
              updated_at: new Date().toISOString(),
              message_count: thread.messages.length,
            });
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

  // Encontrar el mensaje que está en streaming (último assistant)
  const streamingMessage = isStreaming 
    ? visibleMessages.find(m => m.role === 'assistant' && !m.content)
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
          
          {visibleMessages.map((message) => (
            <MessageBubble 
              key={message.id} 
              message={message}
              isStreaming={streamingMessage?.id === message.id}
              streamContent={streamingMessage?.id === message.id ? currentChunk : undefined}
              onEdit={handleEditMessage}
            />
          ))}
          
          {isLoading && visibleMessages.length === 0 && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          )}
        </div>
      </div>

      {/* Barra de error */}
      {error && (
        <div className="px-4 py-2 bg-destructive/10 border-t border-destructive/20">
          <div className="max-w-3xl mx-auto flex items-center gap-2 text-sm text-destructive">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
            <Button 
              variant="ghost" 
              size="sm" 
              className="ml-auto h-6 text-xs"
              onClick={() => setError(null)}
            >
              Cerrar
            </Button>
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
