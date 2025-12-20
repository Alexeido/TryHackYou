import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// ============================================
// TIPOS
// ============================================

export type Provider = 'openai' | 'google' | 'deepseek' | 'openrouter' | 'anthropic';

export interface ApiKeys {
  openai: string;
  google: string;
  deepseek: string;
  openrouter: string;
  anthropic: string;
}

export interface KeyValidationStatus {
  valid: boolean;
  error: string | null;
  checking: boolean;
}

export interface Message {
  id: number;
  conversation_id: string;
  parent_id: number | null;
  role: 'system' | 'user' | 'assistant' | 'tool';
  content: string | null;
  tool_calls?: ToolCall[] | null;
  tool_call_id?: string | null;
  model_used?: string | null;
  created_at: string;
  children_count?: number;
}

export interface ToolCall {
  id: string;
  type: 'function';
  function: {
    name: string;
    arguments: string;
  };
}

export interface TreeNode {
  id: number;
  parent_id: number | null;
  role: string;
  content_preview?: string;
  children_count: number;
  children?: TreeNode[];
}

export interface Conversation {
  id: string;
  title: string;
  system_prompt?: string;
  active_leaf_id: number | null;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface Model {
  id: string;
  name: string;
  provider: Provider;
  elo_score: number;
  context_window?: number;
  pricing_input?: number;
  pricing_output?: number;
  isFavorite?: boolean;
}

// ============================================
// CONFIG STORE - API Keys, Theme, System Prompt
// ============================================

interface ConfigState {
  // API Keys
  apiKeys: ApiKeys;
  keyValidation: Record<Provider, KeyValidationStatus>;
  setApiKey: (provider: Provider, key: string) => void;
  setKeyValidation: (provider: Provider, status: KeyValidationStatus) => void;
  
  // Theme
  theme: 'light' | 'dark' | 'system';
  setTheme: (theme: 'light' | 'dark' | 'system') => void;
  
  // System Prompt
  systemPrompt: string;
  setSystemPrompt: (prompt: string) => void;
  
  // Backend URL
  backendUrl: string;
  setBackendUrl: (url: string) => void;
}

export const useConfigStore = create<ConfigState>()(
  persist(
    (set) => ({
      apiKeys: {
        openai: '',
        google: '',
        deepseek: '',
        openrouter: '',
        anthropic: '',
      },
      
      keyValidation: {
        openai: { valid: false, error: null, checking: false },
        google: { valid: false, error: null, checking: false },
        deepseek: { valid: false, error: null, checking: false },
        openrouter: { valid: false, error: null, checking: false },
        anthropic: { valid: false, error: null, checking: false },
      },
      
      theme: 'dark',
      systemPrompt: "Eres un experto en Ciberseguridad ofensiva y defensiva. Ayuda al usuario con escaneos, análisis de logs y scripts de pentesting ético. Responde siempre en español.",
      backendUrl: 'http://localhost:4000',
      
      setApiKey: (provider, key) => set((state) => ({
        apiKeys: { ...state.apiKeys, [provider]: key },
        keyValidation: { 
          ...state.keyValidation, 
          [provider]: { valid: false, error: null, checking: false } 
        }
      })),
      
      setKeyValidation: (provider, status) => set((state) => ({
        keyValidation: { ...state.keyValidation, [provider]: status }
      })),
      
      setTheme: (theme) => set({ theme }),
      setSystemPrompt: (prompt) => set({ systemPrompt: prompt }),
      setBackendUrl: (url) => set({ backendUrl: url }),
    }),
    {
      name: 'cerebro-config',
      partialize: (state) => ({
        apiKeys: state.apiKeys,
        theme: state.theme,
        systemPrompt: state.systemPrompt,
        backendUrl: state.backendUrl,
      }),
    }
  )
);

// ============================================
// CHAT STORE - Messages, Streaming, Tree
// ============================================

interface ChatState {
  // Conversación actual
  conversationId: string | null;
  messages: Message[];
  
  // Árbol de mensajes
  fullTree: TreeNode[] | null;
  activeLeafId: number | null;
  
  // Estado de streaming
  isLoading: boolean;
  isStreaming: boolean;
  currentChunk: string;
  streamingMessageId: number | null;
  
  // Acciones
  setConversation: (id: string | null) => void;
  setMessages: (messages: Message[]) => void;
  addMessage: (message: Message) => void;
  updateMessage: (id: number, updates: Partial<Message>) => void;
  
  // Streaming
  setLoading: (loading: boolean) => void;
  setStreaming: (streaming: boolean) => void;
  appendChunk: (chunk: string) => void;
  clearChunk: () => void;
  setStreamingMessageId: (id: number | null) => void;
  
  // Árbol
  setFullTree: (tree: TreeNode[] | null) => void;
  setActiveLeafId: (id: number | null) => void;
  
  // Reset
  resetChat: () => void;
}

export const useChatStore = create<ChatState>()((set) => ({
  conversationId: null,
  messages: [],
  fullTree: null,
  activeLeafId: null,
  isLoading: false,
  isStreaming: false,
  currentChunk: '',
  streamingMessageId: null,
  
  setConversation: (id) => set({ conversationId: id }),
  setMessages: (messages) => set({ messages }),
  addMessage: (message) => set((state) => ({ 
    messages: [...state.messages, message] 
  })),
  updateMessage: (id, updates) => set((state) => ({
    messages: state.messages.map(m => m.id === id ? { ...m, ...updates } : m)
  })),
  
  setLoading: (loading) => set({ isLoading: loading }),
  setStreaming: (streaming) => set({ isStreaming: streaming }),
  appendChunk: (chunk) => set((state) => ({ 
    currentChunk: state.currentChunk + chunk 
  })),
  clearChunk: () => set({ currentChunk: '' }),
  setStreamingMessageId: (id) => set({ streamingMessageId: id }),
  
  setFullTree: (tree) => set({ fullTree: tree }),
  setActiveLeafId: (id) => set({ activeLeafId: id }),
  
  resetChat: () => set({
    conversationId: null,
    messages: [],
    fullTree: null,
    activeLeafId: null,
    isLoading: false,
    isStreaming: false,
    currentChunk: '',
    streamingMessageId: null,
  }),
}));

// ============================================
// MODELS STORE - Lista de modelos, favoritos, filtros
// ============================================

// Estos valores coinciden con el backend
export type BackendSorting = 'default' | 'ranking' | 'context';
export type GroupOption = 'none' | 'provider';

interface ModelsFilters {
  sorting: BackendSorting;  // Se envía al backend
  groupBy: GroupOption;     // Solo frontend
  onlyFree: boolean;        // Se envía al backend (openrouter_free)
}

// Parámetros avanzados para LLMs
export interface AdvancedParams {
  temperature: number | null;  // null = usar default del proveedor
  top_p: number | null;
  max_tokens: number | null;
}

interface ModelsState {
  models: Model[];
  selectedModel: Model | null;
  favorites: string[]; // IDs de modelos favoritos
  isLoadingModels: boolean;
  filters: ModelsFilters;
  
  // Parámetros avanzados
  advancedParams: AdvancedParams;
  modelsUsingDefaults: string[];  // IDs de modelos que ignoran params avanzados
  
  setModels: (models: Model[]) => void;
  setSelectedModel: (model: Model | null) => void;
  toggleFavorite: (modelId: string) => void;
  setLoadingModels: (loading: boolean) => void;
  setSorting: (sorting: BackendSorting) => void;
  setGroupBy: (group: GroupOption) => void;
  setOnlyFree: (onlyFree: boolean) => void;
  
  // Parámetros avanzados
  setAdvancedParams: (params: Partial<AdvancedParams>) => void;
  toggleModelDefaults: (modelId: string) => void;
  addModelToDefaults: (modelId: string) => void;
}

export const useModelsStore = create<ModelsState>()(
  persist(
    (set) => ({
      models: [],
      selectedModel: null,
      favorites: [],
      isLoadingModels: false,
      filters: {
        sorting: 'ranking',  // Por defecto ordenar por ELO/ranking
        groupBy: 'none',
        onlyFree: false,
      },
      advancedParams: {
        temperature: 0.1,  // Default para ciberseguridad (preciso)
        top_p: null,
        max_tokens: null,
      },
      modelsUsingDefaults: ['gpt-5-nano'],  // Modelos conocidos con restricciones
      
      setModels: (models) => set({ models }),
      setSelectedModel: (model) => set({ selectedModel: model }),
      toggleFavorite: (modelId) => set((state) => ({
        favorites: state.favorites.includes(modelId)
          ? state.favorites.filter(id => id !== modelId)
          : [...state.favorites, modelId]
      })),
      setLoadingModels: (loading) => set({ isLoadingModels: loading }),
      setSorting: (sorting) => set((state) => ({
        filters: { ...state.filters, sorting }
      })),
      setGroupBy: (groupBy) => set((state) => ({
        filters: { ...state.filters, groupBy }
      })),
      setOnlyFree: (onlyFree) => set((state) => ({
        filters: { ...state.filters, onlyFree }
      })),
      setAdvancedParams: (params) => set((state) => ({
        advancedParams: { ...state.advancedParams, ...params }
      })),
      toggleModelDefaults: (modelId) => set((state) => ({
        modelsUsingDefaults: state.modelsUsingDefaults.includes(modelId)
          ? state.modelsUsingDefaults.filter(id => id !== modelId)
          : [...state.modelsUsingDefaults, modelId]
      })),
      addModelToDefaults: (modelId) => set((state) => ({
        modelsUsingDefaults: state.modelsUsingDefaults.includes(modelId)
          ? state.modelsUsingDefaults
          : [...state.modelsUsingDefaults, modelId]
      })),
    }),
    {
      name: 'cerebro-models',
      partialize: (state) => ({
        favorites: state.favorites,
        selectedModel: state.selectedModel,
        filters: state.filters,
        advancedParams: state.advancedParams,
        modelsUsingDefaults: state.modelsUsingDefaults,
      }),
    }
  )
);

// ============================================
// UI STORE - Layout, panels, modals
// ============================================

interface UIState {
  isSidebarOpen: boolean;
  isTerminalOpen: boolean;
  isConfigModalOpen: boolean;
  isModelSelectorOpen: boolean;
  
  toggleSidebar: () => void;
  toggleTerminal: () => void;
  setTerminalOpen: (open: boolean) => void;
  setConfigModalOpen: (open: boolean) => void;
  setModelSelectorOpen: (open: boolean) => void;
}

export const useUIStore = create<UIState>()((set) => ({
  isSidebarOpen: true,
  isTerminalOpen: false,
  isConfigModalOpen: false,
  isModelSelectorOpen: false,
  
  toggleSidebar: () => set((state) => ({ isSidebarOpen: !state.isSidebarOpen })),
  toggleTerminal: () => set((state) => ({ isTerminalOpen: !state.isTerminalOpen })),
  setTerminalOpen: (open) => set({ isTerminalOpen: open }),
  setConfigModalOpen: (open) => set({ isConfigModalOpen: open }),
  setModelSelectorOpen: (open) => set({ isModelSelectorOpen: open }),
}));

// ============================================
// CONVERSATIONS STORE - Lista de conversaciones
// ============================================

interface ConversationsState {
  conversations: Conversation[];
  isLoading: boolean;
  
  setConversations: (conversations: Conversation[]) => void;
  addConversation: (conversation: Conversation) => void;
  removeConversation: (id: string) => void;
  updateConversation: (id: string, updates: Partial<Conversation>) => void;
  setLoading: (loading: boolean) => void;
}

export const useConversationsStore = create<ConversationsState>()((set) => ({
  conversations: [],
  isLoading: false,
  
  setConversations: (conversations) => set({ conversations }),
  addConversation: (conversation) => set((state) => ({
    conversations: [conversation, ...state.conversations]
  })),
  removeConversation: (id) => set((state) => ({
    conversations: state.conversations.filter(c => c.id !== id)
  })),
  updateConversation: (id, updates) => set((state) => ({
    conversations: state.conversations.map(c => 
      c.id === id ? { ...c, ...updates } : c
    )
  })),
  setLoading: (loading) => set({ isLoading: loading }),
}));

// ============================================
// TERMINAL STORE - Estado de sesiones de terminal
// ============================================

export interface TerminalJob {
  id: string;
  command: string;
  cwd: string;
  status: 'running' | 'completed' | 'timeout';
  started_at: string;
  elapsed?: string;
  conversation_id?: string;
  leaf_id?: number;
}

export interface TerminalSession {
  conversationId: string;
  initialized: boolean;
  repoPath?: string;
  currentLeafId: number | null;
}

interface TerminalState {
  // Sesiones por conversación
  sessions: Record<string, TerminalSession>;
  
  // Jobs activos en la conversación actual
  runningJobs: TerminalJob[];
  
  // Estado de conexión con el sandbox
  isConnected: boolean;
  lastError: string | null;
  
  // Acciones
  initSession: (conversationId: string, repoPath?: string) => void;
  updateSessionLeaf: (conversationId: string, leafId: number) => void;
  setRunningJobs: (jobs: TerminalJob[]) => void;
  addRunningJob: (job: TerminalJob) => void;
  removeRunningJob: (jobId: string) => void;
  updateJobStatus: (jobId: string, status: 'running' | 'completed' | 'timeout') => void;
  setConnected: (connected: boolean) => void;
  setError: (error: string | null) => void;
  clearSession: (conversationId: string) => void;
}

export const useTerminalStore = create<TerminalState>()((set) => ({
  sessions: {},
  runningJobs: [],
  isConnected: false,
  lastError: null,
  
  initSession: (conversationId, repoPath) => set((state) => ({
    sessions: {
      ...state.sessions,
      [conversationId]: {
        conversationId,
        initialized: true,
        repoPath,
        currentLeafId: null,
      }
    }
  })),
  
  updateSessionLeaf: (conversationId, leafId) => set((state) => ({
    sessions: {
      ...state.sessions,
      [conversationId]: {
        ...state.sessions[conversationId],
        currentLeafId: leafId,
      }
    }
  })),
  
  setRunningJobs: (jobs) => set({ runningJobs: jobs }),
  
  addRunningJob: (job) => set((state) => ({
    runningJobs: [...state.runningJobs, job]
  })),
  
  removeRunningJob: (jobId) => set((state) => ({
    runningJobs: state.runningJobs.filter(j => j.id !== jobId)
  })),
  
  updateJobStatus: (jobId, status) => set((state) => ({
    runningJobs: state.runningJobs.map(j => 
      j.id === jobId ? { ...j, status } : j
    )
  })),
  
  setConnected: (connected) => set({ isConnected: connected }),
  
  setError: (error) => set({ lastError: error }),
  
  clearSession: (conversationId) => set((state) => {
    const { [conversationId]: _, ...rest } = state.sessions;
    return { sessions: rest };
  }),
}));

// ============================================
// LEGACY EXPORT - Compatibilidad con código existente
// ============================================

export const useStore = useUIStore;