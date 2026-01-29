# Documentación Técnica: KaliSandbox (Backend del Agente)

## 1. Visión General

El **KaliSandbox** es un entorno de ejecución aislado basado en Docker que permite al agente de IA ejecutar comandos de ciberseguridad de forma segura. Funciona como un contenedor Kali Linux con una API REST Flask que expone endpoints para ejecutar comandos, gestionar jobs en background y mantener sesiones persistentes con control de versiones Git.

### 1.1 Arquitectura General

```
┌─────────────────────────────────────────────────────────────┐
│                    INFRAESTRUCTURA DOCKER                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌─────────────────┐    RED AISLADA (10.10.0.0/24)         │
│   │   AGENTE (API)  │◄───────────────────────────────────┐  │
│   │   10.10.0.2     │                                    │  │
│   │   Puerto 5000   │    ┌─────────────────┐            │  │
│   │   Flask/Python  │    │  DVWA (Victim)  │            │  │
│   └────────┬────────┘    │   10.10.0.3     │            │  │
│            │             └─────────────────┘            │  │
│            │             ┌─────────────────┐            │  │
│   ┌────────▼────────┐    │ Metasploitable  │            │  │
│   │ /workspace_     │    │   10.10.0.4     │            │  │
│   │   sessions/     │    └─────────────────┘            │  │
│   │ (Git repos)     │    ┌─────────────────┐            │  │
│   └─────────────────┘    │  Juice Shop     │◄───────────┘  │
│                          │   10.10.0.5     │               │
│                          └─────────────────┘               │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Infraestructura Docker

### 2.1 Docker Compose

El archivo `docker-compose.yml` define 4 servicios en una red aislada:

#### 2.1.1 Servicio `attacker` (Agente Principal)

```yaml
attacker:
  build: .
  container_name: agente-tfg
  privileged: true
  ports:
    - "5000:5000"
  volumes:
    - ./script:/app
    - persistent_storage:/workspace_persistent
    - sessions_storage:/workspace_sessions
  networks:
    hacking_net:
      ipv4_address: 10.10.0.2
  command: python3 /app/agent_api.py
```

**Características:**
- **IP Fija**: `10.10.0.2` en la red del laboratorio
- **Modo Privilegiado**: Necesario para herramientas de red avanzadas
- **Volúmenes**:
  - `/app`: Código de la API (montado desde `./script`)
  - `/workspace_persistent`: Herramientas compartidas entre sesiones
  - `/workspace_sessions`: Repositorios Git por conversación

#### 2.1.2 Máquinas Víctimas

| Servicio | Imagen | IP | Puerto Expuesto | Descripción |
|----------|--------|----|-----------------| ------------|
| `victim` | `vulnerables/web-dvwa` | 10.10.0.3 | 8010:80 | DVWA - Damn Vulnerable Web App |
| `meta_victim` | `tleemcjr/metasploitable2` | 10.10.0.4 | 8030:80 | Metasploitable 2 |
| `juice_victim` | `bkimminich/juice-shop` | 10.10.0.5 | 8020:3000 | OWASP Juice Shop |

#### 2.1.3 Red Aislada

```yaml
networks:
  hacking_net:
    driver: bridge
    ipam:
      config:
        - subnet: 10.10.0.0/24
```

**Propósito**: Red tipo "laboratorio de hacking" completamente aislada del host, permitiendo escaneos y ataques sin afectar redes reales.

### 2.2 Dockerfile

El Dockerfile construye una imagen Kali Linux con herramientas de pentesting organizadas en fases:

#### Fase 1: Base y Herramientas Clásicas
```dockerfile
FROM kalilinux/kali-rolling
RUN apt-get update && apt-get install -y \
    nmap sqlmap nikto hydra ffuf whatweb curl jq exploitdb wget \
    iputils-ping netcat-traditional dnsutils samba-client \
    python3 python3-pip python3-flask python3-setuptools wordlists \
    git unzip lynx chromium
```

#### Fase 2: Herramientas ProjectDiscovery + Arjun
- **Nuclei** v3.1.0: Scanner de vulnerabilidades basado en templates
- **Katana** v1.1.0: Spider web con soporte headless/JS
- **Subfinder** v2.6.3: Descubrimiento de subdominios
- **Arjun**: Descubrimiento de parámetros HTTP ocultos

#### Fase 3: Análisis de JavaScript
- **pup**: Parser de HTML
- **LinkFinder**: Extracción de endpoints desde JS
- **SecretFinder**: Búsqueda de secretos en JS
- **OWASP ZAP**: Scanner de seguridad web automatizado

#### Fase 4: Dependencias Python
```dockerfile
RUN pip3 install flask-cors gitpython --break-system-packages
```

#### Estructura de Directorios
```
/workspace              # Directorio de trabajo temporal
/workspace_persistent   # Herramientas compartidas (volumen Docker)
/workspace_sessions     # Repos Git por conversación (volumen Docker)
/usr/share/wordlists    # Wordlists (rockyou.txt descomprimido)
```

---

## 3. API REST (agent_api.py)

### 3.1 Configuración y Dependencias

```python
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import subprocess, os, uuid, time, signal
from pathlib import Path
from datetime import datetime
import git  # GitPython para control de versiones
```

**Constantes de Configuración:**
```python
WORKING_DIR = "/workspace"
SESSIONS_BASE = "/workspace_sessions"     # Repos git por conversación
PERSISTENT_DIR = "/workspace_persistent"  # Herramientas compartidas
INVENTORY_PATH = f"{PERSISTENT_DIR}/INVENTORY.md"
```

### 3.2 Estructuras de Datos en Memoria

```python
JOBS = {}               # {job_id: {proc, out_file, command, conversation_id, ...}}
CONVERSATION_REPOS = {} # {conversation_id: git.Repo}
LEAF_COMMITS = {}       # {"conv_id_leaf_id": commit_sha}
JOBS_BY_CONV = {}       # {conversation_id: [job_ids]}
SESSION_CWD = {}        # {conversation_id: current_working_dir}
SESSION_HISTORY = {}    # {conversation_id: [entries]}
```

### 3.3 Endpoints Principales

#### 3.3.1 Ejecución de Comandos

**`POST /execute`**

Ejecuta un comando en el sandbox con soporte para ejecución en background.

**Request:**
```json
{
  "command": "nmap -sV 10.10.0.3",
  "wait_time": 10,
  "exit_time": 60,
  "conversation_id": "conv_abc123",
  "leaf_id": 42
}
```

**Parámetros:**
| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `command` | string | Comando bash a ejecutar |
| `wait_time` | int | Segundos a esperar antes de devolver salida parcial |
| `exit_time` | int | Segundos máximos de ejecución (mata el proceso después) |
| `conversation_id` | string | ID de conversación (crea repo Git aislado) |
| `leaf_id` | int | ID del nodo en el árbol de mensajes |

**Comportamiento:**
1. Si `exit_time > 0`: Espera ese tiempo, si el proceso sigue vivo lo mata (SIGINT → SIGTERM → SIGKILL)
2. Si `wait_time > 0` (sin exit_time): Espera pero el proceso sigue en background
3. Sin parámetros: Espera 0.1s (captura comandos instantáneos)

**Response:**
```json
{
  "status": "running",
  "job_id": "uuid-123...",
  "return_code": null,
  "stdout": "Starting Nmap...",
  "stderr": "",
  "cwd": "/workspace_sessions/conv_abc123",
  "conversation_id": "conv_abc123"
}
```

#### 3.3.2 Consulta de Estado

**`GET /status/<job_id>`**

```json
{
  "status": "finished",
  "return_code": 0,
  "stdout": "Nmap scan report...",
  "stderr": "",
  "cwd": "/workspace_sessions/conv_abc123"
}
```

**Soporte Long Polling:** `GET /status/<job_id>?wait=10` espera hasta 10 segundos si el proceso sigue corriendo.

#### 3.3.3 Cancelación de Jobs

**`POST /stop/<job_id>`**

Secuencia de terminación:
1. `SIGINT` (Ctrl+C) - Espera 2s
2. `SIGTERM` - Espera 1s
3. `SIGKILL` - Fuerza terminación

### 3.4 Sistema de Sesiones Git

Cada conversación tiene su propio repositorio Git aislado, permitiendo:
- **Snapshots por mensaje**: Cada respuesta del LLM crea un commit
- **Ramificación**: Navegar entre ramas del árbol de conversación
- **Restauración**: Volver al estado del filesystem en cualquier punto

#### 3.4.1 Inicialización de Sesión

**`POST /session/init`**

```json
{"conversation_id": "conv_abc123"}
```

Crea:
```
/workspace_sessions/conv_abc123/
├── .git/
└── README.md
```

Configuración Git:
- `user.name`: "Cerebro Agent"
- `user.email`: "agent@tfg.local"

#### 3.4.2 Checkpoints

**`POST /session/checkpoint`**

```json
{
  "conversation_id": "conv_abc123",
  "leaf_id": "msg_42",
  "parent_leaf_id": "msg_41"
}
```

Acciones:
1. Si tiene `parent_leaf_id`, hace checkout a ese tag
2. `git add -A` (todos los cambios)
3. `git commit -m "Checkpoint: {leaf_id}"`
4. Crea tag `leaf_{leaf_id}`

#### 3.4.3 Cambio de Rama

**`POST /session/switch`**

```json
{
  "conversation_id": "conv_abc123",
  "leaf_id": "msg_35"
}
```

Ejecuta `git checkout leaf_msg_35 --force`, restaurando el estado del filesystem.

### 3.5 Compresión de Output

La función `compress_output()` agrupa líneas similares para reducir tokens:

**Entrada:**
```
Ping... time=10ms
Ping... time=11ms
Ping... time=12ms
```

**Salida:**
```
Ping... time={ 10ms, 11ms, 12ms }
```

**Algoritmo:**
1. Encuentra prefijo común entre líneas consecutivas
2. Si el prefijo es >20 caracteres o >60% de la longitud, agrupa
3. Formato: `{prefijo}{ sufijo1, sufijo2, ... }`

### 3.6 Almacenamiento Persistente

**`/workspace_persistent/`** es un volumen Docker compartido:

```
/workspace_persistent/
├── tools/        # Herramientas instaladas (sqlmap, metasploit)
├── wordlists/    # Wordlists personalizadas
├── downloads/    # Descargas temporales grandes
└── INVENTORY.md  # Catálogo de herramientas instaladas
```

**INVENTORY.md** se genera automáticamente al iniciar para evitar descargas duplicadas:

```markdown
# 🗂️ Persistent Tools Inventory

| Tool | Path | Size | Version | Date Added |
|------|------|------|---------|------------|
| sqlmap | /workspace_persistent/tools/sqlmap | 15MB | 1.7 | 2025-01-15 |
```

### 3.7 Panel de Administración Web

**`GET /admin`**

Interfaz web con:
- Total de jobs activos
- Sesiones por conversación
- Filtrado por conversation_id
- Estado de repos Git

**`GET /admin/api/conversations`** - Lista conversaciones con repos Git
**`GET /admin/api/running`** - Jobs en ejecución agrupados por conversación

### 3.8 Historial de Comandos

**`GET /history/<session_id>`**

Devuelve el historial optimizado para tokens:
- Si todos los comandos son del mismo día: solo hora en cada entrada
- Si hay múltiples días: fecha y hora completa

```json
{
  "session_id": "conv_abc123",
  "date": "2025-01-28",
  "cwd_actual": "/workspace_sessions/conv_abc123/scans",
  "total_commands": 15,
  "history": [
    {"command": "nmap -sV 10.10.0.3", "cwd": "/workspace", "timestamp": "14:32:15"}
  ]
}
```

---

## 4. Interfaz Web del Terminal

### 4.1 Frontend (index.html + app.js)

Interfaz web simple para testing manual:

```html
<div id="terminal" class="terminal"></div>
<form id="cmdForm">
  <input id="cmdInput" placeholder="whoami" />
  <button id="sendBtn">Enviar</button>
  <button id="cancelBtn" style="display:none">Cancelar</button>
</form>
```

### 4.2 Polling de Jobs

```javascript
async function startPolling(jobId) {
  pollInterval = setInterval(async () => {
    const res = await fetch(`/status/${jobId}`);
    const j = await res.json();
    
    // Solo mostrar contenido nuevo (delta)
    if (j.stdout && j.stdout.length > lastStdoutLen) {
      appendLine(j.stdout.substring(lastStdoutLen));
      lastStdoutLen = j.stdout.length;
    }
    
    if (j.status !== 'running') {
      clearInterval(pollInterval);
    }
  }, 1000);
}
```

### 4.3 Estilos (style.css)

Tema oscuro con variables CSS:
```css
:root {
  --bg: #0b0f12;
  --panel: #0f1720;
  --text: #dbe6ef;
  --accent: #4fd1c5;
}
```

---

## 5. Herramientas de Pentesting Incluidas

### 5.1 Reconocimiento
| Herramienta | Uso |
|-------------|-----|
| nmap | Escaneo de puertos y servicios |
| masscan | Escaneo de puertos a gran escala |
| subfinder | Descubrimiento de subdominios |
| whatweb | Fingerprinting web |
| dig/nslookup | Resolución DNS |

### 5.2 Escaneo de Vulnerabilidades
| Herramienta | Uso |
|-------------|-----|
| nikto | Scanner de vulnerabilidades web |
| nuclei | Scanner basado en templates |
| sqlmap | Detección y explotación de SQLi |
| wpscan | Scanner de WordPress |

### 5.3 Fuzzing y Bruteforce
| Herramienta | Uso |
|-------------|-----|
| ffuf | Web fuzzer rápido |
| gobuster | Directory/DNS bruteforce |
| hydra | Bruteforce de credenciales |
| john | Password cracking |

### 5.4 Explotación
| Herramienta | Uso |
|-------------|-----|
| searchsploit | Base de datos de exploits |
| metasploit | Framework de explotación |
| netcat | Conexiones de red/shells |

### 5.5 Análisis de JavaScript
| Herramienta | Uso |
|-------------|-----|
| katana | Spider con soporte headless |
| LinkFinder | Extracción de endpoints |
| SecretFinder | Búsqueda de secretos |
| arjun | Descubrimiento de parámetros |

---

## 6. Seguridad y Aislamiento

### 6.1 Niveles de Aislamiento

1. **Red Docker**: Subred `10.10.0.0/24` aislada
2. **Volúmenes separados**: Cada conversación tiene su propio repo Git
3. **Sin acceso a Internet**: Las víctimas no tienen salida a Internet
4. **Modo privilegiado controlado**: Solo el contenedor atacante

### 6.2 Persistencia de Datos

- **Volúmenes nombrados**: `persistent_storage` y `sessions_storage` sobreviven a reinicios
- **Git como backup**: Cada estado del filesystem es un commit recuperable
- **INVENTORY.md**: Evita reinstalar herramientas grandes

### 6.3 Límites de Recursos

El modo privilegiado permite:
- Captura de paquetes (tcpdump)
- Manipulación de interfaces de red
- Ejecución de herramientas que requieren CAP_NET_RAW

---

## 7. Flujo de Ejecución de un Comando

```
┌─────────────┐     POST /execute      ┌─────────────────┐
│   Backend   │ ─────────────────────► │   agent_api.py  │
│    LLM      │                        │                 │
└─────────────┘                        └────────┬────────┘
                                                │
                                                ▼
                                       ┌────────────────┐
                                       │ Determinar CWD │
                                       │ (SESSION_CWD)  │
                                       └────────┬───────┘
                                                │
                                                ▼
                                       ┌────────────────┐
                                       │ subprocess.    │
                                       │ Popen(command) │
                                       │ → stdout/err   │
                                       │   a archivos   │
                                       └────────┬───────┘
                                                │
                              ┌─────────────────┴─────────────────┐
                              │                                   │
                              ▼                                   ▼
                     wait_time > 0?                       exit_time > 0?
                              │                                   │
                              ▼                                   ▼
                     Esperar N segundos              Esperar N segundos
                     (proceso continúa)              Si sigue vivo: KILL
                              │                                   │
                              └─────────────┬─────────────────────┘
                                            │
                                            ▼
                                   ┌────────────────┐
                                   │ Leer stdout/   │
                                   │ stderr parcial │
                                   └────────┬───────┘
                                            │
                                            ▼
                                   ┌────────────────┐
                                   │ Guardar en     │
                                   │ JOBS + HISTORY │
                                   └────────┬───────┘
                                            │
                                            ▼
                                   ┌────────────────┐
                                   │ Response JSON  │
                                   │ {job_id, ...}  │
                                   └────────────────┘
```

---

## 8. Integración con el Sistema

### 8.1 Comunicación con Backend LLM

El Backend LLM se comunica con el KaliSandbox vía HTTP:

```python
# Desde routes/chat.py
SANDBOX_URL = "http://localhost:5000"

async with httpx.AsyncClient(timeout=120.0) as client:
    response = await client.post(f"{SANDBOX_URL}/execute", json=payload)
```

### 8.2 Sincronización Git con el Árbol de Conversación

1. Usuario envía mensaje → Backend LLM procesa
2. LLM ejecuta comando → KaliSandbox devuelve resultado
3. Backend guarda mensaje → Llama a `/session/checkpoint`
4. Usuario navega en árbol → Frontend llama a `/session/switch`
5. KaliSandbox restaura estado del filesystem

---

## 9. Limitaciones Conocidas

1. **Sin persistencia de procesos**: Si Docker se reinicia, los jobs se pierden
2. **Memoria limitada**: JOBS crece indefinidamente sin limpieza automática
3. **Git sin compactación**: Los repos pueden crecer mucho con muchos commits
4. **Timeout fijo**: 120s de timeout en el cliente puede ser insuficiente para scans largos

---

## 10. Extensibilidad

### 10.1 Añadir Nuevas Herramientas

1. Añadir al Dockerfile en la fase correspondiente
2. Actualizar INVENTORY.md si es herramienta grande
3. Reconstruir imagen: `docker-compose build attacker`

### 10.2 Añadir Nuevas Víctimas

1. Añadir servicio en `docker-compose.yml`
2. Asignar IP en la red `hacking_net`
3. El agente podrá acceder automáticamente

### 10.3 Añadir Nuevos Endpoints

1. Crear función en `agent_api.py`
2. Decorar con `@app.route()`
3. La API estará disponible automáticamente
