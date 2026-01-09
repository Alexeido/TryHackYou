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

/**
 * Todas las herramientas disponibles
 * Agregar aquí nuevas tools cuando se implementen
 */
export const ALL_TOOLS: ToolDefinition[] = [
  EXECUTE_COMMAND_TOOL,
  CHECK_JOB_STATUS_TOOL,
];

/**
 * Obtiene las herramientas en el formato que espera la API del LLM
 */
export function getToolsForAPI(): Record<string, unknown>[] {
  return ALL_TOOLS as unknown as Record<string, unknown>[];
}
