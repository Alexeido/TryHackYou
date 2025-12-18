# 📐 Arquitectura Frontend - TFG Ciberseguridad

> **Versión:** 2.0 (Revisada)  
> **Fecha:** 17 Diciembre 2025

---

## 1. Stack Tecnológico

### Tecnologías Principales

| Capa | Tecnología | ¿Qué hace? |
|:-----|:-----------|:-----------|
| **Framework** | Next.js 14 (App Router) | Framework de React con enrutamiento automático |
| **UI Components** | Shadcn/UI | Componentes pre-diseñados (botones, modales, etc.) |
| **Estilos** | Tailwind CSS | Clases CSS directamente en el HTML |
| **Iconos** | Lucide React | Iconos SVG bonitos |
| **Estado Global** | Zustand | Guarda datos que necesitan todos los componentes |
| **Markdown** | React Markdown | Renderiza `**negrita**` como **negrita** |

### Tecnologías Descartadas (Simplificamos)

| Tecnología | Decisión | Razón |
|:-----------|:---------|:------|
| **TanStack Query** | ❌ NO usar | Añade complejidad. Usaremos `fetch()` normal con `useState` |
| **Axios** | ❌ NO usar | `fetch()` nativo es suficiente para nuestro caso |

> **Nota:** TanStack Query y Axios son útiles en proyectos grandes, pero para este TFG añaden complejidad sin beneficio real. Mantenemos el stack simple.

---

## 2. Arquitectura de Interfaz (3 Columnas)

### Estructura Visual

```
┌─────────────────────────────────────────────────────────────────────┐
│                           HEADER                                     │
│  [≡] TFG Cyber Agent    │ 🟢 gemini-2.0-flash ▼ 🔍 │    [⚙️]        │
├────────────┬────────────────────────────────┬───────────────────────┤
│  SIDEBAR   │         CHAT AREA              │    TERMINAL/LOGS      │
│   (20%)    │          (50-80%)              │       (0-30%)         │
│            │                                │                       │
│ [+ Nuevo]  │  ┌─────────────────────────┐   │  Inicialmente oculto  │
│            │  │ 👤 Usuario:             │   │                       │
│ ─ Hoy ──── │  │ Escanea el puerto 80    │   │  Se abre si hay       │
│ • Chat 1   │  └─────────────────────────┘   │  tool_calls           │
│ • Chat 2   │                                │                       │
│            │  ┌─────────────────────────┐   │  ┌─────────────────┐  │
│ ─ Ayer ─── │  │ 🤖 Asistente:           │   │  │ $ nmap -p 80... │  │
│ • Chat 3   │  │ Ejecutando nmap...      │   │  │ PORT  STATE     │  │
│            │  └─────────────────────────┘   │  │ 80    open      │  │
│            │                                │   └─────────────────┘  │
│            │  ┌─────────────────────────┐   │                       │
│            │  │ 📝 Escribe tu mensaje...│   │                       │
│            │  └─────────────────────────┘   │                       │
└────────────┴────────────────────────────────┴───────────────────────┘
```

---

## 3. Sistema de Selección de Modelos (DUAL)

El header tiene **dos formas** de seleccionar modelo:

### A. Selector Rápido (Dropdown)

- **Trigger:** Click en el nombre del modelo actual (`gemini-2.0-flash ▼`)
- **Comportamiento:** Dropdown simple con los modelos **favoritos** del usuario
- **Contenido:** Máximo 5-7 modelos marcados como favoritos
- **Uso:** Cambio rápido entre modelos frecuentes

```
┌──────────────────────────┐
│ ★ gemini-2.0-flash       │  ← Actual (highlighted)
│ ★ gpt-4o                 │
│ ★ claude-3.5-sonnet      │
│ ★ deepseek-chat          │
├──────────────────────────┤
│ 🔍 Ver todos los modelos │
└──────────────────────────┘
```

### B. Selector Avanzado (Modal Completo)

- **Trigger:** Click en el icono de lupa (🔍) O en "Ver todos los modelos"
- **Comportamiento:** Abre un Dialog/Modal grande
- **Contenido:**
  - Barra de búsqueda
  - Filtros (por proveedor, por ranking, por contexto)
  - Lista completa de modelos con info detallada
  - Botón de estrella para añadir/quitar de favoritos

```
┌─────────────────────────────────────────────────────────────────┐
│  🔍 Selector de Modelos                                    [X]  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Buscar: [________________________] 🔍                          │
│                                                                 │
│  Ordenar: [Ranking ▼]    Agrupar: [Por proveedor ▼]            │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ ⭐ OpenAI                                                 │  │
│  │   ├─ gpt-4o          │ ELO: 1287 │ 128K ctx │ $5/1M      │  │
│  │   ├─ gpt-4o-mini     │ ELO: 1273 │ 128K ctx │ $0.15/1M   │  │
│  │   └─ o1-preview      │ ELO: 1350 │ 128K ctx │ $15/1M     │  │
│  │                                                           │  │
│  │ ☆ Google                                                  │  │
│  │   ├─ gemini-2.0-flash │ ELO: 1354 │ 1M ctx  │ FREE       │  │
│  │   └─ gemini-1.5-pro   │ ELO: 1300 │ 2M ctx  │ $1.25/1M   │  │
│  │                                                           │  │
│  │ ☆ DeepSeek                                                │  │
│  │   └─ deepseek-chat    │ ELO: 1280 │ 64K ctx │ $0.14/1M   │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  [Cancelar]                                      [Seleccionar]  │
└─────────────────────────────────────────────────────────────────┘
```

### Gestión de Favoritos

- **Almacenamiento:** `localStorage` (array de model_ids)
- **Estructura:** `["gpt-4o", "gemini-2.0-flash", "deepseek-chat"]`
- **Límite sugerido:** 7 favoritos máximo
- **Default:** Si no hay favoritos, mostrar los 3 con mejor ranking

---

## 4. Gestión de Datos

### Separación de Responsabilidades

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Next.js)                        │
│                                                                  │
│   localStorage (Navegador)                                       │
│   ├─ api_keys: { openai: "sk-...", google: "AIza..." }          │
│   ├─ favorite_models: ["gpt-4o", "gemini-2.0-flash"]            │
│   ├─ ui_preferences: { theme: "dark" }                          │
│   └─ system_prompt: "Eres un agente de ciberseguridad..."       │
│                                                                  │
└──────────────────────────────────┬──────────────────────────────┘
                               │ HTTP (fetch)
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      BACKEND (FastAPI + Python)                  │
│                                                                  │
│   SQLite (Servidor)                                              │
│   ├─ conversations: { id, title, created_at, updated_at }       │
│   └─ messages: { id, conversation_id, role, content, ... }      │
│                                                                  │
│   Endpoints:                                                     │
│   ├─ POST /models/discover    → Lista modelos                   │
│   ├─ POST /chat               → Envía mensaje (ya existe)       │
│   ├─ POST /conversations      → Crea conversación (NUEVO)       │
│   ├─ GET  /conversations      → Lista conversaciones (NUEVO)    │
│   ├─ GET  /conversations/{id} → Historial completo (NUEVO)      │
│   └─ DELETE /conversations/{id} → Borra conversación (NUEVO)    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### ¿Por qué la DB está en el Backend?

1. **Persistencia real:** Los datos no se pierden al borrar caché del navegador
2. **Acceso multi-dispositivo:** El mismo usuario puede ver sus chats desde otro PC
3. **Seguridad:** El historial no está expuesto en el navegador
4. **Simplicidad:** Un solo lugar para guardar datos (Python ya tiene SQLite integrado)

---

## 5. Modal de Configuración

El botón ⚙️ abre un Dialog con pestañas:

### Pestaña 1: Apariencia
- Toggle Modo Oscuro / Claro
- (Futuro: tamaño de fuente)

### Pestaña 2: Instrucciones del Sistema
- Textarea grande para el `SYSTEM_PROMPT`
- Placeholder con ejemplo: "Eres un experto en ciberseguridad..."
- Botón "Restaurar por defecto"

### Pestaña 3: API Keys
- Input tipo `password` para cada proveedor:
  - OpenAI
  - Google (Gemini)
  - DeepSeek
  - OpenRouter
  - Anthropic
- Botón "Guardar" (persiste en localStorage)
- Indicador visual de qué keys están configuradas (✓/✗)

---

## 6. Componentes Shadcn/UI a Usar

| Componente | Uso |
|:-----------|:----|
| `ResizablePanelGroup` | Las 3 columnas ajustables |
| `ScrollArea` | Listas con scroll bonito |
| `Dialog` | Modal de configuración y selector de modelos |
| `Tabs` | Pestañas dentro del modal de config |
| `DropdownMenu` | Selector rápido de modelos |
| `Switch` | Toggle modo oscuro |
| `Card` | Mensajes del chat |
| `Badge` | Indicador del modelo activo |
| `Input` | Campos de texto y búsqueda |
| `Button` | Botones varios |
| `Command` | Búsqueda con filtrado (selector avanzado) |

---

## 7. Arquitectura Preparada para Streaming (Futuro)

Aunque la v1 no tendrá streaming, diseñamos pensando en él:

### Estructura del Estado de Mensajes

```typescript
interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  isStreaming?: boolean;  // ← Para futuro streaming
  tool_calls?: ToolCall[];
  created_at: string;
}

interface ChatState {
  messages: Message[];
  isLoading: boolean;
  
  // Métodos preparados para streaming
  addMessage: (msg: Message) => void;
  updateLastMessage: (content: string) => void;  // ← Para append de chunks
  setStreaming: (id: string, status: boolean) => void;
}
```

### Flujo Actual (Sin Streaming)
1. Usuario envía mensaje
2. `isLoading = true`, se muestra spinner
3. Esperamos respuesta completa del backend
4. Añadimos mensaje del asistente
5. `isLoading = false`

### Flujo Futuro (Con Streaming)
1. Usuario envía mensaje
2. Añadimos mensaje vacío con `isStreaming = true`
3. Recibimos chunks via SSE
4. `updateLastMessage()` va concatenando
5. Chunk final: `isStreaming = false`

---

## 8. Manejo de Errores

### Errores a Detectar

| Error | Detección | UX |
|:------|:----------|:---|
| Backend caído | `fetch` falla con network error | Toast: "No se puede conectar al servidor" |
| API Key inválida | Backend devuelve 401/403 | Toast: "API Key inválida para [proveedor]" |
| Rate limiting | Backend devuelve 429 | Toast: "Demasiadas peticiones. Espera X segundos" |
| Modelo no disponible | Backend devuelve 404 | Toast: "El modelo ya no está disponible" |

### Implementación Simple

```typescript
async function sendMessage(content: string) {
  try {
    const res = await fetch(`${API_URL}/chat`, { ... });
    
    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.detail || 'Error desconocido');
    }
    
    return await res.json();
  } catch (e) {
    if (e.message.includes('fetch')) {
      showToast('error', 'No se puede conectar al servidor');
    } else {
      showToast('error', e.message);
    }
  }
}
```

---

## 9. Dockerización

### Variables de Entorno

```env
# .env.local (desarrollo)
NEXT_PUBLIC_API_URL=http://localhost:8000

# .env.production (docker)
NEXT_PUBLIC_API_URL=http://backend:8000
```

### Dockerfile (Multi-stage)

```dockerfile
# Stage 1: Build
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: Run
FROM node:20-alpine AS runner
WORKDIR /app
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000
CMD ["node", "server.js"]
```

---

## 10. Resumen de Trabajo Frontend

### Componentes a Crear

1. **Layout Principal** (`MainLayout.tsx`) - ✅ Ya existe base
2. **Sidebar** (`ChatSidebar.tsx`) - Lista de conversaciones
3. **ChatArea** (`ChatArea.tsx`) - Mensajes + Input
4. **ModelDropdown** (`ModelDropdown.tsx`) - Selector rápido
5. **ModelSelectorModal** (`ModelSelectorModal.tsx`) - Selector completo
6. **ConfigModal** (`ConfigModal.tsx`) - Configuración
7. **TerminalPanel** (`TerminalPanel.tsx`) - Logs de tools

### Stores Zustand

1. **chatStore** - Mensajes, conversación activa
2. **configStore** - API Keys, theme, system prompt
3. **modelsStore** - Lista de modelos, favoritos, modelo activo