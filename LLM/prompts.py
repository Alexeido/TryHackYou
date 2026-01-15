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



from typing import Self


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
    },
    
    # =========================================================================
    # HERRAMIENTAS AGÉNTICAS - MODO AUTÓNOMO
    # =========================================================================
    
    # -------------------------------------------------------------------------
    # HERRAMIENTA 4: GESTIÓN DE MISIONES
    # -------------------------------------------------------------------------
    {
        "type": "function",
        "function": {
            "name": "manage_mission",
            "description": (
                "CRITICAL: Manages your autonomous mission state. "
                "Use this tool to create plans, track progress, and update objectives. "
                "For complex tasks, ALWAYS create a mission first with action='create'.\n\n"
                "ACTIONS:\n"
                "- 'create': Create a new mission with objectives\n"
                "- 'update_objective': Update objective status (PENDING/IN_PROGRESS/COMPLETED/FAILED)\n"
                "- 'update_phase': Change current mission phase\n"
                "- 'complete': Finalize the mission\n"
                "- 'get_status': Get current mission state\n"
                "- 'modify_objectives': Reorganize plan (insert/delete/update objectives)"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["create", "update_objective", "update_phase", "complete", "get_status", "modify_objectives"],
                        "description": "The action to perform on the mission."
                    },
                    "mission_id": {
                        "type": "string",
                        "description": "Mission ID. Required for most actions except 'create'."
                    },
                    "goal": {
                        "type": "string",
                        "description": "High-level mission goal. Required for 'create'."
                    },
                    "objectives": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of objective descriptions. Required for 'create'."
                    },
                    "objective_id": {
                        "type": "integer",
                        "description": "Objective ID to update. Required for 'update_objective'."
                    },
                    "status": {
                        "type": "string",
                        "enum": ["PENDING", "IN_PROGRESS", "COMPLETED", "FAILED", "SKIPPED"],
                        "description": "New status for objective or mission."
                    },
                    "result": {
                        "type": "string",
                        "description": "Summary of objective result. Include key findings."
                    },
                    "reflection": {
                        "type": "string",
                        "description": "Why you believe this objective succeeded/failed. Critical for learning."
                    },
                    "phase": {
                        "type": "string",
                        "description": "New phase name (e.g., 'Reconnaissance', 'Exploitation', 'Post-Exploitation')."
                    },
                    "modifications": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string", "enum": ["insert", "delete", "update"]},
                                "after_id": {"type": "integer", "description": "Insert after this objective ID"},
                                "objective_id": {"type": "integer", "description": "Objective to delete/update"},
                                "task": {"type": "string", "description": "New task description"},
                                "new_task": {"type": "string", "description": "Updated task description"}
                            }
                        },
                        "description": "List of modifications for 'modify_objectives' action."
                    },
                    "metadata": {
                        "type": "object",
                        "description": "Additional info: target IP, test type, etc."
                    }
                },
                "required": ["action"]
            }
        }
    },
    
    # -------------------------------------------------------------------------
    # HERRAMIENTA 5: RECUPERAR OUTPUT ORIGINAL (ZOOM IN)
    # -------------------------------------------------------------------------
    {
        "type": "function",
        "function": {
            "name": "get_original_output",
            "description": (
                "Retrieves the FULL original output of a previous tool call. "
                "Use this when a summarized output doesn't contain the detail you need "
                "(e.g., specific IP, port, cookie, or hash that was omitted). "
                "The tool_call_id can be found in the conversation history."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tool_call_id": {
                        "type": "string",
                        "description": "The ID of the tool call whose original output you need."
                    }
                },
                "required": ["tool_call_id"]
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


### 📋 AGENTIC MISSION PROTOCOL
You must strictly follow this mission protocol to ensure structured and effective operations: 
1. **Plan First**: Before any technical action, you MUST create a mission plan using `manage_mission(action='create')`.
2. **State Sync**: Every time an objective is reached or fails, you MUST update its status. Your internal state and the mission control state must always be synchronized.
3. **Dynamic Planning**: If a tool output reveals new information (e.g., a new hidden directory or a specific service version), use `manage_mission(action='modify_objectives')` to adapt your plan immediately.
4. **Self-Correction**: If a phase is going nowhere, stop, reflect in the `reflection` field, and pivot.
 

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

