/**
 * Tool Definitions - Schemas de herramientas disponibles para el LLM
 * Estas herramientas se envían al modelo para que pueda invocarlas
 */

export interface ToolDefinition {
  type: "function";
  function: {
    name: string;
    description: string;
    parameters: {
      type: "object";
      properties: Record<string, unknown>;
      required: string[];
    };
  };
}

/**
 * Herramienta: execute_command
 * Ejecuta comandos shell en el sandbox Kali Linux
 */
export const EXECUTE_COMMAND_TOOL: ToolDefinition = {
  type: "function",
  function: {
    name: "execute_command",
    description: `Executes a shell command in a Kali Linux sandbox environment. Use this for:
- Network scanning (nmap, masscan)
- Web vulnerability scanning (nikto, sqlmap, ffuf)
- Information gathering (whois, dig, curl, wget)
- Brute force attacks (hydra, john - only in authorized pentests)
- Exploitation (metasploit, searchsploit)
- File operations (ls, cat, grep, find)
- Any other Linux command

The command runs in a persistent workspace that is:
- Isolated per conversation (each chat has its own directory)
- Version-controlled with git (creates checkpoints after each response)
- Shared access to /workspace_persistent/ for heavy tools (sqlmap, metasploit, wordlists)

Important notes:
- Always check /workspace_persistent/INVENTORY.md before downloading heavy tools
- Use absolute paths or verify current directory with 'pwd'
- Commands run as root in the Kali container

BACKGROUND EXECUTION with wait_time:
When you use wait_time, the command runs in background. You'll get:
1. Partial output after wait_time seconds
2. A job_id to check progress later with check_job_status
3. The full output will be delivered automatically when the job completes

Example: For a long nmap scan, use wait_time=10 to get initial results, then the final output arrives automatically when done.`,
    parameters: {
      type: "object",
      properties: {
        command: {
          type: "string",
          description: "The shell command to execute (bash syntax)"
        },
        wait_time: {
          type: "number",
          description: "Seconds to wait before returning partial output. The command continues running in background and you'll receive the final output automatically when it completes. Use 5-10 for quick commands, 15-30 for scans. If not set, waits for command to fully complete.",
        },
        exit_time: {
          type: "number",
          description: "Force-stop the command after this many seconds and return whatever output exists. Use this when you need results within a time limit. Takes precedence over wait_time.",
        }
      },
      required: ["command"]
    }
  }
};

/**
 * Herramienta: check_job_status
 * Consulta el estado de un job en background
 */
export const CHECK_JOB_STATUS_TOOL: ToolDefinition = {
  type: "function",
  function: {
    name: "check_job_status",
    description: `Check the status and output of a background job. Use this when:
- The user asks about the progress of a running scan/command
- You want to see partial output of a long-running process
- You need to verify if a background job has completed

Returns the current status (running/finished), output so far, and execution time.`,
    parameters: {
      type: "object",
      properties: {
        job_id: {
          type: "string",
          description: "The job_id returned from a previous execute_command call"
        },
        wait: {
          type: "number",
          description: "Optional: seconds to wait for new output if job is still running (long-polling). Default: 0 (return immediately)",
        }
      },
      required: ["job_id"]
    }
  }
};

// ============================================================================
// HERRAMIENTAS AGÉNTICAS - MODO AUTÓNOMO
// ============================================================================

/**
 * Herramienta: manage_mission
 * Gestiona el estado de misiones autónomas del agente
 */
export const MANAGE_MISSION_TOOL: ToolDefinition = {
  type: "function",
  function: {
    name: "manage_mission",
    description: `CRITICAL: Manages your autonomous mission state. Use this tool to create plans, track progress, and update objectives.

For complex tasks (like "get root access", "perform full pentest", etc.), you MUST:
1. Create a mission FIRST with action='create'
2. Update objective status as you progress
3. Complete the mission when done

ACTIONS:
- 'create': Create a new mission with objectives (REQUIRED before starting autonomous work)
- 'update_objective': Update objective status (PENDING/IN_PROGRESS/COMPLETED/FAILED/SKIPPED)
- 'update_phase': Change current mission phase (e.g., "Reconnaissance", "Exploitation")
- 'complete': Finalize the mission
- 'get_status': Get current mission state
- 'modify_objectives': Reorganize plan (insert/delete/update objectives dynamically)`,
    parameters: {
      type: "object",
      properties: {
        action: {
          type: "string",
          enum: ["create", "update_objective", "update_phase", "complete", "get_status", "modify_objectives"],
          description: "The action to perform on the mission."
        },
        mission_id: {
          type: "string",
          description: "Mission ID. Required for most actions except 'create'."
        },
        goal: {
          type: "string",
          description: "High-level mission goal. Required for 'create'. Example: 'Obtain root access on 10.5.0.5'"
        },
        objectives: {
          type: "array",
          items: { type: "string" },
          description: "List of objective descriptions. Required for 'create'. Example: ['Reconnaissance', 'Enumeration', 'Exploitation', 'Post-exploitation', 'Documentation']"
        },
        objective_id: {
          type: "integer",
          description: "Objective ID to update. Required for 'update_objective'."
        },
        status: {
          type: "string",
          enum: ["PENDING", "IN_PROGRESS", "COMPLETED", "FAILED", "SKIPPED"],
          description: "New status for objective or mission."
        },
        result: {
          type: "string",
          description: "Summary of objective result. Include key findings like IPs, ports, versions, vulnerabilities."
        },
        reflection: {
          type: "string",
          description: "Why you believe this objective succeeded/failed. Critical for learning and adaptation."
        },
        phase: {
          type: "string",
          description: "New phase name for 'update_phase'. Examples: 'Reconnaissance', 'Exploitation', 'Post-Exploitation'"
        },
        modifications: {
          type: "array",
          items: {
            type: "object",
            properties: {
              type: { type: "string", enum: ["insert", "delete", "update"] },
              after_id: { type: "integer", description: "Insert after this objective ID" },
              objective_id: { type: "integer", description: "Objective to delete/update" },
              task: { type: "string", description: "New task description" },
              new_task: { type: "string", description: "Updated task description" }
            }
          },
          description: "List of modifications for 'modify_objectives' action."
        },
        metadata: {
          type: "object",
          description: "Additional info: target IP, test type, etc."
        }
      },
      required: ["action"]
    }
  }
};

/**
 * Herramienta: stop_job
 * Detiene un proceso en background
 */
export const STOP_JOB_TOOL: ToolDefinition = {
  type: "function",
  function: {
    name: "stop_job",
    description: `Forcefully stops a running background job. Use when:
- A scan is taking too long and you want to proceed
- The process is stuck or unresponsive
- You've gathered enough partial output

This sends SIGTERM then SIGKILL to the process.`,
    parameters: {
      type: "object",
      properties: {
        job_id: {
          type: "string",
          description: "The job_id of the background process to stop"
        }
      },
      required: ["job_id"]
    }
  }
};

/**
 * Herramienta: get_original_output
 * Recupera el output original completo de un comando resumido
 */
export const GET_ORIGINAL_OUTPUT_TOOL: ToolDefinition = {
  type: "function",
  function: {
    name: "get_original_output",
    description: `Retrieves the FULL original output of a previous tool call whose output was summarized.

Use this when a summarized output doesn't contain the detail you need, such as:
- Specific IP addresses that were omitted
- Port numbers or service versions
- Cookies, tokens, or hashes
- Any other critical technical detail

The tool_call_id can be found in the conversation history from previous tool executions.`,
    parameters: {
      type: "object",
      properties: {
        tool_call_id: {
          type: "string",
          description: "The ID of the tool call whose original output you need to retrieve"
        }
      },
      required: ["tool_call_id"]
    }
  }
};

/**
 * Todas las herramientas disponibles
 * Agregar aquí nuevas tools cuando se implementen
 */
export const ALL_TOOLS: ToolDefinition[] = [
  EXECUTE_COMMAND_TOOL,
  CHECK_JOB_STATUS_TOOL,
  MANAGE_MISSION_TOOL,
  STOP_JOB_TOOL,
  GET_ORIGINAL_OUTPUT_TOOL,
];

/**
 * Obtiene las herramientas en el formato que espera la API del LLM
 */
export function getToolsForAPI(): Record<string, unknown>[] {
  return ALL_TOOLS as unknown as Record<string, unknown>[];
}
