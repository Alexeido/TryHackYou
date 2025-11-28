# API Documentation for LLM Agent

You have access to a Linux terminal via a REST API. Use this to execute commands, monitor their output, and manage long-running processes.

## Base URL
`http://localhost:5000`

## Endpoints

### 1. Execute Command
**POST** `/execute`

Starts a shell command in the background.

**Body (JSON):**
```json
{
  "command": "ping -c 10 google.com",
  "session_id": "my-session",
  "wait_time": 5,
  "exit_time": 30
}
```
- `command`: The shell command to run.
- `session_id` (optional): Session identifier to maintain persistent working directory. If not provided, uses `"default"`. Each session has its own current working directory (cwd).
- `wait_time` (optional): Seconds to wait before returning the first response. Recommended: `5` or `10` to see immediate output.
- `exit_time` (optional): Seconds after which, if the process is still running, the server will stop the process and return the final output. If both `exit_time` and `wait_time` are provided, `exit_time` takes precedence.

**Notes on precedence:**
- If both `wait_time` and `exit_time` are present, `exit_time` is applied (the process will be stopped after `exit_time` seconds and the response returned). 
- If only `wait_time` is present, the API waits but does not stop the command.
- If neither is provided, the API waits 0.1s to catch instant commands.

**Response:**
```json
{
  "job_id": "uuid-string",
  "status": "running",
  "cwd": "/app",
  "stdout": "PING google.com ...",
  "return_code": null
}
```
*Note: `stdout` and `stderr` fields are omitted if empty.*

**Working Directory:**
- The `cwd` field shows the current working directory for this session.
- `cd` commands automatically update the session's working directory.
- All subsequent commands in the same session execute from this directory.

### 2. Check Status / Get Output
**GET** `/status/<job_id>?wait=5`

Retrieves the full output (stdout/stderr) generated so far.

- `wait` (optional): Seconds to wait if the process is still running (long polling). Recommended: `5`.

**Response:**
```json
{
  "status": "finished",
  "return_code": 0,
  "cwd": "/app/examples",
  "stdout": "file1.txt\nfile2.txt\n"
}
```

**Output Compression:**
Repetitive lines are automatically compressed to save tokens.
*Raw:*
```text
64 bytes from 1.1.1.1: icmp_seq=1 time=10ms
64 bytes from 1.1.1.1: icmp_seq=2 time=11ms
```
*Compressed (what you see):*
```text
64 bytes from 1.1.1.1: icmp_seq={ 1 time=10ms, 2 time=11ms }
```

### 3. Stop Command
**POST** `/stop/<job_id>`

Sends `SIGINT` (Ctrl+C) to the process. Use this if a command is stuck or you have enough information.

### 4. Session History
**GET** `/history/<session_id>`

Returns the complete command history for a session.

**Response:**
```json
{
  "session_id": "my-session",
  "cwd_actual": "/app/examples",
  "total_comandos": 3,
  "historial": [
    {
      "comando": "whoami",
      "ubicacion": "/app",
      "fecha": "2025-11-28 14:25:30",
      "salida": "root\n",
      "return_code": 0
    },
    {
      "comando": "cd examples",
      "ubicacion": "/app",
      "fecha": "2025-11-28 14:25:35",
      "return_code": 0
    }
  ]
}
```

Fields in history entries:
- `comando`: Command that was executed
- `ubicacion`: Working directory where it was executed
- `fecha`: Timestamp in format `YYYY-MM-DD HH:MM:SS`
- `salida`: stdout output (only if present)
- `error`: stderr output (only if present)
- `return_code`: Exit code (only if command finished)

## Capabilities & Limitations

### 🛡️ Security & Environment
- **User:** You are **root**.
- **Environment:** You are running inside a dedicated **sandbox**.
- **Privileges:** You have full control over this isolated environment. You do NOT need `sudo`.

### ✅ What you CAN do:
- Run standard Linux commands (`nmap`, `curl`, `python3`, `ls`, etc.).
- Run long-running processes (background jobs).
- Poll for output updates using `/status`.
- Cancel processes using `/stop`.
- Analyze compressed logs efficiently.
- Use `cd` to navigate directories (persistent per session).
- Create files and directories anywhere in the sandbox.
- View command history for any session via `/history/<session_id>`.

### ❌ What you CANNOT do:
- **Interactive Input:** You cannot send text to `stdin`.
  - *Do NOT run:* `python3 script.py` if it uses `input()`.
  - *Do NOT run:* `apt install` without `-y` (it will hang asking for confirmation).
- **Sudo:** Do not use `sudo`. You are already root.
- **Editors:** Do not run `vim`, `nano`, or `top`. They require a TTY.

## Working with Sessions

Each `session_id` maintains:
- **Current working directory (cwd)**: Persistent across commands.
- **Command history**: All executed commands with timestamps and results.

**Best Practice:** Use a unique `session_id` for each task or conversation to keep contexts isolated.

## Workflow Examples

### Example 1: Simple Command
```bash
curl -X POST http://localhost:5000/execute \
  -H "Content-Type: application/json" \
  -d '{"command":"whoami"}'
```
*Response:* `{"status": "finished", "return_code": 0, "cwd": "/app", "stdout": "root\n"}`

### Example 2: Long-running with Wait Time
```bash
curl -X POST http://localhost:5000/execute \
  -H "Content-Type: application/json" \
  -d '{"command":"ping google.com","wait_time":5,"session_id":"scan-1"}'
```
*Response:* `{"job_id": "abc-123", "status": "running", "cwd": "/app", "stdout": "PING..."}`

Then monitor:
```bash
curl "http://localhost:5000/status/abc-123?wait=5"
```

### Example 3: Working with Directories
```bash
# Create and navigate
curl -X POST http://localhost:5000/execute \
  -H "Content-Type: application/json" \
  -d '{"command":"mkdir project","session_id":"dev-1"}'

curl -X POST http://localhost:5000/execute \
  -H "Content-Type: application/json" \
  -d '{"command":"cd project","session_id":"dev-1"}'

# Create file (now in /app/project)
curl -X POST http://localhost:5000/execute \
  -H "Content-Type: application/json" \
  -d '{"command":"touch main.py","session_id":"dev-1"}'
```

### Example 4: View Session History
```bash
curl http://localhost:5000/history/dev-1
```
*Shows all commands executed in session `dev-1` with timestamps and results.*
