from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import subprocess
import os
import uuid
import time
import signal
from pathlib import Path
from datetime import datetime

# GitPython para control de versiones por conversación
try:
    import git
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False
    print("[!] GitPython no disponible. Funciones de snapshot deshabilitadas.")

app = Flask(__name__)
CORS(app)  # Habilitar CORS para permitir peticiones desde el frontend

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

WORKING_DIR = "/workspace"
SESSIONS_BASE = "/workspace_sessions"    # Repos git por conversación
PERSISTENT_DIR = "/workspace_persistent"  # Herramientas compartidas
INVENTORY_PATH = f"{PERSISTENT_DIR}/INVENTORY.md"

# =============================================================================
# ALMACENES EN MEMORIA
# =============================================================================

# Jobs en ejecución: { job_id: { proc, out_file, command, conversation_id, ... } }
JOBS = {}

# Git repos por conversación: { conversation_id: git.Repo }
CONVERSATION_REPOS = {}

# Commits por leaf: { "conv_id_leaf_id": commit_sha }
LEAF_COMMITS = {}

# Jobs agrupados por conversación: { conversation_id: [job_ids] }
JOBS_BY_CONV = {}

# CWD por conversación: { conversation_id: current_working_dir }
SESSION_CWD = {}

# Historial de comandos: { conversation_id: [entries] }
SESSION_HISTORY = {}

# =============================================================================
# INICIALIZACIÓN PERSISTENT STORAGE
# =============================================================================

def init_persistent_storage():
    """Crea estructura de carpetas persistentes e INVENTORY.md inicial"""
    os.makedirs(f"{PERSISTENT_DIR}/tools", exist_ok=True)
    os.makedirs(f"{PERSISTENT_DIR}/downloads", exist_ok=True)
    os.makedirs(f"{PERSISTENT_DIR}/wordlists", exist_ok=True)
    
    if not os.path.exists(INVENTORY_PATH):
        with open(INVENTORY_PATH, "w") as f:
            f.write("""# 🗂️ Persistent Tools Inventory

**Last Updated**: (auto-updated by agent)

---

## 📦 Installed Tools

| Tool | Path | Size | Version | Date Added |
|------|------|------|---------|------------|
| (none yet) | - | - | - | - |

---

## 📝 Usage Instructions

Before downloading any tool larger than 10MB:
1. Read this file: `cat /workspace_persistent/INVENTORY.md`
2. If tool exists: Create symlink: `ln -s /workspace_persistent/tools/TOOL_NAME ./TOOL_NAME`
3. If not: Install to `/workspace_persistent/tools/` and update this file

## 📁 Directory Structure

```
/workspace_persistent/
├── tools/        # Installed tools (sqlmap, metasploit, etc.)
├── wordlists/    # Custom wordlists
├── downloads/    # Temporary large downloads
└── INVENTORY.md  # This file
```
""")
        print("[+] INVENTORY.md creado")

# Ejecutar al iniciar
init_persistent_storage()

# =============================================================================
# ENDPOINTS: GESTIÓN DE SESIONES (GIT SNAPSHOTS)
# =============================================================================

@app.route('/session/init', methods=['POST'])
def init_session():
    """
    Crea un nuevo repo git para una conversación.
    POST { "conversation_id": "conv_abc123" }
    """
    if not GIT_AVAILABLE:
        return jsonify({"error": "GitPython not available"}), 500
    
    data = request.get_json() or {}
    conv_id = data.get('conversation_id')
    
    if not conv_id:
        return jsonify({"error": "conversation_id required"}), 400
    
    # Si ya existe, retornar info actual
    if conv_id in CONVERSATION_REPOS:
        repo = CONVERSATION_REPOS[conv_id]
        return jsonify({
            "status": "exists",
            "conversation_id": conv_id,
            "repo_path": str(Path(SESSIONS_BASE) / conv_id),
            "commit": repo.head.commit.hexsha[:8] if repo.head.is_valid() else "none"
        })
    
    try:
        repo_path = Path(SESSIONS_BASE) / conv_id
        repo_path.mkdir(parents=True, exist_ok=True)
        
        # Inicializar repo git
        repo = git.Repo.init(repo_path)
        repo.config_writer().set_value("user", "name", "Cerebro Agent").release()
        repo.config_writer().set_value("user", "email", "agent@tfg.local").release()
        
        # Commit inicial
        readme = repo_path / "README.md"
        readme.write_text(f"# Workspace - Conversation {conv_id}\n\nCreated: {datetime.now().isoformat()}\n")
        repo.index.add(["README.md"])
        initial_commit = repo.index.commit("Initial commit")
        
        # Guardar en memoria
        CONVERSATION_REPOS[conv_id] = repo
        SESSION_CWD[conv_id] = str(repo_path)
        JOBS_BY_CONV[conv_id] = []
        SESSION_HISTORY[conv_id] = []
        
        print(f"[+] Session initialized: {conv_id}")
        
        return jsonify({
            "status": "created",
            "conversation_id": conv_id,
            "repo_path": str(repo_path),
            "commit": initial_commit.hexsha[:8]
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/session/checkpoint', methods=['POST'])
def create_checkpoint():
    """
    Crea un checkpoint (commit + tag) para un leaf_id específico.
    POST { "conversation_id": "...", "leaf_id": "...", "parent_leaf_id": "..." }
    """
    if not GIT_AVAILABLE:
        return jsonify({"error": "GitPython not available"}), 500
    
    data = request.get_json() or {}
    conv_id = data.get('conversation_id')
    leaf_id = data.get('leaf_id')
    parent_leaf = data.get('parent_leaf_id')
    
    if not conv_id or not leaf_id:
        return jsonify({"error": "conversation_id and leaf_id required"}), 400
    
    if conv_id not in CONVERSATION_REPOS:
        return jsonify({"error": f"Session {conv_id} not initialized"}), 404
    
    try:
        repo = CONVERSATION_REPOS[conv_id]
        tag_name = f"leaf_{leaf_id}"
        
        # Si tiene padre, partir de ese commit
        if parent_leaf:
            parent_tag = f"leaf_{parent_leaf}"
            try:
                repo.git.checkout(parent_tag, force=True)
            except git.exc.GitCommandError:
                pass  # Padre no existe, usar HEAD actual
        
        # Añadir todos los cambios
        repo.git.add(A=True)
        
        # Intentar commit (puede fallar si no hay cambios)
        try:
            commit = repo.index.commit(f"Checkpoint: {leaf_id}")
            commit_sha = commit.hexsha[:8]
        except git.exc.GitCommandError:
            # No hay cambios, usar commit actual
            commit_sha = repo.head.commit.hexsha[:8]
        
        # Crear/actualizar tag
        try:
            repo.delete_tag(tag_name)
        except:
            pass
        repo.create_tag(tag_name)
        
        # Guardar mapping
        LEAF_COMMITS[f"{conv_id}_{leaf_id}"] = commit_sha
        
        print(f"[+] Checkpoint created: {conv_id}/{leaf_id} -> {commit_sha}")
        
        return jsonify({
            "status": "ok",
            "conversation_id": conv_id,
            "leaf_id": leaf_id,
            "commit": commit_sha,
            "tag": tag_name
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/session/switch', methods=['POST'])
def switch_branch():
    """
    Cambia a un leaf específico (git checkout del tag).
    POST { "conversation_id": "...", "leaf_id": "..." }
    """
    if not GIT_AVAILABLE:
        return jsonify({"error": "GitPython not available"}), 500
    
    data = request.get_json() or {}
    conv_id = data.get('conversation_id')
    leaf_id = data.get('leaf_id')
    
    if not conv_id or not leaf_id:
        return jsonify({"error": "conversation_id and leaf_id required"}), 400
    
    if conv_id not in CONVERSATION_REPOS:
        return jsonify({"error": f"Session {conv_id} not found"}), 404
    
    try:
        repo = CONVERSATION_REPOS[conv_id]
        tag_name = f"leaf_{leaf_id}"
        
        # Checkout al tag
        repo.git.checkout(tag_name, force=True)
        
        # Restaurar CWD al root del repo
        repo_path = Path(SESSIONS_BASE) / conv_id
        SESSION_CWD[conv_id] = str(repo_path)
        
        commit_sha = repo.head.commit.hexsha[:8]
        
        print(f"[+] Switched to: {conv_id}/{leaf_id} ({commit_sha})")
        
        return jsonify({
            "status": "ok",
            "conversation_id": conv_id,
            "leaf_id": leaf_id,
            "commit": commit_sha,
            "cwd": SESSION_CWD[conv_id]
        })
        
    except git.exc.GitCommandError as e:
        return jsonify({"error": f"Tag {tag_name} not found: {str(e)}"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/session/info/<conversation_id>', methods=['GET'])
def get_session_info(conversation_id):
    """Devuelve información completa de una sesión/conversación"""
    if conversation_id not in CONVERSATION_REPOS:
        return jsonify({"error": "Session not found"}), 404
    
    try:
        repo = CONVERSATION_REPOS[conversation_id]
        repo_path = Path(SESSIONS_BASE) / conversation_id
        
        # Tags (leafs)
        tags = [tag.name for tag in repo.tags]
        
        # Jobs de esta conversación
        job_ids = JOBS_BY_CONV.get(conversation_id, [])
        jobs = []
        for jid in job_ids:
            if jid in JOBS:
                job = JOBS[jid]
                proc = job["proc"]
                jobs.append({
                    "job_id": jid[:8],
                    "command": job["command"],
                    "status": "running" if proc.poll() is None else "finished",
                    "leaf_id": job.get("leaf_id")
                })
        
        # Archivos en workspace (excluyendo .git)
        files = []
        for f in repo_path.rglob("*"):
            if f.is_file() and ".git" not in f.parts:
                files.append(str(f.relative_to(repo_path)))
        
        return jsonify({
            "conversation_id": conversation_id,
            "cwd": SESSION_CWD.get(conversation_id),
            "commit": repo.head.commit.hexsha[:8] if repo.head.is_valid() else None,
            "tags": tags,
            "jobs": jobs,
            "files": files[:100]  # Limitar
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

def compress_output(text):
    """
    Agrupa líneas consecutivas similares para reducir el tamaño del log.
    Ejemplo:
      Ping... time=10ms
      Ping... time=11ms
    Se convierte en:
      Ping... time={ 10ms, 11ms }
    """
    if not text: return ""
    lines = text.splitlines()
    if len(lines) < 2: return text
    
    compressed = []
    buffer = []
    
    def process_buffer():
        if not buffer: return
        if len(buffer) == 1:
            compressed.append(buffer[0])
        else:
            # Encontrar prefijo común
            prefix = os.path.commonprefix(buffer)
            # Heurística: Si el prefijo es corto o nulo, no agrupamos
            if len(prefix) < 10: 
                compressed.extend(buffer)
            else:
                # Extraer la parte variable (sufijos)
                suffixes = [line[len(prefix):] for line in buffer]
                # Formato comprimido
                joined = ", ".join(suffixes)
                compressed.append(f"{prefix}{{ {joined} }}")
        buffer.clear()

    for line in lines:
        # Si la línea está vacía, procesamos buffer y la añadimos tal cual
        if not line.strip():
            process_buffer()
            compressed.append(line)
            continue
        
        if not buffer:
            buffer.append(line)
            continue
            
        # Comprobar similitud con el buffer actual (usando la primera como referencia)
        ref = buffer[0]
        common = os.path.commonprefix([ref, line])
        
        # Criterio: Comparten prefijo largo (>20 chars) o >60% de longitud
        if len(common) > 20 or (len(ref) > 0 and len(common) / len(ref) > 0.6):
            buffer.append(line)
        else:
            process_buffer()
            buffer.append(line)
            
    process_buffer()
    return "\n".join(compressed)

@app.route('/execute', methods=['POST'])
def execute_command():
    """
    Inicia un comando en background y devuelve un job_id.
    
    Parámetros:
    - command (str): Comando a ejecutar
    - wait_time (int): Segundos a esperar antes de responder
    - exit_time (int): Segundos tras los cuales matar el proceso
    - conversation_id (str): ID de conversación (usa repo git dedicado)
    - leaf_id (str): ID del mensaje/nodo actual
    - session_id (str): DEPRECADO - usar conversation_id
    """
    try:
        data = request.get_json()
        if not data or 'command' not in data:
            return jsonify({"status": "error", "message": "No command provided"}), 400
        
        command = data['command'].strip()
        wait_time = float(data.get('wait_time', 0))
        exit_time = float(data.get('exit_time', 0))
        
        # Soportar tanto conversation_id (nuevo) como session_id (legacy)
        conv_id = data.get('conversation_id') or data.get('session_id', 'default')
        leaf_id = data.get('leaf_id')

        # Determinar CWD: si tiene repo git, usar ese; si no, usar WORKING_DIR
        if conv_id in CONVERSATION_REPOS:
            if conv_id not in SESSION_CWD:
                SESSION_CWD[conv_id] = str(Path(SESSIONS_BASE) / conv_id)
        else:
            if conv_id not in SESSION_CWD:
                SESSION_CWD[conv_id] = WORKING_DIR
        
        current_cwd = SESSION_CWD[conv_id]

        # Detectar si es un comando cd para actualizar el cwd
        if command.startswith('cd '):
            target_dir = command[3:].strip()
            # Si es cd sin argumentos o cd ~, ir al workspace base
            base_dir = str(Path(SESSIONS_BASE) / conv_id) if conv_id in CONVERSATION_REPOS else WORKING_DIR
            if not target_dir or target_dir == '~':
                target_dir = base_dir
            # Si es relativo, construir la ruta desde current_cwd
            if not target_dir.startswith('/'):
                target_dir = os.path.join(current_cwd, target_dir)
            # Normalizar la ruta
            target_dir = os.path.normpath(target_dir)
            SESSION_CWD[conv_id] = target_dir
            command = f"cd {target_dir}"
        
        # Prefijar el comando con cd al directorio actual
        full_command = f"cd {current_cwd} && {command}"

        print(f"[*] Job: {command} en {current_cwd} (conv={conv_id}, leaf={leaf_id})")

        job_id = str(uuid.uuid4())
        
        # Usamos archivos temporales para capturar salida sin bloquear
        out_path = f"/tmp/{job_id}.out"
        err_path = f"/tmp/{job_id}.err"
        
        out_file = open(out_path, "w+")
        err_file = open(err_path, "w+")

        # Ejecutar en background (Popen)
        proc = subprocess.Popen(
            full_command,
            shell=True,
            stdout=out_file,
            stderr=err_file,
            cwd=current_cwd if os.path.isdir(current_cwd) else WORKING_DIR,
            text=True
        )

        JOBS[job_id] = {
            "proc": proc,
            "out_file": out_file,
            "err_file": err_file,
            "out_path": out_path,
            "err_path": err_path,
            "command": command,
            "session_id": conv_id,  # Mantener para compatibilidad
            "conversation_id": conv_id,
            "leaf_id": leaf_id,
            "start_time": time.time()
        }
        
        # Registrar job en la conversación
        if conv_id not in JOBS_BY_CONV:
            JOBS_BY_CONV[conv_id] = []
        JOBS_BY_CONV[conv_id].append(job_id)
        
        # Guardar en historial de la sesión
        if conv_id not in SESSION_HISTORY:
            SESSION_HISTORY[conv_id] = []
        
        SESSION_HISTORY[conv_id].append({
            "job_id": job_id,
            "command": command,
            "timestamp": time.time(),
            "cwd": current_cwd,
            "leaf_id": leaf_id
        })

        # Comportamiento de espera:
        # - Si se pasa `exit_time` (>0) se espera ese tiempo y SI SIGUE EN EJECUCIÓN
        #   se detiene el proceso y se devuelve la salida (exit_time tiene preferencia).
        # - Si no hay `exit_time` y sí `wait_time` (>0) se espera ese tiempo pero no se
        #   detiene el proceso (modo síncrono/LLM).
        # - Si no hay ninguno, hacemos una pequeña espera de cortesía (0.1s) para
        #   atrapar comandos instantáneos.
        if exit_time > 0:
            start_wait = time.time()
            while time.time() - start_wait < exit_time:
                if proc.poll() is not None:
                    break
                time.sleep(0.5)

            # Si sigue vivo al pasar exit_time, lo detenemos (SIGINT -> TERM -> KILL)
            if proc.poll() is None:
                proc.send_signal(signal.SIGINT)
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.terminate()
                    try:
                        proc.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        proc.kill()

        elif wait_time > 0:
            start_wait = time.time()
            while time.time() - start_wait < wait_time:
                if proc.poll() is not None:
                    break
                time.sleep(0.5)

        else:
            # Pequeña espera de cortesía (0.1s) para capturar comandos instantáneos (whoami, ls, etc.)
            try:
                proc.wait(timeout=0.1)
            except subprocess.TimeoutExpired:
                pass # Sigue corriendo, no pasa nada

        # Preparar respuesta inicial
        return_code = proc.poll()
        is_running = (return_code is None)
        
        # Leer lo que haya hasta ahora
        def read_content(path):
            if not os.path.exists(path): return ""
            with open(path, 'r', errors='replace') as f:
                return f.read()

        stdout_content = read_content(out_path)
        stderr_content = read_content(err_path)

        # Aplicar compresión si hay contenido
        if stdout_content: stdout_content = compress_output(stdout_content)
        
        # Actualizar historial con resultados si el comando terminó
        if not is_running and conv_id in SESSION_HISTORY:
            for entry in reversed(SESSION_HISTORY[conv_id]):
                if entry["job_id"] == job_id:
                    entry["return_code"] = return_code
                    entry["stdout"] = stdout_content
                    entry["stderr"] = stderr_content
                    entry["finished_at"] = time.time()
                    break

        response = {
            "status": "running" if is_running else "finished",
            "job_id": job_id,
            "return_code": return_code,
            "cwd": SESSION_CWD[conv_id],
            "conversation_id": conv_id
        }
        
        if leaf_id:
            response["leaf_id"] = leaf_id
        if stdout_content: response["stdout"] = stdout_content
        if stderr_content: response["stderr"] = stderr_content
        
        return jsonify(response)

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/status/<job_id>', methods=['GET'])
def get_status(job_id):
    """
    Devuelve el estado del job y su salida acumulada hasta el momento.
    Opcional: ?wait=N espera hasta N segundos si el proceso sigue corriendo.
    """
    if job_id not in JOBS:
        return jsonify({"status": "error", "message": "Job not found"}), 404
    
    job = JOBS[job_id]
    proc = job["proc"]
    
    # Soporte para espera en status (long polling simple)
    wait_time = float(request.args.get('wait', 0))
    if wait_time > 0 and proc.poll() is None:
        start_wait = time.time()
        while time.time() - start_wait < wait_time:
            if proc.poll() is not None:
                break
            time.sleep(0.5)
    
    # Verificar si sigue corriendo
    return_code = proc.poll()
    is_running = (return_code is None)

    # Leer salida actual
    # Hacemos flush de los archivos desde el proceso padre no es necesario, 
    # pero leemos desde el sistema de archivos.
    
    def read_content(path):
        if not os.path.exists(path): return ""
        with open(path, 'r', errors='replace') as f:
            return f.read()

    stdout_content = read_content(job["out_path"])
    stderr_content = read_content(job["err_path"])

    # Aplicar compresión
    if stdout_content: stdout_content = compress_output(stdout_content)

    response = {
        "status": "running" if is_running else "finished",
        "return_code": return_code
    }
    
    # Incluir cwd si hay session_id guardado
    session_id = job.get("session_id", "default")
    if session_id in SESSION_CWD:
        response["cwd"] = SESSION_CWD[session_id]
    
    if stdout_content: response["stdout"] = stdout_content
    if stderr_content: response["stderr"] = stderr_content
    
    return jsonify(response)

@app.route('/stop/<job_id>', methods=['POST'])
def stop_job(job_id):
    """
    Detiene un job en ejecución.
    Intenta enviar SIGINT (Ctrl+C) primero, luego SIGTERM/KILL.
    """
    if job_id not in JOBS:
        return jsonify({"status": "error", "message": "Job not found"}), 404
    
    job = JOBS[job_id]
    proc = job["proc"]
    
    if proc.poll() is None:
        # 1. Intentar Ctrl+C (SIGINT)
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=2) # Esperar a que reaccione
        except subprocess.TimeoutExpired:
            # 2. Si no hace caso, SIGTERM (Terminate)
            proc.terminate()
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                # 3. Si sigue vivo, SIGKILL (Kill -9)
                proc.kill()
        
        return jsonify({"status": "success", "message": "Process stopped (SIGINT/TERM)"})
    else:
        return jsonify({"status": "success", "message": "Process was already finished"})


@app.route('/health', methods=['GET'])
def health_check():
    """Para comprobar si el agente está vivo"""
    return jsonify({"status": "online", "system": "Kali Linux Agent"}), 200


@app.route('/history/<session_id>', methods=['GET'])
def get_session_history(session_id):
    """Devuelve el historial de comandos de una sesión en formato JSON.
    Si todos los comandos son del mismo día, devuelve ese día arriba y cada
    entrada solo con la hora para ahorrar tokens. Si hay varias fechas,
    cada entrada incluye fecha y hora completa.
    """
    if session_id not in SESSION_HISTORY:
        return jsonify({"status": "error", "message": f"Session '{session_id}' not found"}), 404

    history = SESSION_HISTORY[session_id]
    current_cwd = SESSION_CWD.get(session_id, WORKING_DIR)

    # Recoger fechas presentes en el historial (usando `finished_at` si existe, si no `timestamp`)
    def entry_ts(entry):
        return entry.get("finished_at", entry.get("timestamp", 0))

    date_set = set()
    for entry in history:
        ts = entry_ts(entry)
        if ts:
            date_set.add(time.strftime('%Y-%m-%d', time.localtime(ts)))
        else:
            # entradas sin timestamp explícito las marcamos con una cadena vacía
            date_set.add('')

    same_day = (len(date_set) == 1)

    formatted_history = []
    for entry in history:
        ts = entry_ts(entry)
        if ts:
            if same_day:
                # Solo hora cuando todo es el mismo día
                ts_str = time.strftime('%H:%M:%S', time.localtime(ts))
            else:
                # Fecha y hora completa cuando hay múltiple días
                ts_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts))
        else:
            ts_str = ""

        formatted_entry = {
            "command": entry["command"],
            "cwd": entry["cwd"],
            "timestamp": ts_str
        }

        if entry.get("stdout"):
            formatted_entry["stdout"] = entry["stdout"]
        if entry.get("stderr"):
            formatted_entry["error"] = entry["stderr"]
        if entry.get("return_code") is not None:
            formatted_entry["return_code"] = entry["return_code"]

        formatted_history.append(formatted_entry)

    response = {
        "session_id": session_id,
        "cwd_actual": current_cwd,
        "total_commands": len(formatted_history),
        "history": formatted_history
    }

    if same_day:
        # Añadimos la fecha común arriba para ahorro de tokens
        common_date = next(iter(date_set))
        response["date"] = common_date

    return jsonify(response)


@app.route('/admin/session/<session_id>', methods=['GET'])
def session_history(session_id):
    """Muestra el historial de comandos de una sesión específica."""
    if session_id not in SESSION_HISTORY:
        return render_template('admin.html', 
                              error=f"Sesión '{session_id}' no encontrada",
                              total_jobs=0,
                              active_sessions=0,
                              total_conversations=0,
                              jobs=[],
                              sessions=[],
                              conversations=[])
    
    history = SESSION_HISTORY[session_id]
    current_cwd = SESSION_CWD.get(session_id, WORKING_DIR)
    
    # Formatear timestamps para la vista web
    formatted_history = []
    for entry in history:
        formatted_entry = entry.copy()
        formatted_entry["timestamp"] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(entry["timestamp"]))
        formatted_history.append(formatted_entry)
    
    return render_template('session_history.html',
                          session_id=session_id,
                          current_cwd=current_cwd,
                          history=formatted_history)


# =============================================================================
# ENDPOINTS ADMIN API (JSON)
# =============================================================================

@app.route('/admin/api/conversations', methods=['GET'])
def api_list_conversations():
    """API: Lista todas las conversaciones con repos git"""
    conversations = []
    
    for conv_id, repo in CONVERSATION_REPOS.items():
        try:
            commit = repo.head.commit.hexsha[:8] if repo.head.is_valid() else "none"
        except:
            commit = "none"
        
        # Contar jobs activos
        job_ids = JOBS_BY_CONV.get(conv_id, [])
        active_jobs = sum(1 for jid in job_ids if jid in JOBS and JOBS[jid]["proc"].poll() is None)
        
        conversations.append({
            "conversation_id": conv_id,
            "cwd": SESSION_CWD.get(conv_id, ""),
            "commit": commit,
            "active_jobs": active_jobs,
            "total_jobs": len(job_ids),
            "tags_count": len(list(repo.tags)) if GIT_AVAILABLE else 0
        })
    
    return jsonify({"conversations": conversations, "total": len(conversations)})


@app.route('/admin/api/running', methods=['GET'])
def api_list_running():
    """API: Lista todos los jobs en ejecución, agrupados por conversación"""
    running = {}
    
    for conv_id, job_ids in JOBS_BY_CONV.items():
        conv_running = []
        for jid in job_ids:
            if jid in JOBS and JOBS[jid]["proc"].poll() is None:
                job = JOBS[jid]
                conv_running.append({
                    "job_id": jid,
                    "job_id_short": jid[:8],
                    "command": job["command"],
                    "leaf_id": job.get("leaf_id"),
                    "elapsed": round(time.time() - job["start_time"], 1)
                })
        
        if conv_running:
            running[conv_id] = conv_running
    
    # También incluir jobs sin conversación (legacy)
    for jid, job in JOBS.items():
        if job["proc"].poll() is None:
            conv_id = job.get("conversation_id", "default")
            if conv_id not in running:
                running[conv_id] = []
            # Evitar duplicados
            if not any(j["job_id"] == jid for j in running[conv_id]):
                running[conv_id].append({
                    "job_id": jid,
                    "job_id_short": jid[:8],
                    "command": job["command"],
                    "leaf_id": job.get("leaf_id"),
                    "elapsed": round(time.time() - job["start_time"], 1)
                })
    
    total = sum(len(v) for v in running.values())
    return jsonify({"running": running, "total": total})


@app.route('/admin/api/conversation/<conv_id>/jobs', methods=['GET'])
def api_conversation_jobs(conv_id):
    """API: Lista jobs de una conversación específica"""
    job_ids = JOBS_BY_CONV.get(conv_id, [])
    
    jobs = []
    for jid in job_ids:
        if jid in JOBS:
            job = JOBS[jid]
            proc = job["proc"]
            jobs.append({
                "job_id": jid,
                "job_id_short": jid[:8],
                "command": job["command"],
                "status": "running" if proc.poll() is None else "finished",
                "return_code": proc.poll(),
                "leaf_id": job.get("leaf_id"),
                "started_at": time.strftime('%H:%M:%S', time.localtime(job["start_time"])),
                "elapsed": round(time.time() - job["start_time"], 1)
            })
    
    return jsonify({
        "conversation_id": conv_id,
        "jobs": jobs,
        "total": len(jobs),
        "running": sum(1 for j in jobs if j["status"] == "running")
    })


# =============================================================================
# PANEL ADMIN WEB
# =============================================================================

@app.route('/admin', methods=['GET'])
def admin_panel():
    """Panel de administración: muestra sesiones, jobs, conversaciones."""
    # Filtro opcional por conversación
    filter_conv = request.args.get('conversation', '')
    
    # Recopilar información de todos los jobs
    jobs_info = []
    for job_id, job in JOBS.items():
        proc = job["proc"]
        is_running = (proc.poll() is None)
        conv_id = job.get("conversation_id", job.get("session_id", "default"))
        
        # Aplicar filtro si existe
        if filter_conv and conv_id != filter_conv:
            continue
        
        jobs_info.append({
            "job_id": job_id,
            "command": job["command"],
            "session_id": job.get("session_id", "default"),
            "conversation_id": conv_id,
            "leaf_id": job.get("leaf_id", "-"),
            "status": "running" if is_running else "finished",
            "return_code": proc.poll(),
            "started_at": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(job["start_time"])),
            "start_time": job["start_time"],
            "elapsed": round(time.time() - job["start_time"], 1)
        })
    
    # Información de sesiones legacy
    sessions_info = [
        {"session_id": sid, "cwd": cwd, "commands_count": len(SESSION_HISTORY.get(sid, []))}
        for sid, cwd in SESSION_CWD.items()
        if sid not in CONVERSATION_REPOS  # Solo mostrar las que NO son conversaciones git
    ]
    
    # Información de conversaciones (con git)
    conversations_info = []
    for conv_id, repo in CONVERSATION_REPOS.items():
        try:
            commit = repo.head.commit.hexsha[:8] if repo.head.is_valid() else "none"
            tags = len(list(repo.tags))
        except:
            commit = "none"
            tags = 0
        
        job_ids = JOBS_BY_CONV.get(conv_id, [])
        active = sum(1 for jid in job_ids if jid in JOBS and JOBS[jid]["proc"].poll() is None)
        
        conversations_info.append({
            "conversation_id": conv_id,
            "cwd": SESSION_CWD.get(conv_id, ""),
            "commit": commit,
            "tags": tags,
            "commands_count": len(SESSION_HISTORY.get(conv_id, [])),
            "active_jobs": active,
            "total_jobs": len(job_ids)
        })
    
    # Lista de IDs para el dropdown del filtro
    all_conv_ids = list(CONVERSATION_REPOS.keys()) + [s for s in SESSION_CWD.keys() if s not in CONVERSATION_REPOS]
    
    return render_template('admin.html', 
                          total_jobs=len(JOBS),
                          active_sessions=len(sessions_info),
                          total_conversations=len(conversations_info),
                          jobs=jobs_info,
                          sessions=sessions_info,
                          conversations=conversations_info,
                          filter_conv=filter_conv,
                          all_conv_ids=all_conv_ids)


@app.route('/', methods=['GET'])
def index():
    """Sirve la interfaz web simple para usar la API."""
    return render_template('index.html')

if __name__ == '__main__':
    # Host '0.0.0.0' es OBLIGATORIO para que Docker deje entrar conexiones de fuera
    app.run(host='0.0.0.0', port=5000, debug=True)