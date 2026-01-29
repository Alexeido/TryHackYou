# Documentación Técnica: Frontend LLM

## 1. Visión General

El **Frontend LLM** es una aplicación web construida con **Next.js 16** y **React 19** que proporciona una interfaz de usuario completa para interactuar con múltiples proveedores de IA, gestionar conversaciones con estructura de árbol, ejecutar comandos en el sandbox, y supervisar misiones autónomas del agente.

### 1.1 Stack Tecnológico

| Categoría | Tecnología | Versión |
|-----------|------------|---------|
| Framework | Next.js | 16.0.10 |
| UI Library | React | 19.2.1 |
| Lenguaje | TypeScript | 5.x |
| State Management | Zustand | 5.0.6 |
| Styling | TailwindCSS | 4.1.7 |
| Component Library | Radix UI | 1.x |
| Icons | Lucide React | 0.513.0 |
| Markdown | react-markdown + remark-gfm | 10.1.0 |
| Syntax Highlighting | Prism React Renderer | 2.4.1 |
| Resizable Panels | react-resizable-panels | 2.1.7 |
| Monospace Font | Geist Mono | 1.4.1 |

### 1.2 Arquitectura de Alto Nivel

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Frontend LLM (Next.js)                            │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      STORES (Zustand)                                │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │   │
│  │  │ Config   │ │  Chat    │ │  Models  │ │   UI     │ │ Terminal │  │   │
│  │  │ Store    │ │  Store   │ │  Store   │ │  Store   │ │  Store   │  │   │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘  │   │
│  └───────┼────────────┼────────────┼────────────┼────────────┼────────┘   │
│          │            │            │            │            │            │
│  ┌───────┴────────────┴────────────┴────────────┴────────────┴────────┐   │
│  │                        COMPONENTS                                   │   │
│  │                                                                     │   │
│  │   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐            │   │
│  │   │  Sidebar    │    │   Chat      │    │  Terminal   │            │   │
│  │   │  - History  │    │   Area      │    │   Panel     │            │   │
│  │   │  - Search   │    │   - Input   │    │   - Output  │            │   │
│  │   │  - Config   │    │   - Messages│    │   - Commands│            │   │
│  │   └─────────────┘    └─────────────┘    └─────────────┘            │   │
│  │                                                                     │   │
│  │   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐            │   │
│  │   │  Mission    │    │   Models    │    │   Config    │            │   │
│  │   │  Panel      │    │   Selector  │    │   Dialog    │            │   │
│  │   │  - Status   │    │   - Grid    │    │   - Keys    │            │   │
│  │   │  - Approval │    │   - Filters │    │   - Settings│            │   │
│  │   └─────────────┘    └─────────────┘    └─────────────┘            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────┴───────────────────────────────────┐   │
│  │                         SERVICES                                     │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │   │
│  │  │  api.ts  │  │terminal.ts│  │missions.ts│  │ tools.ts │            │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                          HTTP / SSE / WebSocket
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │       Backend LLM (FastAPI)   │
                    │       Puerto 4000             │
                    └───────────────────────────────┘
```

---

## 2. Estructura del Proyecto

```
LLM/frontend/
├── app/
│   ├── globals.css           # Estilos globales + TailwindCSS
│   ├── icon.tsx              # Icono de la aplicación
│   ├── layout.tsx            # Layout raíz con providers
│   └── page.tsx              # Página principal
│
├── components/
│   ├── chat/
│   │   ├── ChatArea.tsx      # Área de mensajes principal
│   │   ├── ChatInput.tsx     # Input de chat con auto-resize
│   │   ├── MessageBubble.tsx # Renderizado de mensajes (Markdown, code)
│   │   └── CodeBlock.tsx     # Bloques de código con syntax highlight
│   │
│   ├── config/
│   │   ├── ConfigPanel.tsx   # Panel de configuración desplegable
│   │   ├── ProviderSelect.tsx # Selector de proveedor de IA
│   │   └── ApiKeyInput.tsx   # Input de API key con validación
│   │
│   ├── layout/
│   │   ├── MainLayout.tsx    # Layout con paneles redimensionables
│   │   ├── ChatSidebar.tsx   # Sidebar con historial de conversaciones
│   │   └── Header.tsx        # Header con controles globales
│   │
│   ├── mission/
│   │   ├── MissionPanel.tsx  # Panel de estado de misión
│   │   ├── ObjectiveList.tsx # Lista de objetivos con estados
│   │   └── ApprovalDialog.tsx # Diálogo de aprobación de comandos
│   │
│   ├── models/
│   │   ├── ModelSelector.tsx # Grid de modelos disponibles
│   │   ├── ModelCard.tsx     # Card de modelo individual
│   │   └── ModelFilters.tsx  # Filtros por proveedor, capacidad
│   │
│   ├── terminal/
│   │   ├── TerminalPanel.tsx # Panel de terminal integrado
│   │   └── TerminalOutput.tsx # Renderizado de output ANSI
│   │
│   └── ui/                   # Componentes base (shadcn/ui)
│       ├── button.tsx
│       ├── dialog.tsx
│       ├── input.tsx
│       ├── scroll-area.tsx
│       └── ...
│
├── hooks/
│   ├── useChat.ts            # Hook de lógica de chat
│   ├── useKeyboardShortcuts.ts
│   └── useTheme.ts
│
├── lib/
│   └── utils.ts              # Utilidades (cn, formatDate, etc.)
│
├── services/
│   ├── api.ts                # Cliente HTTP para backend
│   ├── terminal.ts           # Comunicación con sandbox
│   ├── missions.ts           # API de misiones
│   └── tools.ts              # Definiciones de tools para LLM
│
├── store/
│   └── useStore.ts           # Stores de Zustand (5 stores)
│
└── public/                   # Assets estáticos
```

---

## 3. Stores de Zustand (store/useStore.ts)

### 3.1 useConfigStore

Gestiona configuración persistente de la aplicación.

```typescript
interface ConfigState {
  // Proveedores
  provider: Provider; // 'openai' | 'google' | 'deepseek' | 'openrouter' | 'anthropic' | 'ollama'
  
  // API Keys por proveedor
  apiKeys: Record<Provider, string>;
  
  // Ollama específico
  ollamaUrl: string;  // Default: 'http://localhost:11434'
  
  // Configuración de backend
  backendUrl: string; // Default: 'http://localhost:4000'
  
  // UI
  theme: 'light' | 'dark' | 'system';
  
  // System prompt personalizado
  systemPrompt: string;
  
  // Actions
  setProvider: (provider: Provider) => void;
  setApiKey: (provider: Provider, key: string) => void;
  setBackendUrl: (url: string) => void;
  setTheme: (theme: Theme) => void;
  setSystemPrompt: (prompt: string) => void;
}
```

**Persistencia:** Los datos se guardan en `localStorage` automáticamente.

### 3.2 useChatStore

Gestiona el estado de la conversación actual.

```typescript
interface ChatState {
  // Mensajes de la conversación actual
  messages: Message[];
  
  // Conversación activa
  conversationId: string | null;
  activeLeafId: number | null;
  
  // Estado de streaming
  isStreaming: boolean;
  streamingContent: string;
  
  // Estados de carga
  isLoading: boolean;
  error: string | null;
  
  // Árbol de mensajes (para navegación de ramas)
  messageTree: TreeNode[];
  
  // Tool calls en progreso
  pendingToolCalls: ToolCall[];
  
  // Actions
  sendMessage: (content: string) => Promise<void>;
  regenerate: () => Promise<void>;
  editMessage: (messageId: number, content: string) => Promise<void>;
  switchBranch: (leafId: number) => Promise<void>;
  loadConversation: (id: string) => Promise<void>;
  clearChat: () => void;
  
  // Streaming
  appendStreamChunk: (chunk: string) => void;
  finalizeStream: (message: Message) => void;
}
```

### 3.3 useModelsStore

Gestiona la lista de modelos y selección.

```typescript
interface ModelsState {
  // Lista de modelos disponibles
  models: Model[];
  
  // Modelo seleccionado actualmente
  selectedModel: Model | null;
  
  // Favoritos del usuario
  favorites: string[]; // IDs de modelos
  
  // Filtros activos
  filters: {
    provider: Provider | null;
    hasTools: boolean;
    hasVision: boolean;
    searchQuery: string;
  };
  
  // Parámetros avanzados
  advancedParams: {
    temperature: number;  // Default: 0.7
    topP: number;         // Default: 1.0
    maxTokens: number | null;
  };
  
  // Estados
  isLoading: boolean;
  
  // Actions
  fetchModels: () => Promise<void>;
  selectModel: (model: Model) => void;
  toggleFavorite: (modelId: string) => void;
  setFilter: (key: string, value: any) => void;
  setAdvancedParam: (key: string, value: number) => void;
}
```

### 3.4 useUIStore

Gestiona estados de UI globales.

```typescript
interface UIState {
  // Paneles
  sidebarOpen: boolean;
  terminalOpen: boolean;
  missionPanelOpen: boolean;
  configPanelOpen: boolean;
  
  // Modales
  modelSelectorOpen: boolean;
  settingsDialogOpen: boolean;
  
  // Estados de tamaño de paneles (react-resizable-panels)
  panelSizes: {
    sidebar: number;
    terminal: number;
    mission: number;
  };
  
  // Tema (sincronizado con sistema)
  isDarkMode: boolean;
  
  // Actions
  toggleSidebar: () => void;
  toggleTerminal: () => void;
  toggleMissionPanel: () => void;
  openModelSelector: () => void;
  closeModelSelector: () => void;
  setPanelSize: (panel: string, size: number) => void;
}
```

### 3.5 useConversationsStore

Gestiona el historial de conversaciones.

```typescript
interface ConversationsState {
  // Lista de conversaciones
  conversations: Conversation[];
  
  // Búsqueda
  searchQuery: string;
  
  // Paginación
  hasMore: boolean;
  isLoading: boolean;
  
  // Actions
  fetchConversations: () => Promise<void>;
  createConversation: () => Promise<string>;
  deleteConversation: (id: string) => Promise<void>;
  renameConversation: (id: string, title: string) => Promise<void>;
  pinConversation: (id: string) => Promise<void>;
  search: (query: string) => void;
}
```

### 3.6 useTerminalStore

Gestiona el estado del terminal integrado.

```typescript
interface TerminalState {
  // Output del terminal (histórico)
  output: TerminalLine[];
  
  // Comando actual siendo escrito
  currentCommand: string;
  
  // Historial de comandos
  commandHistory: string[];
  historyIndex: number;
  
  // Estado de ejecución
  isExecuting: boolean;
  currentJobId: string | null;
  
  // Sesión de sandbox
  sessionId: string | null;
  
  // Actions
  executeCommand: (command: string) => Promise<void>;
  appendOutput: (line: TerminalLine) => void;
  clearOutput: () => void;
  setCurrentCommand: (cmd: string) => void;
  navigateHistory: (direction: 'up' | 'down') => void;
}
```

### 3.7 useMissionStore

Gestiona el estado de misiones autónomas.

```typescript
interface MissionState {
  // Misión activa
  activeMission: Mission | null;
  
  // Lista de objetivos
  objectives: Objective[];
  
  // Aprobaciones pendientes
  pendingApprovals: Approval[];
  
  // Estados
  isLoading: boolean;
  
  // Actions
  fetchActiveMission: (conversationId: string) => Promise<void>;
  approveCommand: (approvalId: number, approved: boolean) => Promise<void>;
  refreshMission: () => Promise<void>;
}
```

---

## 4. Servicios (services/)

### 4.1 api.ts - Cliente HTTP Principal

```typescript
// Base de todas las peticiones
const BASE_URL = getBackendUrl(); // Desde configStore

// ==================== CHAT ====================

export async function sendChatMessage(request: ChatRequest): Promise<Response> {
  return fetch(`${BASE_URL}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
}

// Streaming con SSE
export function streamChat(request: ChatRequest): EventSource {
  // Crear URL con parámetros
  const eventSource = new EventSource(`${BASE_URL}/chat/stream`, { ... });
  
  eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    switch (data.type) {
      case 'content':
        // Chunk de texto
        useChatStore.getState().appendStreamChunk(data.chunk);
        break;
        
      case 'tool_call':
        // LLM quiere ejecutar una tool
        useChatStore.getState().addPendingToolCall(data.tool_call);
        break;
        
      case 'tool_result':
        // Resultado de tool execution
        useChatStore.getState().updateToolCallResult(data.tool_call_id, data.result);
        break;
        
      case 'done':
        // Finalizado
        useChatStore.getState().finalizeStream(data.message);
        break;
    }
  };
  
  return eventSource;
}

// ==================== CONVERSATIONS ====================

export async function getConversations(): Promise<Conversation[]> {
  const res = await fetch(`${BASE_URL}/conversations`);
  return res.json();
}

export async function getConversation(id: string): Promise<Conversation> {
  const res = await fetch(`${BASE_URL}/conversations/${id}`);
  return res.json();
}

export async function getConversationThread(id: string): Promise<Message[]> {
  const res = await fetch(`${BASE_URL}/conversations/${id}/thread`);
  return res.json();
}

export async function getConversationTree(id: string): Promise<TreeNode[]> {
  const res = await fetch(`${BASE_URL}/conversations/${id}/tree`);
  return res.json();
}

export async function createConversation(systemPrompt?: string): Promise<Conversation> {
  const res = await fetch(`${BASE_URL}/conversations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ system_prompt: systemPrompt }),
  });
  return res.json();
}

export async function deleteConversation(id: string): Promise<void> {
  await fetch(`${BASE_URL}/conversations/${id}`, { method: 'DELETE' });
}

export async function switchBranch(conversationId: string, leafId: number): Promise<void> {
  await fetch(`${BASE_URL}/conversations/${conversationId}/active-leaf`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ leaf_id: leafId }),
  });
}

// ==================== MODELS ====================

export async function discoverModels(provider: Provider, apiKey: string): Promise<Model[]> {
  const res = await fetch(`${BASE_URL}/models/discover`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ provider, api_key: apiKey }),
  });
  return res.json();
}

export async function getOllamaModels(url: string): Promise<Model[]> {
  const res = await fetch(`${BASE_URL}/ollama/models`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ollama_url: url }),
  });
  return res.json();
}

// ==================== HEALTH ====================

export async function validateApiKeys(keys: Record<Provider, string>): Promise<ValidationResult> {
  const res = await fetch(`${BASE_URL}/health/keys`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ keys }),
  });
  return res.json();
}
```

### 4.2 terminal.ts - Comunicación con Sandbox

```typescript
const SANDBOX_URL = 'http://localhost:5000';

// Ejecutar comando en sandbox
export async function executeCommand(command: string, options?: ExecuteOptions): Promise<ExecuteResponse> {
  const res = await fetch(`${SANDBOX_URL}/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      command,
      timeout: options?.timeout ?? 120,
      background: options?.background ?? false,
    }),
  });
  
  return res.json();
}

// Consultar estado de job
export async function checkJobStatus(jobId: string): Promise<JobStatus> {
  const res = await fetch(`${SANDBOX_URL}/status/${jobId}`);
  return res.json();
}

// Detener job
export async function stopJob(jobId: string): Promise<void> {
  await fetch(`${SANDBOX_URL}/stop/${jobId}`, { method: 'POST' });
}

// Iniciar sesión Git
export async function initSession(name?: string): Promise<SessionInfo> {
  const res = await fetch(`${SANDBOX_URL}/session/init`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_name: name }),
  });
  return res.json();
}

// Obtener historial de sesión
export async function getSessionHistory(sessionId: string): Promise<CommandHistory[]> {
  const res = await fetch(`${SANDBOX_URL}/history/${sessionId}`);
  return res.json();
}
```

### 4.3 missions.ts - API de Misiones

```typescript
// Obtener misión activa de una conversación
export async function getActiveMission(conversationId: string): Promise<Mission | null> {
  const res = await fetch(`${BASE_URL}/missions/conversation/${conversationId}/active`);
  if (res.status === 404) return null;
  return res.json();
}

// Obtener objetivos de una misión
export async function getMissionObjectives(missionId: string): Promise<Objective[]> {
  const res = await fetch(`${BASE_URL}/missions/${missionId}/objectives`);
  return res.json();
}

// Obtener aprobaciones pendientes
export async function getPendingApprovals(): Promise<Approval[]> {
  const res = await fetch(`${BASE_URL}/missions/approvals`);
  return res.json();
}

// Aprobar/rechazar comando
export async function handleApproval(approvalId: number, approved: boolean, comment?: string): Promise<void> {
  await fetch(`${BASE_URL}/missions/approvals/${approvalId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ approved, comment }),
  });
}

// Cancelar misión
export async function cancelMission(missionId: string): Promise<void> {
  await fetch(`${BASE_URL}/missions/${missionId}/complete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: 'CANCELLED' }),
  });
}
```

### 4.4 tools.ts - Definiciones de Tools para LLM

```typescript
// Definición de tools que se envían al LLM
export const AVAILABLE_TOOLS: ToolDefinition[] = [
  {
    type: 'function',
    function: {
      name: 'execute_command',
      description: `Execute a shell command in a Kali Linux sandbox environment.
        The sandbox has access to common pentesting tools: nmap, sqlmap, nikto, hydra, etc.
        Commands that exceed timeout will run in background with a job_id for status checking.
        Use this for reconnaissance, scanning, exploitation, and post-exploitation tasks.`,
      parameters: {
        type: 'object',
        properties: {
          command: {
            type: 'string',
            description: 'The shell command to execute',
          },
          timeout: {
            type: 'integer',
            description: 'Timeout in seconds (default: 120). Use higher for long-running scans.',
          },
          background: {
            type: 'boolean',
            description: 'Run in background immediately, returning a job_id',
          },
        },
        required: ['command'],
      },
    },
  },
  
  {
    type: 'function',
    function: {
      name: 'check_job_status',
      description: `Check the status of a background job.
        Returns: running, finished, stopped, or error.
        If finished, includes the full output.`,
      parameters: {
        type: 'object',
        properties: {
          job_id: {
            type: 'string',
            description: 'The job ID returned from execute_command',
          },
        },
        required: ['job_id'],
      },
    },
  },
  
  {
    type: 'function',
    function: {
      name: 'manage_mission',
      description: `Manage the current autonomous mission.
        Actions:
        - create: Create a new mission with objectives
        - update_objective: Update objective status (IN_PROGRESS, COMPLETED, FAILED, SKIPPED)
        - update_phase: Change mission phase (Reconnaissance, Enumeration, Exploitation, etc.)
        - complete: Mark mission as COMPLETED or FAILED
        - get_status: Get current mission state
        - modify_objectives: Add, remove, or reorder objectives`,
      parameters: {
        type: 'object',
        properties: {
          action: {
            type: 'string',
            enum: ['create', 'update_objective', 'update_phase', 'complete', 'get_status', 'modify_objectives'],
          },
          goal: {
            type: 'string',
            description: 'Mission goal (required for create)',
          },
          objectives: {
            type: 'array',
            items: { type: 'string' },
            description: 'List of objectives (required for create)',
          },
          objective_id: {
            type: 'integer',
            description: 'Objective ID (for update_objective)',
          },
          status: {
            type: 'string',
            enum: ['PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'SKIPPED'],
          },
          result_summary: {
            type: 'string',
            description: 'Summary of objective result',
          },
          phase: {
            type: 'string',
            description: 'Current phase of the mission',
          },
          mission_id: {
            type: 'string',
            description: 'Mission ID (for update_phase, complete)',
          },
          modifications: {
            type: 'array',
            description: 'Modifications to objectives (for modify_objectives)',
          },
        },
        required: ['action'],
      },
    },
  },
  
  {
    type: 'function',
    function: {
      name: 'read_file',
      description: `Read contents of a file in the sandbox.
        Useful for reading configuration files, logs, or extracted data.`,
      parameters: {
        type: 'object',
        properties: {
          path: {
            type: 'string',
            description: 'Absolute path to the file',
          },
        },
        required: ['path'],
      },
    },
  },
  
  {
    type: 'function',
    function: {
      name: 'write_file',
      description: `Write content to a file in the sandbox.
        Useful for creating scripts, wordlists, or saving data.`,
      parameters: {
        type: 'object',
        properties: {
          path: {
            type: 'string',
            description: 'Absolute path to the file',
          },
          content: {
            type: 'string',
            description: 'Content to write',
          },
        },
        required: ['path', 'content'],
      },
    },
  },
];

// Helper para obtener tools filtradas por capacidad del modelo
export function getToolsForModel(model: Model): ToolDefinition[] {
  if (!model.capabilities?.tools) {
    return []; // Modelo no soporta tools
  }
  
  return AVAILABLE_TOOLS;
}
```

---

## 5. Componentes Principales

### 5.1 MainLayout.tsx

Layout principal con paneles redimensionables.

```tsx
export default function MainLayout() {
  const { sidebarOpen, terminalOpen, missionPanelOpen } = useUIStore();
  
  return (
    <div className="h-screen flex flex-col bg-background">
      <Header />
      
      <PanelGroup direction="horizontal" className="flex-1">
        {/* Sidebar */}
        {sidebarOpen && (
          <>
            <Panel defaultSize={20} minSize={15} maxSize={30}>
              <ChatSidebar />
            </Panel>
            <PanelResizeHandle className="w-1 bg-border hover:bg-primary/50" />
          </>
        )}
        
        {/* Main Content */}
        <Panel defaultSize={60}>
          <PanelGroup direction="vertical">
            {/* Chat Area */}
            <Panel defaultSize={terminalOpen ? 70 : 100}>
              <ChatArea />
            </Panel>
            
            {/* Terminal */}
            {terminalOpen && (
              <>
                <PanelResizeHandle className="h-1 bg-border hover:bg-primary/50" />
                <Panel defaultSize={30} minSize={15}>
                  <TerminalPanel />
                </Panel>
              </>
            )}
          </PanelGroup>
        </Panel>
        
        {/* Mission Panel */}
        {missionPanelOpen && (
          <>
            <PanelResizeHandle className="w-1 bg-border hover:bg-primary/50" />
            <Panel defaultSize={20} minSize={15} maxSize={35}>
              <MissionPanel />
            </Panel>
          </>
        )}
      </PanelGroup>
    </div>
  );
}
```

### 5.2 ChatArea.tsx

Área principal de chat con mensajes y input.

```tsx
export default function ChatArea() {
  const { 
    messages, 
    isStreaming, 
    streamingContent,
    conversationId,
  } = useChatStore();
  
  const scrollRef = useRef<HTMLDivElement>(null);
  
  // Auto-scroll cuando hay nuevo contenido
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, streamingContent]);
  
  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <ScrollArea ref={scrollRef} className="flex-1 p-4">
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
        
        {/* Streaming indicator */}
        {isStreaming && (
          <MessageBubble 
            message={{ 
              role: 'assistant', 
              content: streamingContent 
            }} 
            isStreaming 
          />
        )}
      </ScrollArea>
      
      {/* Input */}
      <div className="border-t p-4">
        <ChatInput disabled={isStreaming} />
      </div>
    </div>
  );
}
```

### 5.3 MessageBubble.tsx

Renderizado de mensajes con soporte Markdown y código.

```tsx
export default function MessageBubble({ message, isStreaming }: Props) {
  const isUser = message.role === 'user';
  const isTool = message.role === 'tool';
  
  return (
    <div className={cn(
      "flex gap-3 mb-4",
      isUser && "justify-end"
    )}>
      {/* Avatar */}
      {!isUser && (
        <Avatar className="w-8 h-8">
          {isTool ? <ToolIcon /> : <BotIcon />}
        </Avatar>
      )}
      
      {/* Content */}
      <div className={cn(
        "max-w-[80%] rounded-lg p-3",
        isUser && "bg-primary text-primary-foreground",
        !isUser && "bg-muted"
      )}>
        {/* Tool calls badge */}
        {message.tool_calls && (
          <div className="flex gap-2 mb-2">
            {JSON.parse(message.tool_calls).map((tc: ToolCall) => (
              <Badge key={tc.id} variant="outline">
                <TerminalIcon className="w-3 h-3 mr-1" />
                {tc.function.name}
              </Badge>
            ))}
          </div>
        )}
        
        {/* Markdown content */}
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            code({ node, inline, className, children, ...props }) {
              const match = /language-(\w+)/.exec(className || '');
              
              if (!inline && match) {
                return (
                  <CodeBlock 
                    language={match[1]} 
                    code={String(children).replace(/\n$/, '')}
                  />
                );
              }
              
              return <code className="bg-muted px-1 rounded" {...props}>{children}</code>;
            },
            // ... other components
          }}
        >
          {message.content || ''}
        </ReactMarkdown>
        
        {/* Streaming cursor */}
        {isStreaming && <span className="animate-pulse">▌</span>}
      </div>
      
      {/* User avatar */}
      {isUser && (
        <Avatar className="w-8 h-8">
          <UserIcon />
        </Avatar>
      )}
    </div>
  );
}
```

### 5.4 ChatSidebar.tsx

Sidebar con historial de conversaciones.

```tsx
export default function ChatSidebar() {
  const { 
    conversations, 
    searchQuery, 
    fetchConversations,
    search,
  } = useConversationsStore();
  
  const { loadConversation, conversationId } = useChatStore();
  const { closeSidebar } = useUIStore();
  
  useEffect(() => {
    fetchConversations();
  }, []);
  
  // Filtrar conversaciones
  const filtered = useMemo(() => {
    if (!searchQuery) return conversations;
    
    return conversations.filter(c => 
      c.title.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [conversations, searchQuery]);
  
  // Separar pinned de no pinned
  const pinned = filtered.filter(c => c.pinned);
  const unpinned = filtered.filter(c => !c.pinned);
  
  return (
    <div className="h-full flex flex-col bg-background border-r">
      {/* Header */}
      <div className="p-4 border-b flex justify-between items-center">
        <h2 className="font-semibold">Conversaciones</h2>
        <Button variant="ghost" size="icon" onClick={() => createConversation()}>
          <PlusIcon />
        </Button>
      </div>
      
      {/* Search */}
      <div className="p-2">
        <Input 
          placeholder="Buscar..." 
          value={searchQuery}
          onChange={(e) => search(e.target.value)}
        />
      </div>
      
      {/* List */}
      <ScrollArea className="flex-1">
        {/* Pinned */}
        {pinned.length > 0 && (
          <div className="p-2">
            <h3 className="text-xs text-muted-foreground mb-2">FIJADAS</h3>
            {pinned.map(conv => (
              <ConversationItem 
                key={conv.id} 
                conversation={conv}
                isActive={conv.id === conversationId}
                onClick={() => loadConversation(conv.id)}
              />
            ))}
          </div>
        )}
        
        {/* Regular */}
        <div className="p-2">
          {unpinned.map(conv => (
            <ConversationItem 
              key={conv.id} 
              conversation={conv}
              isActive={conv.id === conversationId}
              onClick={() => loadConversation(conv.id)}
            />
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}
```

### 5.5 MissionPanel.tsx

Panel de estado de misión autónoma.

```tsx
export default function MissionPanel() {
  const { 
    activeMission, 
    objectives, 
    pendingApprovals,
    fetchActiveMission,
  } = useMissionStore();
  
  const { conversationId } = useChatStore();
  
  useEffect(() => {
    if (conversationId) {
      fetchActiveMission(conversationId);
    }
  }, [conversationId]);
  
  if (!activeMission) {
    return (
      <div className="h-full flex items-center justify-center text-muted-foreground">
        No hay misión activa
      </div>
    );
  }
  
  return (
    <div className="h-full flex flex-col bg-background border-l">
      {/* Header */}
      <div className="p-4 border-b">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">Misión</h2>
          <Badge variant={getStatusVariant(activeMission.status)}>
            {activeMission.status}
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground mt-1">
          {activeMission.goal}
        </p>
        {activeMission.current_phase && (
          <Badge variant="outline" className="mt-2">
            Fase: {activeMission.current_phase}
          </Badge>
        )}
      </div>
      
      {/* Approval alerts */}
      {pendingApprovals.length > 0 && (
        <div className="p-4 bg-yellow-500/10 border-b border-yellow-500/20">
          <div className="flex items-center gap-2 text-yellow-600">
            <AlertTriangleIcon className="w-4 h-4" />
            <span className="text-sm font-medium">
              {pendingApprovals.length} comando(s) esperando aprobación
            </span>
          </div>
        </div>
      )}
      
      {/* Objectives */}
      <ScrollArea className="flex-1 p-4">
        <h3 className="text-sm font-medium mb-3">Objetivos</h3>
        <ObjectiveList objectives={objectives} />
      </ScrollArea>
      
      {/* Approval dialogs */}
      {pendingApprovals.map(approval => (
        <ApprovalDialog key={approval.id} approval={approval} />
      ))}
    </div>
  );
}
```

### 5.6 ApprovalDialog.tsx

Diálogo para aprobar/rechazar comandos peligrosos.

```tsx
export default function ApprovalDialog({ approval }: Props) {
  const { approveCommand } = useMissionStore();
  const [comment, setComment] = useState('');
  
  const handleApprove = async () => {
    await approveCommand(approval.id, true, comment);
  };
  
  const handleReject = async () => {
    await approveCommand(approval.id, false, comment);
  };
  
  return (
    <Dialog open>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ShieldAlertIcon className="w-5 h-5 text-yellow-500" />
            Aprobación Requerida
          </DialogTitle>
          <DialogDescription>
            El agente quiere ejecutar un comando de riesgo{' '}
            <Badge variant={getRiskVariant(approval.risk_level)}>
              {approval.risk_level.toUpperCase()}
            </Badge>
          </DialogDescription>
        </DialogHeader>
        
        <div className="my-4">
          <Label>Comando</Label>
          <div className="mt-1 p-3 bg-muted rounded font-mono text-sm">
            {approval.command}
          </div>
        </div>
        
        <div className="my-4">
          <Label>Motivo</Label>
          <p className="text-sm text-muted-foreground">
            {approval.reason}
          </p>
        </div>
        
        <div className="my-4">
          <Label>Comentario (opcional)</Label>
          <Textarea 
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Añadir contexto sobre tu decisión..."
          />
        </div>
        
        <DialogFooter>
          <Button variant="outline" onClick={handleReject}>
            <XIcon className="w-4 h-4 mr-2" />
            Rechazar
          </Button>
          <Button variant="destructive" onClick={handleApprove}>
            <CheckIcon className="w-4 h-4 mr-2" />
            Aprobar y Ejecutar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

### 5.7 ModelSelector.tsx

Grid de selección de modelos con filtros.

```tsx
export default function ModelSelector() {
  const { 
    models, 
    selectedModel, 
    filters,
    selectModel,
    setFilter,
    favorites,
    toggleFavorite,
  } = useModelsStore();
  
  const { closeModelSelector } = useUIStore();
  
  // Filtrar y ordenar modelos
  const filteredModels = useMemo(() => {
    let result = models;
    
    // Filtro por proveedor
    if (filters.provider) {
      result = result.filter(m => m.provider === filters.provider);
    }
    
    // Filtro por capacidades
    if (filters.hasTools) {
      result = result.filter(m => m.capabilities?.tools);
    }
    if (filters.hasVision) {
      result = result.filter(m => m.capabilities?.vision);
    }
    
    // Búsqueda
    if (filters.searchQuery) {
      const query = filters.searchQuery.toLowerCase();
      result = result.filter(m => 
        m.name.toLowerCase().includes(query) ||
        m.id.toLowerCase().includes(query)
      );
    }
    
    // Ordenar: favoritos primero, luego por score
    return result.sort((a, b) => {
      const aFav = favorites.includes(a.id) ? 1 : 0;
      const bFav = favorites.includes(b.id) ? 1 : 0;
      if (aFav !== bFav) return bFav - aFav;
      return (b.score || 0) - (a.score || 0);
    });
  }, [models, filters, favorites]);
  
  return (
    <Dialog open onOpenChange={closeModelSelector}>
      <DialogContent className="max-w-4xl max-h-[80vh]">
        <DialogHeader>
          <DialogTitle>Seleccionar Modelo</DialogTitle>
        </DialogHeader>
        
        {/* Filters */}
        <div className="flex gap-2 mb-4">
          <Input 
            placeholder="Buscar modelo..." 
            value={filters.searchQuery}
            onChange={(e) => setFilter('searchQuery', e.target.value)}
          />
          
          <Select 
            value={filters.provider || ''} 
            onValueChange={(v) => setFilter('provider', v || null)}
          >
            <SelectTrigger className="w-40">
              <SelectValue placeholder="Proveedor" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">Todos</SelectItem>
              <SelectItem value="openai">OpenAI</SelectItem>
              <SelectItem value="google">Google</SelectItem>
              <SelectItem value="anthropic">Anthropic</SelectItem>
              <SelectItem value="deepseek">DeepSeek</SelectItem>
              <SelectItem value="openrouter">OpenRouter</SelectItem>
              <SelectItem value="ollama">Ollama</SelectItem>
            </SelectContent>
          </Select>
          
          <Toggle 
            pressed={filters.hasTools}
            onPressedChange={(v) => setFilter('hasTools', v)}
          >
            <WrenchIcon className="w-4 h-4 mr-2" />
            Tools
          </Toggle>
          
          <Toggle 
            pressed={filters.hasVision}
            onPressedChange={(v) => setFilter('hasVision', v)}
          >
            <EyeIcon className="w-4 h-4 mr-2" />
            Visión
          </Toggle>
        </div>
        
        {/* Models grid */}
        <ScrollArea className="h-[500px]">
          <div className="grid grid-cols-2 gap-2">
            {filteredModels.map(model => (
              <ModelCard
                key={model.id}
                model={model}
                isSelected={selectedModel?.id === model.id}
                isFavorite={favorites.includes(model.id)}
                onSelect={() => selectModel(model)}
                onToggleFavorite={() => toggleFavorite(model.id)}
              />
            ))}
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}
```

### 5.8 TerminalPanel.tsx

Terminal integrado para comandos directos.

```tsx
export default function TerminalPanel() {
  const {
    output,
    currentCommand,
    isExecuting,
    executeCommand,
    setCurrentCommand,
    navigateHistory,
    clearOutput,
  } = useTerminalStore();
  
  const inputRef = useRef<HTMLInputElement>(null);
  const outputRef = useRef<HTMLDivElement>(null);
  
  // Auto-scroll
  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [output]);
  
  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && currentCommand.trim() && !isExecuting) {
      executeCommand(currentCommand);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      navigateHistory('up');
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      navigateHistory('down');
    } else if (e.key === 'l' && e.ctrlKey) {
      e.preventDefault();
      clearOutput();
    }
  };
  
  return (
    <div className="h-full flex flex-col bg-black text-green-400 font-mono text-sm">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-1 bg-zinc-900 border-b border-zinc-700">
        <span className="text-xs text-zinc-400">Terminal - KaliSandbox</span>
        <Button variant="ghost" size="icon" className="h-6 w-6" onClick={clearOutput}>
          <TrashIcon className="w-3 h-3" />
        </Button>
      </div>
      
      {/* Output */}
      <div ref={outputRef} className="flex-1 overflow-auto p-2">
        {output.map((line, i) => (
          <div 
            key={i}
            className={cn(
              line.type === 'error' && 'text-red-400',
              line.type === 'command' && 'text-blue-400',
              line.type === 'info' && 'text-yellow-400',
            )}
          >
            {line.type === 'command' && <span className="text-green-400">$ </span>}
            {line.content}
          </div>
        ))}
      </div>
      
      {/* Input */}
      <div className="flex items-center border-t border-zinc-700 p-2">
        <span className="text-green-400 mr-2">$</span>
        <input
          ref={inputRef}
          type="text"
          value={currentCommand}
          onChange={(e) => setCurrentCommand(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isExecuting}
          className="flex-1 bg-transparent outline-none text-white"
          placeholder={isExecuting ? "Ejecutando..." : "Escribe un comando..."}
        />
        {isExecuting && <Loader2Icon className="w-4 h-4 animate-spin" />}
      </div>
    </div>
  );
}
```

---

## 6. Flujo de Datos: Envío de Mensaje

```
┌────────────────┐
│  ChatInput     │  Usuario escribe y presiona Enter
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ useChatStore   │  sendMessage(content)
│ .sendMessage() │
└───────┬────────┘
        │
        ▼
┌────────────────────────────────────────────────────────────────┐
│  1. Actualizar estado optimista                                 │
│     - Añadir mensaje de usuario a messages[]                   │
│     - Activar isStreaming = true                               │
└───────┬────────────────────────────────────────────────────────┘
        │
        ▼
┌────────────────────────────────────────────────────────────────┐
│  2. Construir request                                          │
│     - provider, api_key, model_id (desde configStore)          │
│     - conversation_id, parent_message_id                       │
│     - user_message                                             │
│     - tools (desde tools.ts según modelo)                      │
│     - temperature, top_p, max_tokens (desde modelsStore)       │
└───────┬────────────────────────────────────────────────────────┘
        │
        ▼
┌────────────────────────────────────────────────────────────────┐
│  3. Enviar a api.ts                                            │
│     fetch(POST /chat, { ...request, stream: true })            │
└───────┬────────────────────────────────────────────────────────┘
        │
        ▼
┌────────────────────────────────────────────────────────────────┐
│  4. Procesar SSE stream                                        │
│                                                                │
│     event: message                                             │
│     → appendStreamChunk(chunk)                                 │
│     → UI muestra streamingContent + cursor                     │
│                                                                │
│     event: tool_call                                           │
│     → addPendingToolCall(tc)                                   │
│     → UI muestra badge de tool                                 │
│                                                                │
│     event: tool_result                                         │
│     → updateToolCallResult(id, result)                         │
│     → Si hay más tool_calls, backend sigue iterando            │
│                                                                │
│     event: done                                                │
│     → finalizeStream(finalMessage)                             │
│     → isStreaming = false                                      │
│     → Actualizar conversationId, activeLeafId                  │
└────────────────────────────────────────────────────────────────┘
```

---

## 7. Navegación de Ramas (Message Tree)

### 7.1 Concepto

Cuando el usuario edita un mensaje o regenera una respuesta, se crea una nueva rama en el árbol. La UI permite navegar entre ramas.

```
                    [system]
                        │
                    [user 1]
                        │
                   [assistant 1]
                        │
            ┌───────────┼───────────┐
        [user edit]  [user 2]   [regenerated]
            │           │           │
        [asst A]    [asst 2]    [asst B]
```

### 7.2 Componente de Navegación

```tsx
function BranchNavigation({ message }: Props) {
  const { messageTree, switchBranch } = useChatStore();
  
  // Encontrar hermanos (mensajes con mismo parent_id)
  const siblings = messageTree.filter(
    m => m.parent_id === message.parent_id && m.role === message.role
  );
  
  if (siblings.length <= 1) return null;
  
  const currentIndex = siblings.findIndex(s => s.id === message.id);
  
  return (
    <div className="flex items-center gap-1 text-xs text-muted-foreground">
      <Button 
        variant="ghost" 
        size="icon"
        disabled={currentIndex === 0}
        onClick={() => switchBranch(siblings[currentIndex - 1].id)}
      >
        <ChevronLeftIcon className="w-4 h-4" />
      </Button>
      <span>{currentIndex + 1} / {siblings.length}</span>
      <Button 
        variant="ghost" 
        size="icon"
        disabled={currentIndex === siblings.length - 1}
        onClick={() => switchBranch(siblings[currentIndex + 1].id)}
      >
        <ChevronRightIcon className="w-4 h-4" />
      </Button>
    </div>
  );
}
```

---

## 8. Temas (Dark/Light Mode)

### 8.1 Configuración CSS

```css
/* globals.css */
@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222.2 84% 4.9%;
    --primary: 222.2 47.4% 11.2%;
    --muted: 210 40% 96.1%;
    /* ... */
  }

  .dark {
    --background: 222.2 84% 4.9%;
    --foreground: 210 40% 98%;
    --primary: 210 40% 98%;
    --muted: 217.2 32.6% 17.5%;
    /* ... */
  }
}
```

### 8.2 Hook de Tema

```tsx
// hooks/useTheme.ts
export function useTheme() {
  const { theme, setTheme } = useConfigStore();
  
  useEffect(() => {
    const root = document.documentElement;
    
    if (theme === 'system') {
      const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches 
        ? 'dark' 
        : 'light';
      root.classList.toggle('dark', systemTheme === 'dark');
    } else {
      root.classList.toggle('dark', theme === 'dark');
    }
  }, [theme]);
  
  return { theme, setTheme };
}
```

---

## 9. Atajos de Teclado

```tsx
// hooks/useKeyboardShortcuts.ts
export function useKeyboardShortcuts() {
  const { toggleSidebar, toggleTerminal, openModelSelector } = useUIStore();
  const { sendMessage, regenerate } = useChatStore();
  
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Cmd/Ctrl + B: Toggle sidebar
      if ((e.metaKey || e.ctrlKey) && e.key === 'b') {
        e.preventDefault();
        toggleSidebar();
      }
      
      // Cmd/Ctrl + J: Toggle terminal
      if ((e.metaKey || e.ctrlKey) && e.key === 'j') {
        e.preventDefault();
        toggleTerminal();
      }
      
      // Cmd/Ctrl + K: Open model selector
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        openModelSelector();
      }
      
      // Cmd/Ctrl + Shift + R: Regenerate
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key === 'r') {
        e.preventDefault();
        regenerate();
      }
    };
    
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);
}
```

---

## 10. Persistencia

### 10.1 LocalStorage (Zustand Persist)

```typescript
// Stores persistentes
export const useConfigStore = create(
  persist<ConfigState>(
    (set) => ({
      // Estado inicial
      provider: 'openai',
      apiKeys: { openai: '', google: '', /* ... */ },
      // ...
    }),
    {
      name: 'llm-config',  // Key en localStorage
      partialize: (state) => ({
        // Solo persistir estos campos
        provider: state.provider,
        apiKeys: state.apiKeys,
        ollamaUrl: state.ollamaUrl,
        backendUrl: state.backendUrl,
        theme: state.theme,
        systemPrompt: state.systemPrompt,
      }),
    }
  )
);
```

### 10.2 Campos Persistidos

| Store | Campos Persistidos |
|-------|-------------------|
| configStore | provider, apiKeys, ollamaUrl, backendUrl, theme, systemPrompt |
| modelsStore | favorites, advancedParams |
| uiStore | panelSizes |

---

## 11. Integración con Backend

### 11.1 Estructura de Request de Chat

```typescript
interface ChatRequest {
  provider: Provider;
  api_key: string;
  model_id: string;
  conversation_id?: string;
  parent_message_id?: number;
  user_message: string;
  regenerate?: boolean;
  temperature?: number;
  top_p?: number;
  max_tokens?: number;
  tools?: ToolDefinition[];
  stream?: boolean;
  system_prompt?: string;
  auto_summarize?: boolean;
  summarizer_model?: string;
}
```

### 11.2 Eventos SSE del Chat

| Evento | Datos | Descripción |
|--------|-------|-------------|
| `message` | `{ type: 'content', chunk: string }` | Chunk de texto del LLM |
| `tool_call` | `{ type: 'tool_call', tool_call: {...} }` | LLM quiere ejecutar tool |
| `tool_executing` | `{ tool_call_id, name }` | Tool en ejecución |
| `tool_result` | `{ tool_call_id, result }` | Resultado de tool |
| `done` | `{ message_id, conversation_id, leaf_id }` | Finalizado |
| `error` | `{ code, message }` | Error |

---

## 12. Componentes UI Base (shadcn/ui)

Componentes importados de `@/components/ui/`:

- **Button**: Variantes (default, destructive, outline, ghost)
- **Input**: Input con validación
- **Textarea**: Auto-resize para chat
- **Dialog**: Modales (settings, model selector)
- **ScrollArea**: Scroll custom con scrollbar estilizado
- **Badge**: Estados, tags
- **Toggle**: Botones de toggle
- **Select**: Dropdowns
- **Tooltip**: Tooltips informativos
- **Avatar**: Avatares de usuario/bot
- **Card**: Cards para modelos
- **Tabs**: Tabs en configuración
- **Separator**: Separadores visuales

---

## 13. Estilos y Animaciones

### 13.1 Animaciones CSS

```css
/* globals.css */
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.animate-pulse {
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

.animate-spin {
  animation: spin 1s linear infinite;
}
```

### 13.2 Transiciones de Paneles

```css
/* Smooth panel transitions */
[data-panel] {
  transition: flex-basis 200ms ease-out;
}

[data-panel-resize-handle] {
  transition: background-color 150ms ease;
}
```

---

## 14. Configuración de Next.js

```typescript
// next.config.ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Optimizaciones
  reactStrictMode: true,
  
  // Configuración de imágenes
  images: {
    domains: ['avatars.githubusercontent.com'],
  },
  
  // Variables de entorno expuestas al cliente
  env: {
    NEXT_PUBLIC_BACKEND_URL: process.env.NEXT_PUBLIC_BACKEND_URL,
  },
};

export default nextConfig;
```

---

## 15. Scripts de Desarrollo

```json
// package.json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  }
}
```

### 15.1 Desarrollo

```bash
cd LLM/frontend
npm install
npm run dev
```

La aplicación estará disponible en `http://localhost:3000`.

---

## 16. Dependencias Principales

```json
{
  "dependencies": {
    "next": "16.0.10",
    "react": "^19.2.1",
    "react-dom": "^19.2.1",
    "zustand": "^5.0.6",
    "@radix-ui/react-dialog": "^1.1.14",
    "@radix-ui/react-scroll-area": "^1.2.9",
    "@radix-ui/react-select": "^2.2.5",
    "@radix-ui/react-toggle": "^1.1.9",
    "@radix-ui/react-tooltip": "^1.2.7",
    "react-markdown": "^10.1.0",
    "remark-gfm": "^4.0.1",
    "prism-react-renderer": "^2.4.1",
    "react-resizable-panels": "^2.1.7",
    "lucide-react": "^0.513.0",
    "class-variance-authority": "^0.7.1",
    "clsx": "^2.1.1",
    "tailwind-merge": "^3.3.0",
    "geist": "^1.4.1"
  },
  "devDependencies": {
    "typescript": "^5",
    "@types/react": "^19",
    "@types/node": "^22",
    "tailwindcss": "^4.1.7",
    "eslint": "^9",
    "eslint-config-next": "16.0.10"
  }
}
```

---

## 17. Arquitectura de Componentes

```
App
└── MainLayout
    ├── Header
    │   ├── Logo
    │   ├── ModelSelector (trigger)
    │   ├── ConfigToggle
    │   └── ThemeToggle
    │
    ├── ChatSidebar (collapsible)
    │   ├── NewChatButton
    │   ├── SearchInput
    │   ├── ConversationList
    │   │   └── ConversationItem (x N)
    │   └── SettingsLink
    │
    ├── ChatArea
    │   ├── MessageList
    │   │   └── MessageBubble (x N)
    │   │       ├── Avatar
    │   │       ├── MarkdownContent
    │   │       ├── CodeBlock
    │   │       ├── ToolCallBadge
    │   │       └── BranchNavigation
    │   │
    │   ├── StreamingIndicator
    │   └── ChatInput
    │       ├── TextArea
    │       ├── AttachButton
    │       └── SendButton
    │
    ├── TerminalPanel (collapsible)
    │   ├── TerminalHeader
    │   ├── TerminalOutput
    │   └── TerminalInput
    │
    └── MissionPanel (collapsible)
        ├── MissionHeader
        ├── ApprovalAlert
        ├── ObjectiveList
        │   └── ObjectiveItem (x N)
        └── ApprovalDialog (modal)

[Modals]
├── ModelSelector
│   ├── SearchInput
│   ├── FilterBar
│   └── ModelGrid
│       └── ModelCard (x N)
│
├── SettingsDialog
│   ├── ApiKeysTab
│   ├── AppearanceTab
│   └── AdvancedTab
│
└── ConfigPanel (dropdown)
    ├── ProviderSelect
    ├── ApiKeyInput
    └── SystemPromptEditor
```

---

## 18. Manejo de Errores

### 18.1 Error Boundaries

```tsx
// app/error.tsx
'use client';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center h-screen">
      <h2 className="text-2xl font-bold mb-4">Algo salió mal</h2>
      <p className="text-muted-foreground mb-4">{error.message}</p>
      <Button onClick={reset}>Intentar de nuevo</Button>
    </div>
  );
}
```

### 18.2 Errores de API

```typescript
// En los stores
try {
  const response = await api.sendMessage(request);
  // ...
} catch (error) {
  set({ 
    error: error instanceof Error ? error.message : 'Error desconocido',
    isStreaming: false,
    isLoading: false,
  });
  
  // Toast notification
  toast.error('Error al enviar mensaje');
}
```

---

## 19. Optimizaciones de Rendimiento

### 19.1 Memoización

```tsx
// Evitar re-renders innecesarios
const MessageBubble = memo(function MessageBubble({ message }: Props) {
  // ...
});

// useMemo para cálculos pesados
const filteredModels = useMemo(() => {
  return models.filter(/* ... */).sort(/* ... */);
}, [models, filters]);
```

### 19.2 Virtual Scrolling (para listas grandes)

```tsx
// Si hay muchas conversaciones
import { useVirtualizer } from '@tanstack/react-virtual';

function ConversationList() {
  const virtualizer = useVirtualizer({
    count: conversations.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => 50,
  });
  
  // ...
}
```

### 19.3 Lazy Loading

```tsx
// Cargar componentes pesados dinámicamente
const ModelSelector = dynamic(
  () => import('@/components/models/ModelSelector'),
  { loading: () => <Skeleton className="h-[600px]" /> }
);
```

---

## 20. Testing

### 20.1 Estructura Recomendada

```
__tests__/
├── components/
│   ├── MessageBubble.test.tsx
│   ├── ChatInput.test.tsx
│   └── ModelCard.test.tsx
├── hooks/
│   └── useChat.test.ts
├── services/
│   └── api.test.ts
└── stores/
    └── useStore.test.ts
```

### 20.2 Ejemplo de Test

```tsx
// __tests__/components/MessageBubble.test.tsx
import { render, screen } from '@testing-library/react';
import MessageBubble from '@/components/chat/MessageBubble';

describe('MessageBubble', () => {
  it('renders user message correctly', () => {
    render(
      <MessageBubble 
        message={{ role: 'user', content: 'Hello world' }} 
      />
    );
    
    expect(screen.getByText('Hello world')).toBeInTheDocument();
  });
  
  it('renders markdown code blocks', () => {
    render(
      <MessageBubble 
        message={{ 
          role: 'assistant', 
          content: '```python\nprint("hello")\n```' 
        }} 
      />
    );
    
    expect(screen.getByText('print("hello")')).toBeInTheDocument();
  });
});
```
