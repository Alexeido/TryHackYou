from flask import Flask, request, jsonify, render_template
import subprocess
import os
import uuid
import time
import signal

app = Flask(__name__)

# Configuración: Carpeta donde se ejecutarán los comandos
WORKING_DIR = "/workspace"

# Almacén de procesos en memoria: { "job_id": { "proc": Popen, "out": file_obj, "err": file_obj, "cmd": str } }
JOBS = {}

# Directorio actual por sesión (session_id -> cwd)
SESSION_CWD = {}

# Historial de comandos por sesión (session_id -> [lista de comandos])
SESSION_HISTORY = {}

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
    Opcional: "wait_time" (int) espera N segundos antes de responder (para LLMs).
    Opcional: "session_id" (str) identificador de sesión para mantener el cwd.
    """
    try:
        data = request.get_json()
        if not data or 'command' not in data:
            return jsonify({"status": "error", "message": "No command provided"}), 400
        
        command = data['command'].strip()
        wait_time = float(data.get('wait_time', 0))
        exit_time = float(data.get('exit_time', 0))
        session_id = data.get('session_id', 'default')

        # Obtener el directorio actual de la sesión
        if session_id not in SESSION_CWD:
            SESSION_CWD[session_id] = WORKING_DIR
        
        current_cwd = SESSION_CWD[session_id]

        # Detectar si es un comando cd para actualizar el cwd
        if command.startswith('cd '):
            target_dir = command[3:].strip()
            # Si es cd sin argumentos o cd ~, ir a WORKING_DIR
            if not target_dir or target_dir == '~':
                target_dir = WORKING_DIR
            # Si es relativo, construir la ruta desde current_cwd
            if not target_dir.startswith('/'):
                target_dir = os.path.join(current_cwd, target_dir)
            # Normalizar la ruta
            target_dir = os.path.normpath(target_dir)
            SESSION_CWD[session_id] = target_dir
            # El comando cd se ejecutará de todas formas para validar que existe
            command = f"cd {target_dir}"
        
        # Prefijar el comando con cd al directorio actual
        full_command = f"cd {current_cwd} && {command}"

        print(f"[*] Iniciando Job: {command} en {current_cwd} (wait={wait_time}s, exit={exit_time}s)")

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
            cwd=WORKING_DIR,
            text=True
        )

        JOBS[job_id] = {
            "proc": proc,
            "out_file": out_file,
            "err_file": err_file,
            "out_path": out_path,
            "err_path": err_path,
            "command": command,
            "session_id": session_id,
            "start_time": time.time()
        }
        
        # Guardar en historial de la sesión
        if session_id not in SESSION_HISTORY:
            SESSION_HISTORY[session_id] = []
        
        SESSION_HISTORY[session_id].append({
            "job_id": job_id,
            "command": command,
            "timestamp": time.time(),
            "cwd": current_cwd
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
        if not is_running and session_id in SESSION_HISTORY:
            for entry in reversed(SESSION_HISTORY[session_id]):
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
            "cwd": SESSION_CWD[session_id]
        }
        
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
                              jobs=[],
                              sessions=[])
    
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


@app.route('/admin', methods=['GET'])
def admin_panel():
    """Panel de administración: muestra sesiones, jobs en ejecución, etc."""
    # Recopilar información de todos los jobs
    jobs_info = []
    for job_id, job in JOBS.items():
        proc = job["proc"]
        is_running = (proc.poll() is None)
        
        jobs_info.append({
            "job_id": job_id,
            "command": job["command"],
            "session_id": job.get("session_id", "default"),
            "status": "running" if is_running else "finished",
            "return_code": proc.poll(),
            "started_at": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(job["start_time"])),
            "start_time": job["start_time"],
            "elapsed": round(time.time() - job["start_time"], 1)
        })
    
    # Información de sesiones
    sessions_info = [
        {"session_id": sid, "cwd": cwd, "commands_count": len(SESSION_HISTORY.get(sid, []))}
        for sid, cwd in SESSION_CWD.items()
    ]
    
    return render_template('admin.html', 
                          total_jobs=len(JOBS),
                          active_sessions=len(SESSION_CWD),
                          jobs=jobs_info,
                          sessions=sessions_info)


@app.route('/', methods=['GET'])
def index():
    """Sirve la interfaz web simple para usar la API."""
    return render_template('index.html')

if __name__ == '__main__':
    # Host '0.0.0.0' es OBLIGATORIO para que Docker deje entrar conexiones de fuera
    app.run(host='0.0.0.0', port=5000, debug=True)