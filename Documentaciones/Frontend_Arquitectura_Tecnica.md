# 🏗️ Documentación Técnica del Frontend - TryHackYou

> **Versión**: 1.0  
> **Última actualización**: Enero 2026  
> **Framework**: Next.js 16 + React 19 + TypeScript + Tailwind CSS 4

---

## 📋 Índice

1. [Visión General](#visión-general)
2. [Arquitectura de Directorios](#arquitectura-de-directorios)
3. [Stack Tecnológico](#stack-tecnológico)
4. [Stores (Estado Global)](#stores-estado-global)
5. [Servicios (API Layer)](#servicios-api-layer)
6. [Componentes](#componentes)
7. [Flujos de Datos](#flujos-de-datos)
8. [Guía de Resolución de Problemas](#guía-de-resolución-de-problemas)

---

## 🎯 Visión General

Este frontend es una interfaz de chat para modelos de lenguaje (LLM) orientada a **ciberseguridad**. Permite:

- **Chat con streaming SSE** hacia múltiples proveedores (OpenAI, Google, Anthropic, DeepSeek, OpenRouter)
- **Árbol de conversaciones** con ramificaciones (editar mensaje → crea nueva rama)
- **Integración con sandbox Kali Linux** vía contenedor Docker para ejecutar comandos
- **Gestión de sesiones terminal con Git Snapshots** (cada rama del chat tiene su propio estado del filesystem)
- **Persistencia local** de configuración (API keys, preferencias) en localStorage

### Arquitectura de Alto Nivel

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND (Next.js :3000)                      │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ Stores (Zustand)                                                   │ │
│  │  ├─ configStore    → API keys, theme, system prompt                │ │
│  │  ├─ chatStore      → messages, streaming state, árbol              │ │
│  │  ├─ modelsStore    → modelos disponibles, favoritos, filtros       │ │
│  │  ├─ conversationsStore → lista de conversaciones                   │ │
│  │  ├─ terminalStore  → sesiones de terminal, jobs, conexión          │ │
│  │  └─ uiStore        → sidebar, terminal panel, modales              │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                              ↓                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ Services                                                           │ │
│  │  ├─ api.ts      → Backend LLM (:4000)                              │ │
│  │  ├─ terminal.ts → Sandbox Kali (:5000)                             │ │
│  │  └─ tools.ts    → Definiciones de herramientas para el LLM         │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                    ↓                              ↓
        ┌──────────────────┐          ┌───────────────────────┐
        │ Backend LLM      │          │ Sandbox Kali (Docker) │
        │ FastAPI :4000    │          │ Flask :5000           │
        │ - /chat (SSE)    │          │ - /execute            │
        │ - /conversations │          │ - /session/init       │
        │ - /models        │          │ - /session/checkpoint │
        └──────────────────┘          └───────────────────────┘
```

---

## 📁 Arquitectura de Directorios

```
frontend/
├── app/                        # Next.js App Router
│   ├── globals.css             # Estilos globales Tailwind
│   ├── icon.tsx                # Favicon dinámico
│   ├── layout.tsx              # Layout raíz (fuentes, metadata)
│   └── page.tsx                # Página principal → <MainLayout />
│
├── components/                 # Componentes React
│   ├── chat/                   # Área de conversación
│   │   ├── ChatArea.tsx        # ⭐ Principal: input, mensajes, streaming
│   │   ├── MessageBubble.tsx   # Renderizado de cada mensaje
│   │   └── BranchIndicator.tsx # Navegación entre ramas del árbol
│   │
│   ├── config/
│   │   └── ConfigModal.tsx     # Modal de configuración (API keys, params)
│   │
│   ├── layout/
│   │   └── MainLayout.tsx      # Layout con paneles resizables
│   │
│   ├── models/
│   │   └── ModelSelector.tsx   # Dropdown + Modal selector de modelos
│   │
│   ├── sidebar/
│   │   └── ChatSidebar.tsx     # Lista de conversaciones + nuevo chat
│   │
│   ├── terminal/
│   │   └── TerminalPanel.tsx   # Panel de actividad del sandbox
│   │
│   └── ui/                     # Componentes base (shadcn/ui)
│       ├── button.tsx, input.tsx, dialog.tsx, etc.
│
├── hooks/                      # Custom hooks (vacío actualmente)
│
├── lib/                        # Utilidades
│   ├── utils.ts                # cn() para clases condicionales
│   └── dateUtils.ts            # Formateo de fechas en español
│
├── services/                   # Comunicación con APIs
│   ├── api.ts                  # Backend LLM (FastAPI :4000)
│   ├── terminal.ts             # Sandbox Kali (Flask :5000)
│   └── tools.ts                # Schemas de tools para el LLM
│
├── store/
│   └── useStore.ts             # ⭐ Todos los stores Zustand
│
├── package.json                # Dependencias
├── tsconfig.json               # Config TypeScript
└── next.config.ts              # Config Next.js
```

---

## 🛠️ Stack Tecnológico

| Categoría | Tecnología | Versión | Propósito |
|-----------|------------|---------|-----------|
| **Framework** | Next.js | 16.0.10 | SSR, App Router |
| **UI Library** | React | 19.2.1 | Componentes |
| **Language** | TypeScript | 5.x | Tipado estático |
| **Styling** | Tailwind CSS | 4.x | Utility-first CSS |
| **State** | Zustand | 5.0.9 | Estado global ligero |
| **UI Components** | shadcn/ui + Radix | Varios | Componentes accesibles |
| **Markdown** | react-markdown + remark-gfm | 10.1.0 | Renderizado Markdown |
| **Syntax Highlight** | react-syntax-highlighter | 16.1.0 | Bloques de código |
| **Icons** | lucide-react | 0.561.0 | Iconografía |
| **Panels** | react-resizable-panels | 3.0.6 | Layout resizable |

---

## 🗃️ Stores (Estado Global)

Todos los stores están en `store/useStore.ts`. Usa **Zustand** con middleware `persist` para localStorage.

### 1. `useConfigStore` - Configuración del Usuario

```typescript
interface ConfigState {
  apiKeys: {
    openai: string;
    google: string;
    deepseek: string;
    openrouter: string;
    anthropic: string;
  };
  keyValidation: Record<Provider, { valid: boolean; error: string | null; checking: boolean }>;
  theme: 'light' | 'dark' | 'system';
  systemPrompt: string;
  backendUrl: string;  // Default: 'http://localhost:4000'
}
```

**Persiste**: `apiKeys`, `theme`, `systemPrompt`, `backendUrl`  
**Key en localStorage**: `cerebro-config`

**Uso típico**:
```typescript
const { apiKeys, setApiKey, systemPrompt } = useConfigStore();
```

---

### 2. `useChatStore` - Estado del Chat Actual

```typescript
interface ChatState {
  conversationId: string | null;
  messages: Message[];
  fullTree: TreeNode[] | null;      // Árbol completo para navegación
  activeLeafId: number | null;      // Hoja activa (último mensaje de la rama)
  
  // Streaming
  isLoading: boolean;
  isStreaming: boolean;
  currentChunk: string;             // Texto acumulado durante streaming
  streamingMessageId: number | null;
}
```

**NO persiste** (se reinicia al recargar)

**Importante**: El árbol de mensajes usa `parent_id` para representar ramificaciones. Cuando el usuario edita un mensaje, se crea un nuevo nodo con el mismo `parent_id`, creando una bifurcación.

---

### 3. `useModelsStore` - Modelos LLM

```typescript
interface ModelsState {
  models: Model[];
  selectedModel: Model | null;
  favorites: string[];              // IDs de modelos favoritos
  isLoadingModels: boolean;
  
  filters: {
    sorting: 'default' | 'ranking' | 'context';
    groupBy: 'none' | 'provider';
    onlyFree: boolean;              // Solo modelos gratis de OpenRouter
  };
  
  advancedParams: {
    temperature: number | null;     // null = usar default del proveedor
    top_p: number | null;
    max_tokens: number | null;
  };
  
  modelsUsingDefaults: string[];    // Modelos que ignoran params avanzados
}
```

**Persiste**: `favorites`, `selectedModel`, `filters`, `advancedParams`, `modelsUsingDefaults`  
**Key en localStorage**: `cerebro-models`

---

### 4. `useConversationsStore` - Lista de Conversaciones

```typescript
interface ConversationsState {
  conversations: Conversation[];
  isLoading: boolean;
}
```

**NO persiste** (se carga del backend al iniciar)

---

### 5. `useTerminalStore` - Sesiones del Sandbox

```typescript
interface TerminalState {
  sessions: Record<string, TerminalSession>;  // conv_id → sesión
  runningJobs: TerminalJob[];
  isConnected: boolean;
  lastError: string | null;
}

interface TerminalSession {
  conversationId: string;
  initialized: boolean;
  repoPath?: string;      // /workspace_sessions/{conv_id}
  currentLeafId: number | null;
}
```

**NO persiste** (estado efímero de conexión)

---

### 6. `useUIStore` - Estado de la Interfaz

```typescript
interface UIState {
  isSidebarOpen: boolean;
  isTerminalOpen: boolean;
  isConfigModalOpen: boolean;
  isModelSelectorOpen: boolean;
}
```

**NO persiste**

---

## 🌐 Servicios (API Layer)

### `services/api.ts` - Backend LLM

URL base: `useConfigStore.backendUrl` (default `http://localhost:4000`)

| Función | Endpoint | Descripción |
|---------|----------|-------------|
| `checkHealth()` | GET `/health` | Verificar servidor |
| `validateApiKeys(keys)` | POST `/health/keys` | Validar API keys |
| `createConversation(data)` | POST `/conversations` | Nueva conversación |
| `getConversations()` | GET `/conversations` | Listar conversaciones |
| `getConversationThread(id)` | GET `/conversations/{id}/thread` | Mensajes de rama activa |
| `getConversationTree(id)` | GET `/conversations/{id}/tree` | Árbol completo |
| `setActiveLeaf(convId, leafId)` | PATCH `/conversations/{id}/active-leaf` | Cambiar rama |
| `sendMessage(request)` | POST `/chat` | Chat sin streaming |
| `sendMessageStream(request, callbacks)` | POST `/chat` + SSE | Chat con streaming |
| `discoverModels(request)` | POST `/models/discover` | Obtener modelos |

#### Streaming SSE

`sendMessageStream()` maneja eventos:
- `type: 'content'` → Chunk de texto
- `type: 'tool_call'` → LLM quiere ejecutar herramienta
- `type: 'tool_executing'` → Tool ejecutándose en backend
- `type: 'tool_result'` → Resultado de la tool
- `type: 'done'` → Fin del mensaje
- `type: 'error'` → Error

---

### `services/terminal.ts` - Sandbox Kali

URL base: `http://localhost:5000` (hardcoded)

| Función | Endpoint | Descripción |
|---------|----------|-------------|
| `checkTerminalHealth()` | GET `/health` | Estado del sandbox |
| `initTerminalSession(convId)` | POST `/session/init` | Crear repo git |
| `createCheckpoint(convId, leafId, parentLeafId)` | POST `/session/checkpoint` | Commit + tag |
| `switchBranch(convId, leafId)` | POST `/session/switch` | Git checkout |
| `getSessionInfo(convId)` | GET `/session/info/{id}` | Info de sesión |
| `executeCommand(request)` | POST `/execute` | Ejecutar comando |
| `getJobStatus(jobId)` | GET `/status/{id}` | Estado de job |
| `cancelJob(jobId)` | POST `/cancel/{id}` | Detener job |
| `getRunningJobs()` | GET `/admin/api/running` | Jobs activos |

---

### `services/tools.ts` - Definiciones de Herramientas

Define los schemas de tools que se envían al LLM:

```typescript
const EXECUTE_COMMAND_TOOL = {
  type: "function",
  function: {
    name: "execute_command",
    description: "Executes a shell command in a Kali Linux sandbox...",
    parameters: {
      properties: {
        command: { type: "string" },
        wait_time: { type: "number", default: 5 },
        exit_time: { type: "number", default: null }
      },
      required: ["command"]
    }
  }
};
```

`getToolsForAPI()` retorna array de tools para incluir en peticiones al LLM.

---

## 🧩 Componentes

### `MainLayout.tsx` - Layout Principal

**Ubicación**: `components/layout/MainLayout.tsx`  
**Responsabilidad**: Estructura de 3 columnas con paneles resizables

```
┌────────────────┬────────────────────────────┬──────────────┐
│  ChatSidebar   │       ChatArea             │ TerminalPanel│
│  (20% ancho)   │     (55-76% ancho)         │  (25% ancho) │
│  Lista chats   │  Header + Messages + Input │  Actividad   │
│  Nuevo chat    │                            │  Jobs        │
│                │                            │  Sesión      │
└────────────────┴────────────────────────────┴──────────────┘
```

**Usa**: `ResizablePanelGroup` de `react-resizable-panels`

**Header del Chat** contiene:
- `ModelSelector` (dropdown de modelos)
- Botón toggle terminal
- Botón configuración

---

### `ChatArea.tsx` - Área de Chat (⭐ COMPONENTE PRINCIPAL)

**Ubicación**: `components/chat/ChatArea.tsx`  
**Tamaño**: ~827 líneas  
**Responsabilidad**: Toda la lógica de chat

#### Estados locales:
```typescript
const [input, setInput] = useState("");           // Texto del input
const [error, setError] = useState<string | null>(null);
const [paramErrorModel, setParamErrorModel] = useState<string | null>(null);
```

#### Funciones principales:

| Función | Descripción |
|---------|-------------|
| `handleSend()` | Envía mensaje nuevo, crea conversación si no existe |
| `handleRegenerateMessage(id)` | Regenera respuesta del asistente (nueva rama) |
| `handleEditMessage(id, content)` | Edita mensaje del usuario (crea rama) |
| `handleStop()` | Cancela streaming actual |

#### Flujo de `handleSend()`:

1. Verificar API key y modelo seleccionado
2. Si no hay conversación → `createConversation()`
3. Agregar mensaje user temporal a UI
4. Agregar mensaje assistant vacío (para streaming)
5. Llamar `sendMessageStream()` con callbacks:
   - `onMessage` → `appendChunk()`
   - `onToolCall` → Abrir terminal panel
   - `onDone` → Recargar thread, actualizar árbol, crear checkpoint
   - `onError` → Mostrar error parseado

#### useEffects importantes:

```typescript
// Verificar conexión con sandbox cada 30s
useEffect(() => { checkTerminalHealth(); ... }, []);

// Inicializar sesión de terminal cuando cambia conversación
useEffect(() => { initTerminalSession(conversationId); }, [conversationId]);

// Detectar cambios de branch para hacer switchBranch()
useEffect(() => { switchBranch(conversationId, activeLeafId); }, [activeLeafId]);
```

---

### `MessageBubble.tsx` - Burbuja de Mensaje

**Ubicación**: `components/chat/MessageBubble.tsx`  
**Responsabilidad**: Renderizar un mensaje individual

**Features**:
- Markdown con GFM (tablas, listas, etc.)
- Syntax highlighting para código
- Botones: Copiar, Editar (user), Regenerar (assistant)
- Indicador de branches si hay hermanos
- Expansión de tool_calls

**Props**:
```typescript
interface MessageBubbleProps {
  message: Message;
  isStreaming?: boolean;
  streamContent?: string;
  onEdit?: (messageId: number, newContent: string) => void;
  onRegenerate?: (messageId: number) => void;
}
```

---

### `BranchIndicator.tsx` - Navegación de Ramas

**Ubicación**: `components/chat/BranchIndicator.tsx`  
**Responsabilidad**: Mostrar y navegar entre ramas hermanas

Cuando un mensaje tiene hermanos (mismo `parent_id`), muestra:
- Badge `[2/3]` indicando posición
- Flechas ← → para navegar
- Popover con lista de ramas

Al cambiar de rama:
1. Encuentra la hoja más profunda de esa rama
2. Llama a `setActiveLeaf()` en backend
3. Recarga el thread

---

### `ChatSidebar.tsx` - Sidebar de Conversaciones

**Ubicación**: `components/sidebar/ChatSidebar.tsx`  
**Responsabilidad**: Lista de conversaciones y navegación

**Features**:
- Botón "Nueva conversación" → `resetChat()`
- Lista agrupada por fecha (Hoy, Ayer, Esta semana, Anteriores)
- Click en conversación → `handleSelectConversation(id)`
- Botón eliminar → `deleteConversation()`
- Modo colapsado (solo iconos)

---

### `ModelSelector.tsx` - Selector de Modelos

**Ubicación**: `components/models/ModelSelector.tsx`  
**Responsabilidad**: Seleccionar modelo LLM

**Dos modos**:
1. **Dropdown rápido**: Top 5 + favoritos
2. **Modal completo**: Búsqueda, filtros, ordenación

**Filtros**:
- Por proveedor (tabs)
- Solo favoritos
- Solo gratis (OpenRouter)
- Ordenación: ELO, contexto, default

**Búsqueda fuzzy**:
```typescript
function fuzzyMatch(text, query) {
  // Tolera espacios: "gemini 2.5" encuentra "gemini-2.5-pro"
}
```

---

### `ConfigModal.tsx` - Modal de Configuración

**Ubicación**: `components/config/ConfigModal.tsx`  
**Responsabilidad**: Configuración del usuario

**Tabs**:
1. **API Keys**: Input por proveedor + botón validar
2. **Instrucciones**: System prompt editable
3. **Servidor**: URL del backend
4. **Avanzados**: Temperature, Top P, Max Tokens, filtro gratis

**Validación de keys**: Llama a `POST /health/keys` y muestra badges (válida/inválida).

---

### `TerminalPanel.tsx` - Panel del Sandbox

**Ubicación**: `components/terminal/TerminalPanel.tsx`  
**Responsabilidad**: Mostrar actividad del sandbox Kali

**Tabs**:
1. **Actividad**: Tool calls y responses de la conversación
2. **Jobs**: Procesos en ejecución con botón "Stop"
3. **Sesión**: Estado de conexión, workspace git, archivos

**Polling**: Cada 2 segundos si hay jobs corriendo.

---

## 🔄 Flujos de Datos

### Flujo 1: Enviar Mensaje Nuevo

```
1. Usuario escribe en textarea y presiona Enter
   ↓
2. handleSend() en ChatArea
   ├─ Si no hay conversación → createConversation()
   ├─ initTerminalSession() (si sandbox disponible)
   ↓
3. Agregar mensaje user temporal a UI (optimistic update)
   ↓
4. sendMessageStream() con stream=true
   ├─ SSE: onMessage → appendChunk() → UI actualiza
   ├─ SSE: onToolCall → setTerminalOpen(true)
   ├─ SSE: onToolExecuting → log en consola
   ├─ SSE: onToolResult → log en consola
   └─ SSE: onDone →
       ├─ getConversationThread() → setMessages()
       ├─ getConversationTree() → setFullTree()
       └─ createCheckpoint() (sandbox)
```

### Flujo 2: Navegar a Otra Rama

```
1. Usuario hace click en BranchIndicator
   ↓
2. switchToBranch() encuentra hoja de rama destino
   ↓
3. setActiveLeaf() → PATCH /conversations/{id}/active-leaf
   ↓
4. getConversationThread() → setMessages() (nueva rama)
   ↓
5. useEffect detecta cambio de activeLeafId
   ↓
6. switchBranch() → POST /session/switch (sandbox)
   ↓
7. Git checkout restaura filesystem de esa rama
```

### Flujo 3: Tool Call (LLM → Sandbox)

```
1. LLM decide usar execute_command
   ↓
2. Backend recibe tool_call, ejecuta en sandbox
   ├─ SSE: tool_executing → "Ejecutando nmap..."
   ↓
3. Sandbox ejecuta comando, retorna output
   ↓
4. Backend crea mensaje role='tool' con resultado
   ├─ SSE: tool_result → resultado en consola
   ↓
5. LLM continúa generando respuesta
   ├─ SSE: content → chunks de texto
   └─ SSE: done → fin del mensaje
```

---

## 🔧 Guía de Resolución de Problemas

### Problema: "No hay API key configurada"
**Archivo**: `components/chat/ChatArea.tsx`  
**Causa**: `getApiKey()` retorna null  
**Solución**: Verificar `useConfigStore.apiKeys[provider]`

---

### Problema: Streaming no funciona
**Archivo**: `services/api.ts` → `sendMessageStream()`  
**Causa**: Error en parsing de SSE  
**Debug**: Ver consola del navegador, buscar errores en `JSON.parse(jsonStr)`

---

### Problema: Terminal desconectado
**Archivo**: `components/chat/ChatArea.tsx` → `useEffect` de health check  
**Causa**: Flask no responde en `:5000`  
**Debug**: `curl http://localhost:5000/health`

---

### Problema: Branches no funcionan
**Archivos**: 
- `components/chat/BranchIndicator.tsx`
- `services/api.ts` → `setActiveLeaf()`  
**Causa**: `fullTree` no se actualiza  
**Debug**: Verificar respuesta de `GET /conversations/{id}/tree`

---

### Problema: Modelos no cargan
**Archivo**: `components/models/ModelSelector.tsx` → `loadModels()`  
**Causa**: No hay API keys o backend no responde  
**Debug**: Verificar `POST /models/discover` en Network tab

---

### Problema: Configuración no persiste
**Archivo**: `store/useStore.ts`  
**Causa**: Error en `persist` middleware  
**Debug**: Ver `localStorage.getItem('cerebro-config')`

---

### Problema: Tool calls no aparecen
**Archivo**: `components/terminal/TerminalPanel.tsx`  
**Causa**: `message.tool_calls` viene como string en vez de array  
**Fix**: `parseToolCalls()` en `MessageBubble.tsx` maneja ambos formatos

---

## 📝 Notas para IAs

### Dónde buscar cada cosa:

| Necesidad | Archivo |
|-----------|---------|
| Cambiar lógica de envío de mensajes | `components/chat/ChatArea.tsx` |
| Modificar cómo se renderizan mensajes | `components/chat/MessageBubble.tsx` |
| Agregar nueva API key/proveedor | `store/useStore.ts` + `components/config/ConfigModal.tsx` |
| Modificar comunicación con backend | `services/api.ts` |
| Modificar comunicación con sandbox | `services/terminal.ts` |
| Agregar nueva tool para el LLM | `services/tools.ts` |
| Cambiar layout general | `components/layout/MainLayout.tsx` |
| Modificar selector de modelos | `components/models/ModelSelector.tsx` |
| Cambiar sidebar | `components/sidebar/ChatSidebar.tsx` |
| Modificar panel terminal | `components/terminal/TerminalPanel.tsx` |

### Convenciones del código:

1. **Componentes**: `"use client"` al inicio (todos son client components)
2. **Estilos**: `cn()` de `lib/utils.ts` para clases condicionales
3. **Estado**: Zustand stores, no useState para estado compartido
4. **Tipos**: Definidos en `store/useStore.ts`
5. **Iconos**: `lucide-react`
6. **UI base**: `components/ui/*` (shadcn/ui)

### URLs importantes:

- Frontend: `http://localhost:3000`
- Backend LLM: `http://localhost:4000`
- Sandbox Kali: `http://localhost:5000`
- Admin Sandbox: `http://localhost:5000/admin`

---

## 🏷️ Versiones y Compatibilidad

Este documento refleja el estado del frontend a enero 2026. Principales versiones:

- Next.js 16.0.10 (App Router)
- React 19.2.1
- Zustand 5.0.9
- Tailwind CSS 4.x

La arquitectura está diseñada para:
- Soportar múltiples proveedores de LLM
- Manejar conversaciones ramificadas (árbol de mensajes)
- Integrar con un sandbox de ejecución de comandos
- Persistir configuración del usuario localmente
