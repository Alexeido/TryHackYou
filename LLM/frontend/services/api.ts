/**
 * API Service - Comunicación con el backend
 * Usando fetch() nativo para simplicidad
 */

import { 
  useConfigStore, 
  Message, 
  Conversation, 
  TreeNode,
  Provider 
} from '@/store/useStore';

// ============================================
// CONFIGURACIÓN
// ============================================

const getBaseUrl = () => useConfigStore.getState().backendUrl;

interface ApiError {
  detail: string;
  error_code?: string;
}

class ApiException extends Error {
  constructor(
    message: string, 
    public status: number, 
    public errorCode?: string
  ) {
    super(message);
    this.name = 'ApiException';
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorMessage = `Error ${response.status}`;
    try {
      const errorData: ApiError = await response.json();
      errorMessage = errorData.detail || errorMessage;
      throw new ApiException(errorMessage, response.status, errorData.error_code);
    } catch (e) {
      if (e instanceof ApiException) throw e;
      throw new ApiException(errorMessage, response.status);
    }
  }
  return response.json();
}

// ============================================
// HEALTH
// ============================================

export interface HealthResponse {
  status: string;
  version: string;
  database: string;
  timestamp: string;
}

export interface KeyValidationResult {
  valid: boolean;
  error: string | null;
  models_count?: number;
}

export interface KeysValidationResponse {
  openai?: KeyValidationResult;
  google?: KeyValidationResult;
  anthropic?: KeyValidationResult;
  deepseek?: KeyValidationResult;
  openrouter?: KeyValidationResult;
  ollama?: KeyValidationResult;
}

export async function checkHealth(): Promise<HealthResponse> {
  const response = await fetch(`${getBaseUrl()}/health`);
  return handleResponse<HealthResponse>(response);
}

export async function validateApiKeys(keys: {
  openai_key?: string;
  gemini_key?: string;
  anthropic_key?: string;
  deepseek_key?: string;
  openrouter_key?: string;
  ollama_url?: string;
}): Promise<KeysValidationResponse> {
  const response = await fetch(`${getBaseUrl()}/health/keys`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(keys),
  });
  return handleResponse<KeysValidationResponse>(response);
}

// ============================================
// OLLAMA
// ============================================

export interface OllamaModel {
  name: string;
  model: string;
  size: number;
  parameter_size?: string;
  quantization_level?: string;
  family?: string;
}

export interface OllamaModelsResponse {
  connected: boolean;
  models: OllamaModel[];
  error?: string;
}

export async function getOllamaModels(url: string): Promise<OllamaModelsResponse> {
  const response = await fetch(`${getBaseUrl()}/ollama/models`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  });
  return handleResponse<OllamaModelsResponse>(response);
}

// ============================================
// CONVERSATIONS
// ============================================

export interface CreateConversationRequest {
  title?: string;
  system_prompt?: string;
}

export interface CreateConversationResponse {
  id: string;
  system_message_id: number;
  title: string;
}

export interface ThreadResponse {
  conversation_id: string;
  active_leaf_id: number | null;
  messages: Message[];
}

export interface TreeResponse {
  conversation_id: string;
  active_leaf_id: number | null;
  nodes: TreeNode[];
}

export async function createConversation(
  data: CreateConversationRequest
): Promise<CreateConversationResponse> {
  const response = await fetch(`${getBaseUrl()}/conversations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return handleResponse<CreateConversationResponse>(response);
}

export async function getConversations(): Promise<Conversation[]> {
  const response = await fetch(`${getBaseUrl()}/conversations`);
  const data = await handleResponse<{ total: number; conversations: Conversation[] }>(response);
  return data.conversations || [];
}

export async function getConversation(id: string): Promise<Conversation> {
  const response = await fetch(`${getBaseUrl()}/conversations/${id}`);
  return handleResponse<Conversation>(response);
}

export async function deleteConversation(id: string): Promise<void> {
  const response = await fetch(`${getBaseUrl()}/conversations/${id}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    throw new ApiException('Failed to delete conversation', response.status);
  }
}

export async function toggleConversationPin(id: string): Promise<{ pinned: boolean }> {
  const response = await fetch(`${getBaseUrl()}/conversations/${id}/pin`, {
    method: 'POST',
  });
  return handleResponse<{ pinned: boolean }>(response);
}

export async function renameConversation(id: string, title: string): Promise<{ title: string }> {
  const response = await fetch(`${getBaseUrl()}/conversations/${id}/title`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  });
  return handleResponse<{ title: string }>(response);
}

export async function getConversationThread(id: string): Promise<ThreadResponse> {
  const response = await fetch(`${getBaseUrl()}/conversations/${id}/thread`);
  return handleResponse<ThreadResponse>(response);
}

export async function getConversationTree(id: string): Promise<TreeResponse> {
  const response = await fetch(`${getBaseUrl()}/conversations/${id}/tree`);
  return handleResponse<TreeResponse>(response);
}

export async function setActiveLeaf(
  conversationId: string, 
  leafId: number
): Promise<{ active_leaf_id: number }> {
  const response = await fetch(
    `${getBaseUrl()}/conversations/${conversationId}/active-leaf`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ leaf_id: leafId }),
    }
  );
  return handleResponse(response);
}

// ============================================
// CHAT
// ============================================

export interface ChatRequest {
  provider: Provider;
  api_key: string;
  model_id: string;
  conversation_id?: string;
  parent_message_id?: number;
  user_message: string;
  regenerate?: boolean;  // Si true, no crea nuevo mensaje de usuario
  // Parámetros avanzados opcionales
  temperature?: number | null;
  top_p?: number | null;
  max_tokens?: number | null;
  tools?: Record<string, unknown>[];
  stream?: boolean;
  system_prompt?: string;
}

export interface ChatResponse {
  conversation_id: string;
  user_message_id: number;
  assistant_message_id: number;
  content: string | null;
  tool_calls: Record<string, unknown>[] | null;
  finish_reason: string;
  model_used: string;
}

export async function sendMessage(request: ChatRequest): Promise<ChatResponse> {
  const response = await fetch(`${getBaseUrl()}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...request, stream: false }),
  });
  return handleResponse<ChatResponse>(response);
}

// ============================================
// STREAMING CHAT
// ============================================

export interface StreamCallbacks {
  onMessage: (chunk: string) => void;
  onToolCall: (toolCall: Record<string, unknown>) => void;
  onToolExecuting?: (data: { tool_call_id: string; function_name: string }) => void;
  onToolResult?: (data: { tool_call_id: string; result: string; tool_message_id: number }) => void;
  onDone: (data: { 
    conversation_id: string; 
    user_message_id: number; 
    assistant_message_id: number;
    model_used: string;
    had_tool_calls?: boolean;
  }) => void;
  onError: (error: string) => void;
}

export function sendMessageStream(
  request: ChatRequest,
  callbacks: StreamCallbacks
): () => void {
  const controller = new AbortController();
  
  const body = JSON.stringify({ ...request, stream: true });
  
  fetch(`${getBaseUrl()}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body,
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        callbacks.onError(errorData.detail || `Error ${response.status}`);
        return;
      }
      
      const reader = response.body?.getReader();
      if (!reader) {
        callbacks.onError('No response body');
        return;
      }
      
      const decoder = new TextDecoder();
      let buffer = '';
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            // Guardamos el tipo de evento para el siguiente data
            continue;
          }
          
          if (line.startsWith('data: ')) {
            const jsonStr = line.slice(6);
            if (!jsonStr.trim()) continue;
            
            try {
              const data = JSON.parse(jsonStr);
              
              // Contenido de texto
              if (data.type === 'content' && data.chunk !== undefined) {
                callbacks.onMessage(data.chunk);
              } 
              // Tool call streaming
              else if (data.type === 'tool_call' && data.tool_call) {
                callbacks.onToolCall(data.tool_call);
              }
              // Tool ejecutándose (nuevo)
              else if (data.type === 'tool_executing') {
                callbacks.onToolExecuting?.({
                  tool_call_id: data.tool_call_id,
                  function_name: data.function_name
                });
              }
              // Resultado de tool (nuevo)
              else if (data.type === 'tool_result') {
                callbacks.onToolResult?.({
                  tool_call_id: data.tool_call_id,
                  result: data.result,
                  tool_message_id: data.tool_message_id
                });
              }
              // Finalización
              else if (data.type === 'done' || (data.conversation_id && data.assistant_message_id && !data.type)) {
                callbacks.onDone(data);
              } 
              // Legacy: contenido sin type
              else if (data.chunk !== undefined && !data.type) {
                callbacks.onMessage(data.chunk);
              }
              // Legacy: tool_call sin type
              else if (data.tool_call && !data.type) {
                callbacks.onToolCall(data.tool_call);
              }
              // Errores
              else if (data.type === 'error' || data.error) {
                const errorMsg = data.message || data.error || 'Error desconocido del servidor';
                callbacks.onError(errorMsg);
              }
            } catch {
              // Ignorar errores de parse en chunks parciales
            }
          }
        }
      }
    })
    .catch((error) => {
      if (error.name !== 'AbortError') {
        callbacks.onError(error.message);
      }
    });
  
  // Retornar función para cancelar
  return () => controller.abort();
}

// ============================================
// MESSAGES
// ============================================

export interface MessageEditRequest {
  content: string;
  create_branch?: boolean;
}

export interface MessageEditResponse {
  message_id: number;
  conversation_id: string;
  is_new_branch: boolean;
  parent_id: number | null;
}

export async function getMessage(id: number): Promise<Message> {
  const response = await fetch(`${getBaseUrl()}/messages/${id}`);
  return handleResponse<Message>(response);
}

export async function editMessage(
  id: number, 
  data: MessageEditRequest
): Promise<MessageEditResponse> {
  const response = await fetch(`${getBaseUrl()}/messages/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return handleResponse<MessageEditResponse>(response);
}

export async function deleteMessage(id: number): Promise<void> {
  const response = await fetch(`${getBaseUrl()}/messages/${id}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    throw new ApiException('Failed to delete message', response.status);
  }
}

// ============================================
// MODELS DISCOVERY
// ============================================

export type ModelSorting = 'default' | 'ranking' | 'context';

export interface DiscoveredModel {
  id: string;
  name: string;
  provider: string;
  elo_score: number;
  context_window?: number;
  pricing_input?: number;
  pricing_output?: number;
}

export interface ModelsDiscoveryRequest {
  openai_key?: string;
  gemini_key?: string;
  anthropic_key?: string;
  deepseek_key?: string;
  openrouter_key?: string;
  sorting?: ModelSorting;
  group?: boolean;
  snapshots?: boolean;
  openrouter_free?: boolean;
}

export interface ModelsDiscoveryResponse {
  total: number;
  models: DiscoveredModel[];
}

export async function discoverModels(
  request: ModelsDiscoveryRequest
): Promise<ModelsDiscoveryResponse> {
  const response = await fetch(`${getBaseUrl()}/models/discover`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  return handleResponse<ModelsDiscoveryResponse>(response);
}

// ============================================
// TOOL RESPONSE
// ============================================

export interface ToolResponseRequest {
  conversation_id: string;
  tool_call_id: string;
  tool_name: string;
  tool_output: string;
  parent_message_id: number;
  provider: Provider;
  api_key: string;
  model_id: string;
  stream?: boolean;
}

export async function sendToolResponse(
  request: ToolResponseRequest
): Promise<ChatResponse> {
  const response = await fetch(`${getBaseUrl()}/chat/tool-response`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  return handleResponse<ChatResponse>(response);
}

// ============================================
// BACKGROUND JOBS
// ============================================

export interface PendingJob {
  id: number;
  job_id: string;
  conversation_id: string;
  leaf_id: number;
  command: string;
  status: string;
  result?: string;
  created_at: string;
  completed_at?: string;
  notified: number;
}

export interface JobCompletedEvent {
  job_id: string;
  result: string;
  leaf_id: number;
}

/**
 * Obtiene jobs pendientes (running) de una conversación
 */
export async function getPendingJobs(conversationId: string): Promise<PendingJob[]> {
  const response = await fetch(`${getBaseUrl()}/jobs/${conversationId}/pending`);
  return handleResponse<PendingJob[]>(response);
}

/**
 * Obtiene jobs completados no notificados
 */
export async function getCompletedJobs(conversationId: string, leafId?: number): Promise<PendingJob[]> {
  let url = `${getBaseUrl()}/jobs/${conversationId}/completed`;
  if (leafId) {
    url += `?leaf_id=${leafId}`;
  }
  const response = await fetch(url);
  return handleResponse<PendingJob[]>(response);
}

/**
 * Marca un job como notificado
 */
export async function markJobNotified(jobId: string): Promise<void> {
  const response = await fetch(`${getBaseUrl()}/jobs/${jobId}/mark-notified`, {
    method: 'POST',
  });
  if (!response.ok) {
    throw new Error('Failed to mark job as notified');
  }
}

/**
 * Se conecta al stream SSE de notificaciones de jobs completados.
 * Retorna una función para cerrar la conexión.
 */
export function subscribeToJobNotifications(
  conversationId: string,
  callbacks: {
    onConnected?: () => void;
    onJobCompleted: (event: JobCompletedEvent) => void;
    onError?: (error: Error) => void;
  }
): () => void {
  const eventSource = new EventSource(`${getBaseUrl()}/jobs/${conversationId}/stream`);
  
  eventSource.addEventListener('connected', () => {
    callbacks.onConnected?.();
  });
  
  eventSource.addEventListener('job_completed', (e) => {
    try {
      const data = JSON.parse(e.data) as JobCompletedEvent;
      callbacks.onJobCompleted(data);
    } catch (err) {
      console.error('[Jobs] Error parsing job_completed event:', err);
    }
  });
  
  eventSource.addEventListener('heartbeat', () => {
    // Heartbeat recibido, conexión activa
  });
  
  eventSource.onerror = (e) => {
    console.error('[Jobs] EventSource error:', e);
    callbacks.onError?.(new Error('Job notification stream error'));
  };
  
  // Retornar función para cerrar
  return () => {
    eventSource.close();
  };
}
