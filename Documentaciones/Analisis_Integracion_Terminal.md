# Análisis Exhaustivo: Integración Terminal Sandbox + LLM Chat

**Fecha**: 19 de diciembre de 2025  
**Contexto**: Sprint 3 - Integración LLM  
**Objetivo**: Diseñar la integración entre el sandbox terminal (Flask API) y el sistema de chat con árbol de conversación

---

## 📊 Estado Actual

### Backend Terminal (Flask - Puerto 5000)
```python
# Estructura actual en agent_api.py
SESSION_CWD = {}           # session_id -> directorio actual
SESSION_HISTORY = {}       # session_id -> [lista comandos con outputs]
JOBS = {}                  # job_id -> proceso Popen activo
```

**Capacidades actuales:**
- ✅ Ejecución asíncrona de comandos con job_id
- ✅ Persistencia de directorio por sesión (`cd` mantiene estado)
- ✅ Historial de comandos por sesión con timestamps
- ✅ Web UI administrativa (`/admin`) con logs
- ✅ Compresión inteligente de salidas repetitivas
- ✅ Jobs en background con polling de estado

### Frontend LLM (Next.js - Puerto 3000)
```typescript
// Zustand stores
useChatStore: {
  conversationId,
  messages: Message[],
  fullTree: TreeNode,
  activeLeafId,
  isStreaming
}
```

**Capacidades actuales:**
- ✅ Sistema de árbol de conversación (branches)
- ✅ Navegación entre ramas (BranchIndicator)
- ✅ Regenerate de mensajes (crea nuevos nodos)
- ✅ Streaming de respuestas
- ✅ Persistencia en backend FastAPI (SQLite)

### Backend LLM (FastAPI - Puerto 4000)
```python
# Estructura de datos
Conversation → Messages → Tree (parent-child links)
Message: {id, conversation_id, parent_id, children_ids, content, role}
```

---

## 🔴 PROBLEMA CRÍTICO: Gestión de Estado en Branches

### Escenario problemático:

```
Usuario:                            Terminal Sandbox:
┌─────────────────────────┐        ┌──────────────────────┐
│ 1. nmap 10.5.0.3        │───────▶│ CWD: /workspace      │
│    → "21, 22, 80 open"  │        │ FILES: []            │
└─────────────────────────┘        └──────────────────────┘
          │
          ▼
┌─────────────────────────┐        ┌──────────────────────┐
│ 2. mkdir exploits       │───────▶│ CWD: /workspace      │
│    cd exploits          │        │ FILES: [exploits/]   │
└─────────────────────────┘        └──────────────────────┘
          │
          ▼
┌─────────────────────────┐        ┌──────────────────────┐
│ 3. touch payload.py     │───────▶│ CWD: /workspace/     │
│                         │        │      exploits        │
│                         │        │ FILES: [payload.py]  │
└─────────────────────────┘        └──────────────────────┘

[USUARIO EDITA MENSAJE #1 Y ELIGE OTRA RAMA]

┌─────────────────────────┐        ┌──────────────────────┐
│ 1. nmap 10.5.0.3        │        │ ❌ PROBLEMA:         │
│    (mismo mensaje)      │        │                      │
└─────────────────────────┘        │ El sandbox sigue en: │
          │                        │ CWD: /workspace/     │
          ▼                        │      exploits        │
┌─────────────────────────┐        │                      │
│ 2. hydra -l admin ...   │───────▶│ Y tiene el archivo   │
│    (nueva rama)         │        │ payload.py creado    │
└─────────────────────────┘        └──────────────────────┘
                                          ⚠️ INCONSISTENTE
```

**El problema**: El terminal mantiene un estado global por `session_id`, pero el chat tiene múltiples ramas (branches) que representan historias alternativas.

---

## 💡 SOLUCIONES PROPUESTAS

### Opción 1: **Sesión por Conversación (Sencillo pero limitado)**

```typescript
session_id = conversation_id  // Una sesión por conversación
```

**Pros:**
- ✅ Implementación trivial
- ✅ No requiere cambios en el backend terminal
- ✅ Funciona para usuarios single-branch

**Contras:**
- ❌ NO resuelve el problema de branches
- ❌ Todas las ramas comparten el mismo filesystem
- ❌ Navegar entre ramas no restaura el estado del terminal

**Veredicto:** 🚫 Insuficiente para un sistema con árbol de conversación.

---

### Opción 2: **Sesión por Branch (Checkpoint Git-like)** ⭐ RECOMENDADA

```typescript
// Frontend
session_id = `${conversation_id}_leaf_${active_leaf_id}`

// Backend terminal modificado
SESSION_SNAPSHOTS = {
  "conv_123_leaf_456": {
    "cwd": "/workspace/exploits",
    "files": ["payload.py"],
    "env": {...},
    "parent_snapshot": "conv_123_leaf_455"
  }
}
```

**Implementación:**

#### A) Copy-on-Write con Overlayfs (Avanzado)
```python
# Usar overlayfs para cada branch
# Cada leaf_id tiene su propio overlay sobre el workspace base

import subprocess

def create_branch_workspace(conversation_id, leaf_id, parent_leaf_id=None):
    base_dir = "/workspace"
    branch_dir = f"/workspace_branches/{conversation_id}_{leaf_id}"
    
    if parent_leaf_id:
        parent_dir = f"/workspace_branches/{conversation_id}_{parent_leaf_id}"
        # Clonar estado del padre
        subprocess.run(["cp", "-r", parent_dir, branch_dir])
    else:
        # Crear workspace limpio
        subprocess.run(["mkdir", "-p", branch_dir])
    
    return branch_dir
```

**Pros:**
- ✅ Cada rama tiene su propio filesystem completo
- ✅ Navegar entre ramas restaura el estado exacto
- ✅ Permite experimentación paralela (explotar SSH en una rama, HTTP en otra)

**Contras:**
- ⚠️ Requiere más disco (aunque overlayfs optimiza)
- ⚠️ Mayor complejidad en backend

#### B) Snapshots Ligeros con Git (Pragmático) ⭐⭐⭐
```python
# Usar git internamente para gestionar estados

SESSION_GIT_REPOS = {}  # session_id -> path al repo git

def init_session_repo(session_id):
    repo_path = f"/workspace_sessions/{session_id}"
    os.makedirs(repo_path, exist_ok=True)
    subprocess.run(["git", "init"], cwd=repo_path)
    subprocess.run(["git", "config", "user.name", "Agent"], cwd=repo_path)
    subprocess.run(["git", "config", "user.email", "agent@tfg"], cwd=repo_path)
    return repo_path

def commit_branch_state(session_id, leaf_id):
    """Guarda el estado actual como un commit de git"""
    repo_path = SESSION_GIT_REPOS[session_id]
    subprocess.run(["git", "add", "-A"], cwd=repo_path)
    subprocess.run(
        ["git", "commit", "-m", f"State at leaf {leaf_id}"],
        cwd=repo_path
    )
    # Tag para identificar el leaf
    subprocess.run(["git", "tag", f"leaf_{leaf_id}"], cwd=repo_path)

def restore_branch_state(session_id, leaf_id):
    """Restaura el workspace al estado de un leaf específico"""
    repo_path = SESSION_GIT_REPOS[session_id]
    subprocess.run(["git", "checkout", f"leaf_{leaf_id}"], cwd=repo_path)
```

**Pros:**
- ✅ Git hace el trabajo pesado (deduplicación, compresión)
- ✅ Cada commit representa el estado de un nodo del árbol
- ✅ `git checkout` restaura todo instantáneamente
- ✅ `.git` da historial completo debuggeable
- ✅ Almacenamiento eficiente (solo diff entre ramas)

**Contras:**
- ⚠️ Requiere instalar git en el contenedor (ya está ✅)
- ⚠️ Lógica adicional para sincronizar árbol chat ↔ commits git

#### C) Snapshots de Metadata + Rollback Manual (Ligero)
```python
# Solo guardar CWD + lista de archivos creados por leaf
# Al cambiar de rama, borrar archivos creados y restaurar CWD

LEAF_METADATA = {
  "leaf_456": {
    "cwd": "/workspace/exploits",
    "created_files": ["exploits/", "exploits/payload.py"],
    "created_dirs": ["exploits"]
  }
}

def rollback_to_leaf(leaf_id):
    metadata = LEAF_METADATA[leaf_id]
    
    # 1. Borrar archivos de hojas hermanas
    for other_leaf, data in LEAF_METADATA.items():
        if other_leaf != leaf_id:
            for file in data["created_files"]:
                os.remove(file)  # Safe cleanup
    
    # 2. Restaurar CWD
    SESSION_CWD[session_id] = metadata["cwd"]
```

**Pros:**
- ✅ Muy ligero (solo metadata)
- ✅ No requiere herramientas externas
- ✅ Fácil de implementar

**Contras:**
- ❌ NO restaura contenido de archivos modificados
- ❌ Tracking manual de todos los cambios (error-prone)
- ❌ Difícil escalar si se editan archivos existentes

---

### Opción 3: **Contenedor Docker por Leaf (Aislamiento Total)**

```yaml
# docker-compose dinámico
services:
  sandbox_leaf_456:
    build: ./KaliSandbox
    volumes:
      - workspace_leaf_456:/workspace
```

**Pros:**
- ✅ Aislamiento perfecto (cada rama = contenedor independiente)
- ✅ No hay colisión de estados posible
- ✅ Puede ejecutar comandos en paralelo de verdad

**Contras:**
- ❌ Muy pesado (arrancar contenedor por cada rama)
- ❌ Tiempo de startup (~3-5s mínimo)
- ❌ Overhead de recursos (RAM, CPU)
- ❌ Complejidad en orquestación

**Veredicto:** 🚫 Overkill para el alcance del TFG.

---

## 🎯 RECOMENDACIÓN FINAL

### **Implementación Git-based Snapshots (Opción 2B)** ⭐⭐⭐

**Razones:**
1. **Balance perfecto**: Funcionalidad completa sin complejidad extrema
2. **Git es estándar**: Herramienta probada y robusta
3. **Educativo**: Los logs de git ayudan a debuggear
4. **Escalable**: Funciona igual con 5 ramas que con 50
5. **Ya disponible**: Git está instalado en el Dockerfile

### Arquitectura propuesta:

```
┌─────────────────────────────────────────────────────────────┐
│                    FRONTEND (Next.js)                       │
├─────────────────────────────────────────────────────────────┤
│  useChatStore: {                                            │
│    conversationId: "conv_123"                               │
│    activeLeafId: "msg_456"                                  │
│    fullTree: TreeNode                                       │
│  }                                                          │
│                                                             │
│  Cuando cambia activeLeafId:                                │
│  → POST /terminal/switch_branch                             │
│     { conversation_id, leaf_id }                            │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│              BACKEND TERMINAL (Flask 5000)                  │
├─────────────────────────────────────────────────────────────┤
│  SESSION_REPOS = {                                          │
│    "conv_123": "/workspace_sessions/conv_123/.git"          │
│  }                                                          │
│                                                             │
│  LEAF_STATE = {                                             │
│    "conv_123_msg_456": {                                    │
│       "commit_sha": "a1b2c3d",                              │
│       "cwd": "/workspace/exploits",                         │
│       "git_tag": "leaf_msg_456"                             │
│    }                                                        │
│  }                                                          │
│                                                             │
│  /execute:                                                  │
│    1. Verificar si hay cambios → git add + commit          │
│    2. Ejecutar comando                                      │
│    3. Auto-commit después de comando exitoso               │
│                                                             │
│  /switch_branch:                                            │
│    1. git checkout leaf_{leaf_id}                           │
│    2. Restaurar SESSION_CWD                                 │
└─────────────────────────────────────────────────────────────┘
```

### Endpoints nuevos requeridos:

```python
@app.route('/session/init', methods=['POST'])
def init_session():
    """Crea un nuevo repo git para una conversación"""
    data = request.get_json()
    conversation_id = data['conversation_id']
    
    repo_path = f"/workspace_sessions/{conversation_id}"
    os.makedirs(repo_path, exist_ok=True)
    subprocess.run(["git", "init"], cwd=repo_path, check=True)
    
    SESSION_REPOS[conversation_id] = repo_path
    
    # Commit inicial vacío
    open(f"{repo_path}/.gitkeep", "w").close()
    subprocess.run(["git", "add", ".gitkeep"], cwd=repo_path)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path)
    
    return jsonify({"status": "ok", "repo_path": repo_path})

@app.route('/session/checkpoint', methods=['POST'])
def create_checkpoint():
    """Guarda el estado actual como un checkpoint git"""
    data = request.get_json()
    conversation_id = data['conversation_id']
    leaf_id = data['leaf_id']
    parent_leaf_id = data.get('parent_leaf_id')
    
    repo_path = SESSION_REPOS[conversation_id]
    
    # Si es un nuevo branch, crear desde el padre
    if parent_leaf_id and parent_leaf_id in LEAF_STATE:
        parent_tag = f"leaf_{parent_leaf_id}"
        subprocess.run(["git", "checkout", parent_tag], cwd=repo_path)
        subprocess.run(["git", "checkout", "-b", f"branch_{leaf_id}"], cwd=repo_path)
    
    # Commit del estado actual
    subprocess.run(["git", "add", "-A"], cwd=repo_path)
    result = subprocess.run(
        ["git", "commit", "-m", f"State at leaf {leaf_id}"],
        cwd=repo_path,
        capture_output=True
    )
    
    # Tag para identificar
    subprocess.run(["git", "tag", "-f", f"leaf_{leaf_id}"], cwd=repo_path)
    
    # Guardar metadata
    commit_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_path,
        capture_output=True,
        text=True
    ).stdout.strip()
    
    LEAF_STATE[f"{conversation_id}_{leaf_id}"] = {
        "commit_sha": commit_sha,
        "cwd": SESSION_CWD.get(conversation_id, repo_path),
        "git_tag": f"leaf_{leaf_id}"
    }
    
    return jsonify({"status": "ok", "commit": commit_sha})

@app.route('/session/switch', methods=['POST'])
def switch_branch():
    """Cambia a un leaf diferente (restaura estado)"""
    data = request.get_json()
    conversation_id = data['conversation_id']
    leaf_id = data['leaf_id']
    
    repo_path = SESSION_REPOS[conversation_id]
    tag = f"leaf_{leaf_id}"
    
    # Checkout del tag
    result = subprocess.run(
        ["git", "checkout", tag],
        cwd=repo_path,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        return jsonify({
            "status": "error",
            "message": f"Branch not found: {tag}"
        }), 404
    
    # Restaurar CWD
    state_key = f"{conversation_id}_{leaf_id}"
    if state_key in LEAF_STATE:
        SESSION_CWD[conversation_id] = LEAF_STATE[state_key]["cwd"]
    else:
        SESSION_CWD[conversation_id] = repo_path
    
    return jsonify({
        "status": "ok",
        "cwd": SESSION_CWD[conversation_id]
    })
```

### Flujo de ejecución:

```
1. USUARIO ENVÍA MENSAJE
   └─> Frontend: sendMessage()
       └─> Backend LLM: POST /chat
           └─> Message creado en DB
               └─> Frontend recibe message_id (nuevo leaf)
                   └─> POST /terminal/checkpoint {leaf_id: message_id}

2. LLM EJECUTA COMANDO
   └─> Backend LLM: llama a POST /terminal/execute
       └─> Terminal ejecuta comando
           └─> Auto-commit después de comando exitoso
               └─> Respuesta con stdout/stderr

3. USUARIO NAVEGA A OTRA RAMA
   └─> Frontend: BranchIndicator.onClick()
       └─> setActiveLeafId(new_leaf_id)
           └─> useEffect detecta cambio:
               └─> POST /terminal/switch {leaf_id: new_leaf_id}
                   └─> Git checkout restaura filesystem
                       └─> SESSION_CWD actualizado
```

---

## 🔧 CAMBIOS NECESARIOS

### Backend Terminal (`agent_api.py`)

```python
# AÑADIR al inicio del archivo
import git  # pip install gitpython

SESSION_REPOS = {}      # conversation_id -> GitPython Repo object
LEAF_STATE = {}         # "conv_id_leaf_id" -> {commit, cwd, tag}

# MODIFICAR /execute para auto-commit
@app.route('/execute', methods=['POST'])
def execute_command():
    # ... código existente ...
    
    # AL FINAL, antes de return:
    conversation_id = data.get('conversation_id')
    leaf_id = data.get('leaf_id')
    
    if conversation_id and leaf_id and not is_running:
        # Auto-commit después de comando exitoso
        if return_code == 0:
            create_checkpoint_internal(conversation_id, leaf_id)
    
    return jsonify(response)

# AÑADIR funciones auxiliares
def create_checkpoint_internal(conversation_id, leaf_id):
    """Helper para crear checkpoint sin endpoint"""
    if conversation_id not in SESSION_REPOS:
        init_session_internal(conversation_id)
    
    repo = SESSION_REPOS[conversation_id]
    repo.git.add(A=True)
    try:
        repo.index.commit(f"State at leaf {leaf_id}")
        repo.create_tag(f"leaf_{leaf_id}", force=True)
    except git.exc.GitCommandError:
        pass  # No changes, skip commit
```

### Frontend Chat Area (`ChatArea.tsx`)

```typescript
// AÑADIR al inicio
import { initTerminalSession, createTerminalCheckpoint, switchTerminalBranch } from "@/services/terminal";

// MODIFICAR handleSend
const handleSend = async () => {
  // ... código existente hasta crear conversación ...
  
  if (!conversationId) {
    const newConv = await createConversation(/* ... */);
    setConversation(newConv.conversation_id);
    
    // 🆕 Inicializar sesión de terminal
    await initTerminalSession(newConv.conversation_id);
  }
  
  // ... enviar mensaje ...
  
  const assistantMsg = await sendMessage(/* ... */);
  
  // 🆕 Crear checkpoint del nuevo leaf
  await createTerminalCheckpoint(conversationId, assistantMsg.id);
};

// AÑADIR useEffect para detectar cambio de rama
useEffect(() => {
  if (activeLeafId && conversationId) {
    // Cambiar de rama en el terminal
    switchTerminalBranch(conversationId, activeLeafId);
  }
}, [activeLeafId, conversationId]);
```

### Nuevo servicio (`services/terminal.ts`)

```typescript
const TERMINAL_URL = 'http://localhost:5000';

export async function initTerminalSession(conversationId: string) {
  const response = await fetch(`${TERMINAL_URL}/session/init`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ conversation_id: conversationId }),
  });
  return response.json();
}

export async function createTerminalCheckpoint(
  conversationId: string,
  leafId: string,
  parentLeafId?: string
) {
  const response = await fetch(`${TERMINAL_URL}/session/checkpoint`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      conversation_id: conversationId,
      leaf_id: leafId,
      parent_leaf_id: parentLeafId,
    }),
  });
  return response.json();
}

export async function switchTerminalBranch(
  conversationId: string,
  leafId: string
) {
  const response = await fetch(`${TERMINAL_URL}/session/switch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      conversation_id: conversationId,
      leaf_id: leafId,
    }),
  });
  return response.json();
}
```

---

## 📝 CASOS DE USO CUBIERTOS

### ✅ Caso 1: Conversación lineal
```
Usuario: nmap 10.5.0.3
  → Checkpoint leaf_msg_1
Usuario: cd exploits && touch payload.py
  → Checkpoint leaf_msg_2 (hereda de msg_1)
```
**Comportamiento**: Funciona como sesión normal.

### ✅ Caso 2: Regenerar mensaje
```
Usuario: nmap 10.5.0.3
  → Branch A: "Puertos 21,22,80 abiertos"
  [Regenerate]
  → Branch B: "Puerto 445 crítico detectado"
```
**Comportamiento**: Ambas ramas arrancan del mismo estado (post-nmap). Los comandos subsiguientes divergen.

### ✅ Caso 3: Navegar entre ramas
```
Usuario está en Branch A (CWD: /workspace/exploits)
  [Click en Branch B]
  → git checkout leaf_branch_B
  → CWD restaurado: /workspace/
```
**Comportamiento**: El filesystem cambia completamente. Los archivos de Branch A no existen en Branch B.

### ✅ Caso 4: Múltiples chats abiertos
```
Chat 1 (conv_abc): nmap + hydra
Chat 2 (conv_xyz): sqlmap + nikto
```
**Comportamiento**: Repos git separados. Sin colisión posible.

---

## ⚠️ LIMITACIONES Y CONSIDERACIONES

### 1. **Rendimiento de Git**
- Git es rápido para archivos pequeños (<100MB)
- Si el usuario genera logs enormes (e.g., `tcpdump` durante 10 min), el repo crece
- **Solución**: Añadir `.gitignore` para logs grandes, o `git gc` periódico

### 2. **Conflictos de merge**
- NO usamos `git merge`, solo `checkout` de tags
- Cada rama es independiente (no hay merges automáticos)

### 3. **Almacenamiento**
- Cada conversación tiene su repo (~/10-50MB típico)
- Garbage collection manual necesaria para chats antiguos
- **Solución**: Endpoint `/session/cleanup` para borrar repos viejos

### 4. **Comandos interactivos (nano, vim)**
- Requieren PTY (pseudo-terminal)
- La implementación actual no soporta interactividad
- **Solución futura**: Usar `pty` de Python o contenedor con TTY

### 5. **Comandos de larga duración**
- `nmap` completo puede tardar 10+ minutos
- Durante ese tiempo, el usuario puede cambiar de rama
- **Comportamiento**: El job sigue corriendo en background, pero su output se guarda en el repo de la rama actual cuando terminó

---

## 🚀 PLAN DE IMPLEMENTACIÓN

### Fase 1: Prototipo básico (2-3 horas)
1. ✅ Añadir endpoints `/session/init`, `/checkpoint`, `/switch`
2. ✅ Integrar GitPython en `agent_api.py`
3. ✅ Crear `services/terminal.ts`
4. ✅ Test manual: Crear conversación → Ejecutar comando → Cambiar rama

### Fase 2: Integración con ChatArea (2 horas)
1. ✅ Modificar `handleSend` para crear checkpoints
2. ✅ Añadir `useEffect` para detectar cambio de `activeLeafId`
3. ✅ Test: Regenerar mensaje y verificar filesystem diverge

### Fase 3: UI y feedback (1 hora)
1. ✅ Badge visual en mensajes que ejecutaron comandos
2. ✅ Indicador de "Switching branch..." durante checkout
3. ✅ Toast notification si el checkout falla

### Fase 4: Refinamiento (1 hora)
1. ✅ Manejo de errores (git checkout falla)
2. ✅ Cleanup automático de repos antiguos
3. ✅ Documentación de uso para el usuario

**Tiempo total estimado**: 6-7 horas

---

## 🎯 MÉTRICAS DE ÉXITO

### Funcionales
- ✅ Cambiar de rama restaura el filesystem exacto
- ✅ Comandos en ramas diferentes no se interfieren
- ✅ Historial de comandos preservado por rama
- ✅ CWD se mantiene al cambiar de rama

### No funcionales
- ✅ Tiempo de switch < 500ms (git checkout es instantáneo)
- ✅ Almacenamiento < 100MB por conversación típica
- ✅ Sin memoria compartida entre chats (aislamiento)

---

## 📚 ALTERNATIVAS DESCARTADAS

### ❌ Snapshots de VM (QEMU/VirtualBox)
- Demasiado pesado (GBs por snapshot)
- Lento (10-30s por restore)
- Overkill para el alcance

### ❌ Contenedor por mensaje
- Overhead insostenible
- Startup time inaceptable
- Complejidad de orquestación

### ❌ Rollback manual (tracking de archivos)
- Error-prone
- No restaura contenido de archivos modificados
- Difícil de mantener

---

## 🔗 INTEGRACIÓN CON REQUISITOS INICIALES

### ✅ Features del frontend cubiertas:
- [x] Branch navigation con estado consistente
- [x] Regenerate con divergencia real de filesystem
- [x] Historial preservado por rama
- [x] Múltiples chats independientes

### ✅ Features del backend terminal cubiertas:
- [x] Persistencia de estado (git commits)
- [x] Aislamiento entre sesiones (repos separados)
- [x] Historial debuggeable (git log)
- [x] Rollback trivial (git checkout)

---

## 📖 REFERENCIAS

- [GitPython Docs](https://gitpython.readthedocs.io/)
- [OverlayFS Linux](https://www.kernel.org/doc/html/latest/filesystems/overlayfs.html)
- [Flask Background Tasks](https://flask.palletsprojects.com/en/2.3.x/patterns/celery/)

---

## 🎬 CONCLUSIÓN

La integración Git-based Snapshots ofrece el mejor balance entre funcionalidad, complejidad y rendimiento. Es una solución elegante que aprovecha herramientas estándar (Git) para resolver un problema complejo (estado del filesystem en árbol de conversación).

**Próximo paso**: Implementar Fase 1 del prototipo y validar con casos de uso reales.
