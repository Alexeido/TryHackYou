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
- Long-running commands (scans >30s) will timeout, check status with wait_time parameter
- Use absolute paths or verify current directory with 'pwd'
- Commands run as root in the Kali container`,
    parameters: {
      type: "object",
      properties: {
        command: {
          type: "string",
          description: "The shell command to execute (bash syntax)"
        },
        wait_time: {
          type: "number",
          description: "Seconds to wait before returning. Use 5-10 for commands with immediate output, 30-60 for scans. Default: 5",
          default: 5
        },
        exit_time: {
          type: "number",
          description: "Maximum execution time before forcefully stopping the command. Use for long scans to get partial results. Default: none (runs until completion)",
          default: null
        }
      },
      required: ["command"]
    }
  }
};

/**
 * Todas las herramientas disponibles
 * Agregar aquí nuevas tools cuando se implementen
 */
export const ALL_TOOLS: ToolDefinition[] = [
  EXECUTE_COMMAND_TOOL,
  // Futuras tools: read_file, write_file, search_exploits, etc.
];

/**
 * Obtiene las herramientas en el formato que espera la API del LLM
 */
export function getToolsForAPI(): Record<string, unknown>[] {
  return ALL_TOOLS as unknown as Record<string, unknown>[];
}
