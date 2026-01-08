/**
 * Terminal Service - Comunicación con el sandbox de Kali (Flask en puerto 5000)
 * Gestión de sesiones de terminal con git snapshots por conversación
 */

// ============================================
// CONFIGURACIÓN
// ============================================

const TERMINAL_API_URL = 'http://localhost:5000';

interface ApiError {
  error: string;
}

async function handleTerminalResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorMessage = `Error ${response.status}`;
    try {
      const errorData: ApiError = await response.json();
      errorMessage = errorData.error || errorMessage;
    } catch {
      // Si no es JSON, usar mensaje genérico
    }
    throw new Error(errorMessage);
  }
  return response.json();
}

// ============================================
// TIPOS
// ============================================

export interface TerminalHealthResponse {
  status: string;
  active_jobs: number;
  sandbox_name: string;
}

export interface SessionInitResponse {
  status: string;
  conversation_id: string;
  repo_path: string;
  message: string;
}

export interface CheckpointResponse {
  status: string;
  conversation_id: string;
  leaf_id: number;
  parent_leaf_id: number | null;
  commit: string;
  tag: string;
}

export interface SwitchBranchResponse {
  status: string;
  conversation_id: string;
  switched_to_leaf: number;
  restored_from_commit: string;
}

export interface SessionInfo {
  conversation_id: string;
  commit: string;
  cwd: string;
  files: string[];
  tags: string[];
  jobs: JobInfo[];
}

export interface JobInfo {
  id: string;
  command: string;
  cwd?: string;
  status?: string;
  started_at?: string;
  conversation_id?: string;
  leaf_id?: number | null;
  elapsed?: number | string;
  job_id?: string;
  job_id_short?: string;
}

export interface ConversationSummary {
  conversation_id: string;
  repo_path: string;
  total_leaves: number;
  running_jobs: number;
  last_activity: string;
}

// Respuesta real del sandbox (running y total)
export interface RunningJobsResponse {
  total: number;
  running: Record<string, Array<{
    command: string;
    elapsed: number;
    job_id: string;
    job_id_short: string;
    leaf_id: number | null;
  }>>;
}

export interface ExecuteRequest {
  command: string;
  cwd?: string;
  timeout?: number;
  conversation_id?: string;
  leaf_id?: number;
}

export interface ExecuteResponse {
  job_id: string;
  conversation_id?: string;
  leaf_id?: number;
  message: string;
}

export interface JobStatusResponse {
  id: string;
  command: string;
  cwd: string;
  status: 'running' | 'completed' | 'timeout';
  output: string;
  exit_code: number | null;
  started_at: string;
  finished_at: string | null;
  duration: string | null;
}

// ============================================
// HEALTH & STATUS
// ============================================

export async function checkTerminalHealth(): Promise<TerminalHealthResponse> {
  const response = await fetch(`${TERMINAL_API_URL}/health`);
  return handleTerminalResponse<TerminalHealthResponse>(response);
}

// ============================================
// SESSION MANAGEMENT (Git Snapshots)
// ============================================

/**
 * Inicializa una sesión de terminal para una conversación
 * Crea un repositorio git aislado en /workspace_sessions/{conversation_id}
 */
export async function initTerminalSession(conversationId: string): Promise<SessionInitResponse> {
  const response = await fetch(`${TERMINAL_API_URL}/session/init`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ conversation_id: conversationId }),
  });
  return handleTerminalResponse<SessionInitResponse>(response);
}

/**
 * Crea un checkpoint (commit + tag) para una hoja del árbol de conversación
 * Llamar después de cada respuesta del LLM
 */
export async function createCheckpoint(
  conversationId: string, 
  leafId: number, 
  parentLeafId: number | null = null
): Promise<CheckpointResponse> {
  const response = await fetch(`${TERMINAL_API_URL}/session/checkpoint`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ 
      conversation_id: conversationId,
      leaf_id: leafId,
      parent_leaf_id: parentLeafId,
    }),
  });
  return handleTerminalResponse<CheckpointResponse>(response);
}

/**
 * Cambia a una rama diferente del árbol (restaura estado del filesystem)
 * Llamar cuando el usuario navega en el árbol de conversación
 */
export async function switchBranch(
  conversationId: string, 
  leafId: number
): Promise<SwitchBranchResponse> {
  const response = await fetch(`${TERMINAL_API_URL}/session/switch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ 
      conversation_id: conversationId,
      leaf_id: leafId,
    }),
  });
  return handleTerminalResponse<SwitchBranchResponse>(response);
}

/**
 * Obtiene información completa de una sesión
 */
export async function getSessionInfo(conversationId: string): Promise<SessionInfo> {
  const response = await fetch(`${TERMINAL_API_URL}/session/info/${conversationId}`);
  return handleTerminalResponse<SessionInfo>(response);
}

// ============================================
// COMMAND EXECUTION
// ============================================

/**
 * Ejecuta un comando en el sandbox asociado a una conversación
 */
export async function executeCommand(request: ExecuteRequest): Promise<ExecuteResponse> {
  const response = await fetch(`${TERMINAL_API_URL}/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  return handleTerminalResponse<ExecuteResponse>(response);
}

/**
 * Obtiene el estado de un job
 */
export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  const response = await fetch(`${TERMINAL_API_URL}/status/${jobId}`);
  return handleTerminalResponse<JobStatusResponse>(response);
}

/**
 * Obtiene el output de un job
 */
export async function getJobOutput(jobId: string): Promise<{ output: string; status: string }> {
  const response = await fetch(`${TERMINAL_API_URL}/output/${jobId}`);
  return handleTerminalResponse<{ output: string; status: string }>(response);
}

/**
 * Cancela un job en ejecución
 */
export async function cancelJob(jobId: string): Promise<{ status: string; message: string }> {
  const response = await fetch(`${TERMINAL_API_URL}/cancel/${jobId}`, {
    method: 'POST',
  });
  return handleTerminalResponse<{ status: string; message: string }>(response);
}

// ============================================
// ADMIN / MONITORING
// ============================================

/**
 * Lista todas las conversaciones con sesiones de terminal activas
 */
export async function getTerminalConversations(): Promise<ConversationSummary[]> {
  const response = await fetch(`${TERMINAL_API_URL}/admin/api/conversations`);
  const data = await handleTerminalResponse<{ conversations: ConversationSummary[] }>(response);
  return data.conversations;
}

/**
 * Obtiene todos los jobs en ejecución agrupados por conversación
 */
export async function getRunningJobs(): Promise<RunningJobsResponse> {
  const response = await fetch(`${TERMINAL_API_URL}/admin/api/running`);
  return handleTerminalResponse<RunningJobsResponse>(response);
}

/**
 * Obtiene jobs en ejecución para una conversación específica
 */
export async function getRunningJobsForConversation(conversationId: string): Promise<JobInfo[]> {
  const running = await getRunningJobs();
  const rawJobs = running.running?.[conversationId] || [];
  
  // Transformar al formato JobInfo
  return rawJobs.map(job => ({
    id: job.job_id,
    command: job.command,
    elapsed: typeof job.elapsed === 'number' ? `${job.elapsed.toFixed(1)}s` : String(job.elapsed),
    leaf_id: job.leaf_id,
    job_id: job.job_id,
    job_id_short: job.job_id_short,
  }));
}

// ============================================
// UTILITY FUNCTIONS
// ============================================

/**
 * Espera a que un job termine y retorna el resultado
 */
export async function waitForJob(
  jobId: string, 
  pollInterval = 1000, 
  maxWait = 300000
): Promise<JobStatusResponse> {
  const startTime = Date.now();
  
  while (Date.now() - startTime < maxWait) {
    const status = await getJobStatus(jobId);
    
    if (status.status !== 'running') {
      return status;
    }
    
    await new Promise(resolve => setTimeout(resolve, pollInterval));
  }
  
  throw new Error(`Job ${jobId} timeout after ${maxWait}ms`);
}

/**
 * Ejecuta un comando y espera el resultado
 */
export async function executeAndWait(
  request: ExecuteRequest,
  pollInterval = 1000,
  maxWait = 300000
): Promise<JobStatusResponse> {
  const { job_id } = await executeCommand(request);
  return waitForJob(job_id, pollInterval, maxWait);
}
