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
}): Promise<KeysValidationResponse> {
  const response = await fetch(`${getBaseUrl()}/health/keys`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(keys),
  });
  return handleResponse<KeysValidationResponse>(response);
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
  onDone: (data: { 
    conversation_id: string; 
    user_message_id: number; 
    assistant_message_id: number;
    model_used: string;
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
              
              if (data.chunk !== undefined) {
                callbacks.onMessage(data.chunk);
              } else if (data.tool_call) {
                callbacks.onToolCall(data.tool_call);
              } else if (data.conversation_id && data.assistant_message_id) {
                callbacks.onDone(data);
              } else if (data.type === 'error' || data.error) {
                // Manejar errores del backend (type: error, message: ...)
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
