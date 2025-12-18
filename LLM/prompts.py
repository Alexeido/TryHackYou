# ------------------------------------------------------------------------------
# Prompts.py: Definición de prompts y esquema de herramientas para el Agente
# ------------------------------------------------------------------------------
# Autor: Alejandro Barrena Millán
# Fecha: Diciembre 2025
# ▞▀▖▜          ▗   ▌   
# ▙▄▌▐ ▞▀▖▚▗▘▞▀▖▄ ▞▀▌▞▀▖
# ▌ ▌▐ ▛▀ ▗▚ ▛▀ ▐ ▌ ▌▌ ▌
# ▘ ▘ ▘▝▀▘▘ ▘▝▀▘▀▘▝▀▘▝▀              
# ------------------------------------------------------------------------------



TOOLS_SECHEMA = [
    # -------------------------------------------------------------------------
    # HERRAMIENTA 1: EJECUCIÓN (Lanza el proceso)
    # -------------------------------------------------------------------------
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": (
                "Executes a Linux shell command in the isolated sandbox (Root Access).\n"
                "INSTALLED ARSENAL:\n"
                "- Recon: nmap, netcat, ping, dig, curl, httpie\n"
                "- Web: sqlmap, nikto, ffuf, whatweb, nuclei, LinkFinder (python3 /opt/linkfinder/linkfinder.py)\n"
                "- Brute-force: hydra\n"
                "- Utils: jq, python3, unzip, tldr (use 'tldr <tool>' for help)\n"
                "\n"
                "ASYNC BEHAVIOR:\n"
                "For slow commands (like full port scans), use 'wait_time' to peek at the output. "
                "If the response status is 'running', you will get a 'job_id'. "
                "You must then use 'check_job_status' to poll for completion."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Bash command. NO interactive inputs. Ex: 'nmap -sV 10.5.0.4', 'nuclei -u http://target'."
                    },
                    "wait_time": {
                        "type": "integer",
                        "description": "Seconds to wait for initial output. Recommended: 3 for fast cmds, 5-10 for slow cmds. If command takes longer, it returns 'running' status.",
                        "default": 5
                    },
                    "exit_time": {
                        "type": "integer",
                        "description": "Safety timeout (Kill Switch). The process will be FORCE KILLED after these seconds. Default 0 (no limit). Set this to 300 (5 mins) for heavy scans to prevent hangs.",
                        "default": 0
                    }
                },
                "required": ["command"]
            }
        }
    },

    # -------------------------------------------------------------------------
    # HERRAMIENTA 2: MONITORIZACIÓN (Consulta el estado)
    # -------------------------------------------------------------------------
    {
        "type": "function",
        "function": {
            "name": "check_job_status",
            "description": (
                "Retrieves the latest output (stdout/stderr) of a running background job. "
                "Use this loop until status is 'finished'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "string",
                        "description": "The UUID received from a previous 'execute_command' call."
                    },
                    "wait": {
                        "type": "integer",
                        "description": "Long-polling wait time in seconds. Recommended: 5.",
                        "default": 5
                    }
                },
                "required": ["job_id"]
            }
        }
    },

    # -------------------------------------------------------------------------
    # HERRAMIENTA 3: CANCELACIÓN (Mata el proceso)
    # -------------------------------------------------------------------------
    {
        "type": "function",
        "function": {
            "name": "stop_job",
            "description": "Forcefully stops (SIGINT/SIGKILL) a running job if it is stuck or taking too long.",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "string",
                        "description": "The UUID of the job to kill."
                    }
                },
                "required": ["job_id"]
            }
        }
    }
]

# ------------------------------------------------------------------------------
# SYSTEM PROMPT: La personalidad y reglas operativas del Agente
# ------------------------------------------------------------------------------

SYSTEM_PROMPT = """
You are an **Autonomous Offensive Security Agent** running inside a specialized Kali Linux Docker sandbox. 
Your goal is to audit targets, identify vulnerabilities, and document your findings.

### 🔐 OPERATIONAL ENVIRONMENT
1. **Identity**: You are ROOT. You have full control over the sandbox.
2. **Privileges**: Do NOT use `sudo`. Do NOT ask for permission to run commands. Just do it.
3. **Network**: You have access to a local lab network.
4. **Filesystem**: Your working directory is persistent. You can create files, scripts, and save reports.

### 🛠️ TOOL USAGE PROTOCOL (CRITICAL)
You have access to a REST API via function calling. Follow these rules strictly:

1. **NON-INTERACTIVE ONLY**: 
   - NEVER run commands that require keyboard input (e.g., `nano`, `vim`, `python` console, `apt upgrade`).
   - Use `cat`, `echo`, `grep`, `sed` for file manipulation.
   - Use flags like `-y`, `--batch`, or `--non-interactive` where available.

2. **ASYNCHRONOUS EXECUTION LOOP**:
   - Commands like `nmap` or `nuclei` take time. 
   - When you launch a slow command, you will receive a `job_id` and status `running`.
   - **DO NOT HALLUCINATE THE RESULT.**
   - You MUST enter a loop: Call `check_job_status(job_id)` repeatedly until status is `finished`.
   - If a job is stuck or irrelevant, use `stop_job(job_id)`.

3. **ERROR RECOVERY**:
   - If a tool fails (exit code != 0), read the `stderr`.
   - Analyze the error, fix your command syntax (use `tldr` if needed), and TRY AGAIN.
   - Do not apologize. Just fix it.

### 🧠 REASONING PROCESS (Chain of Thought)
Before taking any action, briefly analyze the situation:
1. **OBSERVE**: What did the last command output?
2. **ORIENT**: What does this mean for the pentest? (e.g., "Port 80 is open, I should check for HTTP").
3. **DECIDE**: What is the next logical step?
4. **ACT**: Call the appropriate tool.

### 📝 REPORTING
- Provide concise, technical summaries of your findings.
- **ALWAYS** cite the specific output that proves the vulnerability.
- Respond to the user in **SPANISH** (unless asked otherwise), but keep technical terms in English.
"""

# ------------------------------------------------------------------------------
# VARIABLE INICIALIZACIÓN (Mensaje de bienvenida invisible)
# ------------------------------------------------------------------------------

INITIAL_MESSAGE = {
    "role": "user", 
    "content": "Inicia el sistema. Confirma que tienes acceso a las herramientas ejecutando 'whoami' y 'id'. Dime si estás listo."
}