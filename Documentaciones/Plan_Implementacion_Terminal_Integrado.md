# Plan de Implementación: Terminal Integrado con Git + Persistent Storage

**Fecha**: 19 diciembre 2025  
**Sprint**: 3 - Integración LLM  
**Objetivo**: Sistema terminal con branches git + storage persistente + UI integrada  
**Estado**: ✅ Fases 0, 1, 2 y 3 completadas

---

## 📊 Estado Actual vs Objetivo

| Aspecto | Estado Actual | Estado Objetivo | Estado |
|---------|---------------|-----------------|--------|
| **Organización** | session_id global | conversation_id → repo git dedicado | ✅ |
| **Branches** | ❌ No soportado | ✅ leaf_id → git tag/commit | ✅ |
| **Persistent** | ❌ No existe | ✅ /workspace_persistent compartido | ✅ |
| **UI Admin** | ✅ Simple (todas las sesiones mezcladas) | ✅ Filtro por conversación | ✅ |
| **Tracking Jobs** | ✅ Global JOBS dict | ✅ Jobs asociados a conversation_id | ✅ |
| **Frontend UI** | ❌ No integrado | ✅ Terminal embebido en chat | ✅ |

---

## 🏗️ Arquitectura Objetivo

```
┌─────────────────────────────────────────────────────────────┐
│                 FRONTEND (Next.js 3000)                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ ChatArea (principal)                                 │   │
│  │  ├─ Messages                                         │   │
│  │  ├─ BranchIndicator                                  │   │
│  │  └─ TerminalPanel (nuevo) ↔ localhost:5000          │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↓ REST API
┌─────────────────────────────────────────────────────────────┐
│              BACKEND TERMINAL (Flask 5000)                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ WORKSPACE LAYOUT:                                    │   │
│  │                                                      │   │
│  │ /workspace_sessions/                                 │   │
│  │   ├── conv_abc123/          # Chat 1                │   │
│  │   │   ├── .git/             # Git repo              │   │
│  │   │   ├── nmap_results.txt                          │   │
│  │   │   └── exploits/                                 │   │
│  │   └── conv_xyz456/          # Chat 2                │   │
│  │       └── .git/                                     │   │
│  │                                                      │   │
│  │ /workspace_persistent/      # Compartido todos      │   │
│  │   ├── INVENTORY.md          # Índice LLM-readable   │   │
│  │   ├── tools/                                        │   │
│  │   │   ├── sqlmap/                                   │   │
│  │   │   └── metasploit/                               │   │
│  │   ├── wordlists/                                    │   │
│  │   └── downloads/                                    │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  DATA STRUCTURES:                                           │
│  ├─ CONVERSATION_REPOS: {conv_id → GitRepo}                │
│  ├─ LEAF_COMMITS: {conv_id_leaf_id → commit_sha}           │
│  ├─ JOBS_BY_CONV: {conv_id → [job_ids]}                    │
│  └─ SESSION_CWD: {conv_id → current_dir}                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 📦 FASE 0: Persistent Storage (1.5h)

### Objetivo
Crear carpeta compartida para herramientas pesadas que persisten entre chats.

### Cambios

#### 1. Dockerfile (añadir al final)
```dockerfile
# Crear carpeta persistent
RUN mkdir -p /workspace_persistent/tools && \
    mkdir -p /workspace_persistent/wordlists && \
    mkdir -p /workspace_persistent/downloads && \
    chmod -R 777 /workspace_persistent
```

#### 2. docker-compose.yml
```yaml
services:
  attacker:
    # ... config existente ...
    volumes:
      - ./script:/app
      - persistent_storage:/workspace_persistent  # NUEVO

volumes:
  persistent_storage:  # NUEVO: persiste entre docker compose down
```

#### 3. agent_api.py: Inicialización
```python
PERSISTENT_DIR = "/workspace_persistent"
INVENTORY_PATH = f"{PERSISTENT_DIR}/INVENTORY.md"

def init_persistent_storage():
    """Crea INVENTORY.md si no existe"""
    os.makedirs(f"{PERSISTENT_DIR}/tools", exist_ok=True)
    os.makedirs(f"{PERSISTENT_DIR}/downloads", exist_ok=True)
    os.makedirs(f"{PERSISTENT_DIR}/wordlists", exist_ok=True)
    
    if not os.path.exists(INVENTORY_PATH):
        with open(INVENTORY_PATH, "w") as f:
            f.write("""# 🗂️ Persistent Tools Inventory

Last updated: (auto)

## 📦 Installed Tools

(None yet - LLM will populate this)

## 🔄 Usage

Before downloading tools >10MB, check this file first.
If tool exists, create symlink: `ln -s /workspace_persistent/tools/TOOL_NAME .`
""")

# Al inicio de app
if __name__ == '__main__':
    init_persistent_storage()
    app.run(...)
```

#### 4. llm.md: Actualizar documentación
```markdown
## Persistent Storage

Large tools (>10MB) should be installed in `/workspace_persistent/tools/`.

**Workflow:**
1. Check inventory: `cat /workspace_persistent/INVENTORY.md`
2. If tool exists: `ln -s /workspace_persistent/tools/sqlmap .`
3. If not: Install to persistent and update INVENTORY.md

**Update inventory manually:**
```bash
echo "### sqlmap v1.7.12" >> /workspace_persistent/INVENTORY.md
echo "Path: /workspace_persistent/tools/sqlmap" >> /workspace_persistent/INVENTORY.md
```
```

### Testing
```bash
docker compose down -v  # Borrar volúmenes
docker compose build
docker compose up -d
docker exec agente-tfg ls -la /workspace_persistent
# Debe mostrar: tools/, wordlists/, downloads/, INVENTORY.md
```

---

## 📦 FASE 1: Git Snapshots (3h)

### Objetivo
Cada conversación tiene su repo git. Cada leaf (mensaje) es un commit.

### Nuevas estructuras de datos

```python
import git  # pip install gitpython
from pathlib import Path

SESSIONS_BASE = "/workspace_sessions"
CONVERSATION_REPOS = {}  # {conv_id: git.Repo object}
LEAF_COMMITS = {}        # {f"{conv_id}_{leaf_id}": commit_sha}
JOBS_BY_CONV = {}        # {conv_id: [job_ids]}
SESSION_CWD = {}         # {conv_id: current_working_dir}
```

### Nuevos endpoints

#### POST /session/init
```python
@app.route('/session/init', methods=['POST'])
def init_session():
    """Crea repo git para una nueva conversación"""
    data = request.get_json()
    conv_id = data['conversation_id']
    
    repo_path = Path(SESSIONS_BASE) / conv_id
    repo_path.mkdir(parents=True, exist_ok=True)
    
    repo = git.Repo.init(repo_path)
    repo.config_writer().set_value("user", "name", "Cerebro Agent").release()
    repo.config_writer().set_value("user", "email", "agent@tfg").release()
    
    # Commit inicial
    readme = repo_path / "README.md"
    readme.write_text(f"# Workspace for conversation {conv_id}\n")
    repo.index.add(["README.md"])
    repo.index.commit("Initial commit")
    
    CONVERSATION_REPOS[conv_id] = repo
    SESSION_CWD[conv_id] = str(repo_path)
    JOBS_BY_CONV[conv_id] = []
    
    return jsonify({
        "status": "ok",
        "repo_path": str(repo_path),
        "commit": repo.head.commit.hexsha[:8]
    })
```

#### POST /session/checkpoint
```python
@app.route('/session/checkpoint', methods=['POST'])
def create_checkpoint():
    """Guarda estado como git commit + tag"""
    data = request.get_json()
    conv_id = data['conversation_id']
    leaf_id = data['leaf_id']
    parent_leaf = data.get('parent_leaf_id')
    
    if conv_id not in CONVERSATION_REPOS:
        return jsonify({"error": "Session not initialized"}), 400
    
    repo = CONVERSATION_REPOS[conv_id]
    tag_name = f"leaf_{leaf_id}"
    
    # Si tiene padre, partir de ese commit
    if parent_leaf:
        parent_tag = f"leaf_{parent_leaf}"
        try:
            repo.git.checkout(parent_tag)
        except:
            pass  # Padre no existe, usar HEAD actual
    
    # Commit cambios
    repo.git.add(A=True)
    try:
        commit = repo.index.commit(f"State at leaf {leaf_id}")
        repo.create_tag(tag_name, ref=commit, force=True)
        commit_sha = commit.hexsha[:8]
    except git.exc.GitCommandError:
        # No hay cambios, usar commit actual
        commit_sha = repo.head.commit.hexsha[:8]
        repo.create_tag(tag_name, force=True)
    
    LEAF_COMMITS[f"{conv_id}_{leaf_id}"] = commit_sha
    
    return jsonify({
        "status": "ok",
        "commit": commit_sha,
        "tag": tag_name
    })
```

#### POST /session/switch
```python
@app.route('/session/switch', methods=['POST'])
def switch_branch():
    """Cambia a otro leaf (git checkout)"""
    data = request.get_json()
    conv_id = data['conversation_id']
    leaf_id = data['leaf_id']
    
    if conv_id not in CONVERSATION_REPOS:
        return jsonify({"error": "Session not found"}), 404
    
    repo = CONVERSATION_REPOS[conv_id]
    tag_name = f"leaf_{leaf_id}"
    
    try:
        repo.git.checkout(tag_name, force=True)
    except git.exc.GitCommandError as e:
        return jsonify({"error": str(e)}), 404
    
    # Restaurar CWD
    repo_path = Path(SESSIONS_BASE) / conv_id
    SESSION_CWD[conv_id] = str(repo_path)
    
    return jsonify({
        "status": "ok",
        "cwd": SESSION_CWD[conv_id],
        "commit": repo.head.commit.hexsha[:8]
    })
```

### Modificar /execute

```python
@app.route('/execute', methods=['POST'])
def execute_command():
    # ... código existente ...
    
    # CAMBIO: session_id → conversation_id
    conv_id = data.get('conversation_id', 'default')
    leaf_id = data.get('leaf_id')
    
    # Obtener CWD del repo git
    if conv_id not in SESSION_CWD:
        SESSION_CWD[conv_id] = f"{SESSIONS_BASE}/{conv_id}"
    
    current_cwd = SESSION_CWD[conv_id]
    
    # ... resto igual hasta crear job ...
    
    JOBS[job_id] = {
        # ... campos existentes ...
        "conversation_id": conv_id,  # NUEVO
        "leaf_id": leaf_id,          # NUEVO
    }
    
    # Asociar job a conversación
    if conv_id not in JOBS_BY_CONV:
        JOBS_BY_CONV[conv_id] = []
    JOBS_BY_CONV[conv_id].append(job_id)
    
    # ... resto igual ...
    
    # Auto-checkpoint si comando terminó exitoso
    if not is_running and return_code == 0 and leaf_id:
        try:
            repo = CONVERSATION_REPOS.get(conv_id)
            if repo:
                repo.git.add(A=True)
                repo.index.commit(f"Auto: {command}")
        except:
            pass  # Ignorar errores de git
    
    return jsonify(response)
```

### Testing
```bash
# 1. Crear conversación
curl -X POST localhost:5000/session/init \
  -H "Content-Type: application/json" \
  -d '{"conversation_id":"conv_test_123"}'

# 2. Ejecutar comando
curl -X POST localhost:5000/execute \
  -H "Content-Type: application/json" \
  -d '{"command":"echo hello > file.txt","conversation_id":"conv_test_123","leaf_id":"msg_1"}'

# 3. Crear checkpoint
curl -X POST localhost:5000/session/checkpoint \
  -H "Content-Type: application/json" \
  -d '{"conversation_id":"conv_test_123","leaf_id":"msg_1"}'

# 4. Verificar git
docker exec agente-tfg sh -c "cd /workspace_sessions/conv_test_123 && git log --oneline"
```

---

## 📦 FASE 2: Admin UI Mejorada (2h)

### Objetivo
Filtrar sesiones/jobs por conversación. Ver qué proceso pertenece a qué chat.

### Nuevos endpoints

#### GET /admin/conversations
```python
@app.route('/admin/conversations', methods=['GET'])
def list_conversations():
    """Lista todas las conversaciones activas"""
    conversations = []
    
    for conv_id in CONVERSATION_REPOS.keys():
        repo = CONVERSATION_REPOS[conv_id]
        commit = repo.head.commit.hexsha[:8]
        
        # Jobs activos de esta conversación
        active_jobs = [
            jid for jid in JOBS_BY_CONV.get(conv_id, [])
            if jid in JOBS and JOBS[jid]["proc"].poll() is None
        ]
        
        conversations.append({
            "conversation_id": conv_id,
            "cwd": SESSION_CWD.get(conv_id, ""),
            "commit": commit,
            "active_jobs": len(active_jobs),
            "total_jobs": len(JOBS_BY_CONV.get(conv_id, []))
        })
    
    return jsonify({"conversations": conversations})
```

#### GET /admin/conversation/<conv_id>
```python
@app.route('/admin/conversation/<conv_id>', methods=['GET'])
def conversation_detail(conv_id):
    """Detalle de una conversación: jobs, commits, archivos"""
    if conv_id not in CONVERSATION_REPOS:
        return jsonify({"error": "Not found"}), 404
    
    repo = CONVERSATION_REPOS[conv_id]
    repo_path = Path(SESSIONS_BASE) / conv_id
    
    # Jobs de esta conversación
    job_ids = JOBS_BY_CONV.get(conv_id, [])
    jobs = []
    for jid in job_ids:
        if jid in JOBS:
            job = JOBS[jid]
            jobs.append({
                "job_id": jid,
                "command": job["command"],
                "status": "running" if job["proc"].poll() is None else "finished",
                "leaf_id": job.get("leaf_id"),
                "start_time": job["start_time"]
            })
    
    # Git tags (leafs)
    tags = [tag.name for tag in repo.tags]
    
    # Archivos en el workspace
    files = [str(f.relative_to(repo_path)) for f in repo_path.rglob("*") if f.is_file()]
    
    return jsonify({
        "conversation_id": conv_id,
        "cwd": SESSION_CWD.get(conv_id),
        "commit": repo.head.commit.hexsha[:8],
        "tags": tags,
        "jobs": jobs,
        "files": files[:50]  # Limitar a 50
    })
```

#### GET /admin/running
```python
@app.route('/admin/running', methods=['GET'])
def list_running():
    """Lista TODOS los jobs en ejecución, agrupados por conversación"""
    running = {}
    
    for conv_id, job_ids in JOBS_BY_CONV.items():
        conv_running = []
        for jid in job_ids:
            if jid in JOBS and JOBS[jid]["proc"].poll() is None:
                job = JOBS[jid]
                conv_running.append({
                    "job_id": jid,
                    "command": job["command"],
                    "leaf_id": job.get("leaf_id"),
                    "elapsed": time.time() - job["start_time"]
                })
        
        if conv_running:
            running[conv_id] = conv_running
    
    return jsonify({"running": running, "total": sum(len(v) for v in running.values())})
```

### Actualizar templates/admin.html

```html
<!-- NUEVO: Filtro por conversación -->
<div class="filter-bar">
  <label>
    Conversación:
    <select id="convFilter" onchange="filterByConversation()">
      <option value="all">Todas</option>
      {% for conv in conversations %}
      <option value="{{ conv.id }}">{{ conv.id }}</option>
      {% endfor %}
    </select>
  </label>
</div>

<!-- Tabla de jobs con columna conversation_id -->
<table>
  <thead>
    <tr>
      <th>Job ID</th>
      <th>Conversation</th>  <!-- NUEVA COLUMNA -->
      <th>Command</th>
      <th>Status</th>
      <th>Actions</th>
    </tr>
  </thead>
  <tbody>
    {% for job in jobs %}
    <tr data-conversation="{{ job.conversation_id }}">
      <td>{{ job.job_id[:8] }}</td>
      <td><code>{{ job.conversation_id[:12] }}</code></td>
      <td>{{ job.command }}</td>
      <td>{{ job.status }}</td>
      <td>...</td>
    </tr>
    {% endfor %}
  </tbody>
</table>

<script>
function filterByConversation() {
  const filter = document.getElementById('convFilter').value;
  const rows = document.querySelectorAll('tbody tr');
  
  rows.forEach(row => {
    if (filter === 'all' || row.dataset.conversation.startsWith(filter)) {
      row.style.display = '';
    } else {
      row.style.display = 'none';
    }
  });
}
</script>
```

---

## 📦 FASE 3: Frontend Integration (2.5h)

### Objetivo
Integrar terminal en el frontend Next.js. Mostrar comandos ejecutados en el chat.

### 1. Nuevo servicio: services/terminal.ts

```typescript
const TERMINAL_URL = 'http://localhost:5000';

export async function initTerminalSession(conversationId: string) {
  const res = await fetch(`${TERMINAL_URL}/session/init`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ conversation_id: conversationId }),
  });
  return res.json();
}

export async function createCheckpoint(
  conversationId: string,
  leafId: string,
  parentLeafId?: string
) {
  const res = await fetch(`${TERMINAL_URL}/session/checkpoint`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      conversation_id: conversationId,
      leaf_id: leafId,
      parent_leaf_id: parentLeafId,
    }),
  });
  return res.json();
}

export async function switchBranch(conversationId: string, leafId: string) {
  const res = await fetch(`${TERMINAL_URL}/session/switch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ conversation_id: conversationId, leaf_id: leafId }),
  });
  return res.json();
}

export async function getRunningJobs(conversationId: string) {
  const res = await fetch(`${TERMINAL_URL}/admin/conversation/${conversationId}`);
  const data = await res.json();
  return data.jobs.filter((j: any) => j.status === 'running');
}
```

### 2. Modificar components/chat/ChatArea.tsx

```typescript
import { initTerminalSession, createCheckpoint, switchBranch } from '@/services/terminal';

export function ChatArea() {
  // ... estados existentes ...
  const [terminalInitialized, setTerminalInitialized] = useState(false);
  
  // Inicializar terminal cuando se crea conversación
  useEffect(() => {
    if (conversationId && !terminalInitialized) {
      initTerminalSession(conversationId).then(() => {
        setTerminalInitialized(true);
      });
    }
  }, [conversationId, terminalInitialized]);
  
  // Detectar cambio de rama (branch navigation)
  useEffect(() => {
    if (activeLeafId && conversationId && terminalInitialized) {
      switchBranch(conversationId, activeLeafId).catch(console.error);
    }
  }, [activeLeafId, conversationId, terminalInitialized]);
  
  const handleSend = async () => {
    // ... código existente hasta enviar mensaje ...
    
    const newMsg = await sendMessage(/* ... */);
    
    // Crear checkpoint del nuevo leaf
    if (conversationId && terminalInitialized) {
      await createCheckpoint(conversationId, newMsg.id, newMsg.parent_id);
    }
    
    // ... resto igual ...
  };
  
  // ... resto del componente ...
}
```

### 3. Nuevo componente: TerminalPanel.tsx

```typescript
"use client";

import { useState, useEffect } from 'react';
import { useChatStore } from '@/store/useStore';
import { getRunningJobs } from '@/services/terminal';
import { Terminal, Loader2 } from 'lucide-react';

export function TerminalPanel() {
  const { conversationId } = useChatStore();
  const [runningJobs, setRunningJobs] = useState<any[]>([]);
  
  useEffect(() => {
    if (!conversationId) return;
    
    const interval = setInterval(async () => {
      const jobs = await getRunningJobs(conversationId);
      setRunningJobs(jobs);
    }, 2000);
    
    return () => clearInterval(interval);
  }, [conversationId]);
  
  if (runningJobs.length === 0) return null;
  
  return (
    <div className="fixed bottom-20 right-4 bg-black/90 text-green-400 p-4 rounded-lg border border-green-500/30 w-96">
      <div className="flex items-center gap-2 mb-2">
        <Terminal className="h-4 w-4" />
        <span className="font-mono text-xs">Running Jobs</span>
      </div>
      
      {runningJobs.map(job => (
        <div key={job.job_id} className="flex items-center gap-2 text-xs font-mono mb-1">
          <Loader2 className="h-3 w-3 animate-spin" />
          <span className="truncate">{job.command}</span>
          <span className="text-gray-500">{Math.floor(job.elapsed)}s</span>
        </div>
      ))}
    </div>
  );
}
```

### 4. Integrar en app/page.tsx

```typescript
import { TerminalPanel } from '@/components/terminal/TerminalPanel';

export default function Home() {
  return (
    <div className="h-screen">
      <Sidebar />
      <ChatArea />
      <TerminalPanel />  {/* NUEVO */}
      {/* ... otros componentes ... */}
    </div>
  );
}
```

---

## 📦 FASE 4: LLM System Prompt (1h)

### Actualizar llm.md

Añadir al inicio después de "Base URL":

```markdown
## 🔄 Working with Conversations & Branches

Each conversation has its own isolated workspace with Git version control.

**Important:**
- Always include `conversation_id` and `leaf_id` in `/execute` requests
- These are provided automatically by the frontend
- Each message (leaf) creates a Git checkpoint
- Switching branches restores the exact filesystem state

**Persistent Storage Rules:**
1. BEFORE downloading tools >10MB: `cat /workspace_persistent/INVENTORY.md`
2. If tool exists: Create symlink instead of downloading
3. If new: Install to `/workspace_persistent/tools/NAME` and update INVENTORY.md

**Example:**
```bash
# Check inventory first
cat /workspace_persistent/INVENTORY.md | grep sqlmap

# If exists:
ln -s /workspace_persistent/tools/sqlmap ./sqlmap

# If not:
git clone https://github.com/sqlmapproject/sqlmap.git /workspace_persistent/tools/sqlmap
echo "### sqlmap v1.7.12 - Path: /workspace_persistent/tools/sqlmap" >> /workspace_persistent/INVENTORY.md
ln -s /workspace_persistent/tools/sqlmap ./sqlmap
```
```

---

## 📊 Resumen de Cambios

| Componente | Archivos Modificados | Líneas Estimadas |
|------------|---------------------|------------------|
| **Backend Terminal** | agent_api.py | +250 |
| | llm.md | +40 |
| **Docker** | Dockerfile | +5 |
| | docker-compose.yml | +4 |
| **Frontend** | services/terminal.ts (nuevo) | +60 |
| | ChatArea.tsx | +30 |
| | TerminalPanel.tsx (nuevo) | +50 |
| **UI Admin** | templates/admin.html | +80 |
| **Total** | 8 archivos | ~520 líneas |

---

## ⏱️ Estimación Temporal

| Fase | Tiempo | Acumulado |
|------|--------|-----------|
| Fase 0: Persistent Storage | 1.5h | 1.5h |
| Fase 1: Git Snapshots | 3h | 4.5h |
| Fase 2: Admin UI | 2h | 6.5h |
| Fase 3: Frontend | 2.5h | 9h |
| Fase 4: LLM Prompt | 1h | 10h |
| **Testing & Debug** | 2h | **12h** |

**Total: 12 horas (1.5 días laborables)**

---

## ✅ Checklist de Validación

### Fase 0
- [ ] `/workspace_persistent/` existe en contenedor
- [ ] `INVENTORY.md` se crea automáticamente
- [ ] Volumen Docker persiste tras `docker compose down`

### Fase 1
- [ ] POST /session/init crea repo git
- [ ] POST /session/checkpoint crea tags
- [ ] POST /session/switch restaura filesystem
- [ ] Archivos creados en rama A no existen en rama B

### Fase 2
- [ ] `/admin/conversations` lista todas las conversaciones
- [ ] `/admin/running` agrupa jobs por conversación
- [ ] UI permite filtrar por conversation_id

### Fase 3
- [ ] Frontend inicializa terminal al crear chat
- [ ] Cambiar de rama ejecuta switchBranch()
- [ ] TerminalPanel muestra jobs en ejecución
- [ ] Checkpoint se crea automáticamente tras mensaje

### Fase 4
- [ ] LLM lee INVENTORY.md antes de descargar
- [ ] LLM crea symlinks si herramienta existe
- [ ] LLM actualiza INVENTORY.md tras instalar

---

## 🎯 Casos de Uso Finales

### Caso 1: Usuario ejecuta nmap en dos ramas
```
Rama A: nmap -sV 10.5.0.3 → output: "22, 80 open"
[Regenerate]
Rama B: nmap -A 10.5.0.3 → output: "SSH 7.4, Apache 2.4"

[Usuario navega a Rama A]
→ Backend: git checkout leaf_A
→ Filesystem restaurado: solo existe nmap_output_ramA.txt
```

### Caso 2: LLM descarga sqlmap (persistente)
```
Chat 1: "Instala sqlmap"
→ LLM: cat /workspace_persistent/INVENTORY.md | grep sqlmap
→ LLM: No existe
→ LLM: git clone ... /workspace_persistent/tools/sqlmap
→ LLM: Actualiza INVENTORY.md

Chat 2 (otra conversación): "Usa sqlmap"
→ LLM: cat /workspace_persistent/INVENTORY.md | grep sqlmap
→ LLM: ✅ Existe!
→ LLM: ln -s /workspace_persistent/tools/sqlmap ./sqlmap
→ LLM: python3 sqlmap/sqlmap.py ...
```

### Caso 3: Monitoreo de jobs en UI
```
Frontend muestra TerminalPanel:
┌─────────────────────────────┐
│ 🖥️ Running Jobs            │
├─────────────────────────────┤
│ ⟳ nmap -A 10.5.0.3   (45s) │
│ ⟳ hydra -L users.txt (120s)│
└─────────────────────────────┘

Usuario hace click → abre modal con stdout en tiempo real
```

---

## 📖 Referencias Técnicas

- [GitPython Docs](https://gitpython.readthedocs.io/en/stable/tutorial.html)
- [Docker Named Volumes](https://docs.docker.com/storage/volumes/)
- [Flask Background Tasks](https://flask.palletsprojects.com/en/2.3.x/patterns/celery/)
- [Next.js useEffect Hook](https://react.dev/reference/react/useEffect)

---

## 🎬 Conclusión

Este plan convierte el terminal actual en un sistema completo con:
- ✅ Aislamiento perfecto entre conversaciones
- ✅ Branches git para explorar alternativas sin pérdida de estado
- ✅ Persistent storage para herramientas pesadas (evita descargas duplicadas)
- ✅ UI integrada que muestra qué proceso pertenece a qué conversación
- ✅ Frontend embebido con indicador de jobs en ejecución

**Próximo paso**: Implementar Fase 0 (persistent storage) y validar con tests manuales.
