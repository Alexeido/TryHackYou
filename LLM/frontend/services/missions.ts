/**
 * Missions API Service - Comunicación con el backend para el modo agéntico
 * 
 * Gestiona:
 * - Misiones y objetivos
 * - Sistema de aprobación de comandos peligrosos
 * - Auditoría de comandos
 */

import { useConfigStore } from '@/store/useStore';

const getBaseUrl = () => useConfigStore.getState().backendUrl;

// ============================================
// TIPOS
// ============================================

export type ObjectiveStatus = 
  | 'PENDING' 
  | 'IN_PROGRESS' 
  | 'COMPLETED' 
  | 'FAILED' 
  | 'SKIPPED'
  | 'AWAITING_AUTHORIZATION';

export type MissionStatus = 
  | 'PLANNING' 
  | 'IN_PROGRESS' 
  | 'COMPLETED' 
  | 'FAILED' 
  | 'CANCELLED';

export type RiskLevel = 'safe' | 'low' | 'medium' | 'high' | 'critical';

export interface Objective {
  id: number;
  mission_id: string;
  order_index: number;
  task: string;
  status: ObjectiveStatus;
  result_summary: string | null;
  reflection: string | null;
  requires_approval: boolean;
  approval_status: string | null;
  pending_command: string | null;
  approved_by: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface Mission {
  id: string;
  conversation_id: string;
  goal: string;
  current_phase: string | null;
  status: MissionStatus;
  created_at: string;
  completed_at: string | null;
  metadata: Record<string, unknown> | null;
}

export interface MissionProgress {
  total: number;
  completed: number;
  failed: number;
  skipped: number;
  in_progress: number;
  pending: number;
  awaiting_authorization: number;
  percentage: number;
}

export interface MissionWithObjectives extends Mission {
  objectives: Objective[];
  progress: MissionProgress;
}

export interface PendingApproval {
  id: number;
  mission_id: string;
  mission_goal: string;
  conversation_id: string;
  task: string;
  pending_command: string;
  approval_status: string;
  order_index: number;
}

export interface CommandAnalysis {
  command: string;
  risk_level: RiskLevel;
  requires_approval: boolean;
  matched_patterns: Array<{
    pattern: string;
    description: string;
    risk_level: RiskLevel;
  }>;
  reason: string;
  approval_message?: string;
}

export interface AuditLog {
  id: number;
  conversation_id: string;
  mission_id: string | null;
  objective_id: number | null;
  command: string;
  risk_level: RiskLevel;
  requires_approval: boolean;
  reason: string;
  status: string;
  result_summary: string | null;
  approved_by: string | null;
  created_at: string;
  executed_at: string | null;
}

export interface AuditStatistics {
  total: number;
  by_status: Record<string, number>;
  by_risk: Record<string, number>;
  required_approval: number;
  approval_rate: number;
}

// ============================================
// API HELPERS
// ============================================

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorMessage = `Error ${response.status}`;
    try {
      const errorData = await response.json();
      errorMessage = errorData.detail || errorMessage;
    } catch {
      // Ignore JSON parse errors
    }
    throw new Error(errorMessage);
  }
  return response.json();
}

// ============================================
// MISSIONS API
// ============================================

/**
 * Obtiene la misión activa de una conversación
 */
export async function getActiveMission(conversationId: string): Promise<MissionWithObjectives | null> {
  const response = await fetch(
    `${getBaseUrl()}/missions/conversation/${conversationId}/active`
  );
  const data = await handleResponse<{
    active: boolean;
    mission: Mission | null;
    objectives: Objective[];
    progress: MissionProgress;
  }>(response);
  
  if (!data.active || !data.mission) {
    return null;
  }
  
  return {
    ...data.mission,
    objectives: data.objectives,
    progress: data.progress,
  };
}

/**
 * Obtiene una misión por ID
 */
export async function getMission(missionId: string): Promise<MissionWithObjectives> {
  const response = await fetch(`${getBaseUrl()}/missions/${missionId}`);
  return handleResponse<MissionWithObjectives>(response);
}

/**
 * Obtiene los objetivos de una misión
 */
export async function getObjectives(missionId: string): Promise<Objective[]> {
  const response = await fetch(`${getBaseUrl()}/missions/${missionId}/objectives`);
  const data = await handleResponse<{ mission_id: string; objectives: Objective[] }>(response);
  return data.objectives;
}

/**
 * Actualiza el estado de un objetivo
 */
export async function updateObjective(
  objectiveId: number, 
  update: { 
    status?: ObjectiveStatus; 
    result?: string;
    reflection?: string;
  }
): Promise<{ objective: Objective; progress: MissionProgress }> {
  const response = await fetch(`${getBaseUrl()}/missions/objectives/${objectiveId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(update),
  });
  return handleResponse(response);
}

/**
 * Cancela una misión
 */
export async function cancelMission(missionId: string): Promise<void> {
  const response = await fetch(`${getBaseUrl()}/missions/${missionId}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    throw new Error('Failed to cancel mission');
  }
}

// ============================================
// APPROVAL API
// ============================================

/**
 * Obtiene objetivos pendientes de aprobación
 */
export async function getPendingApprovals(conversationId?: string): Promise<PendingApproval[]> {
  let url = `${getBaseUrl()}/missions/objectives/pending-approval`;
  if (conversationId) {
    url += `?conversation_id=${conversationId}`;
  }
  const response = await fetch(url);
  const data = await handleResponse<{ count: number; pending_objectives: PendingApproval[] }>(response);
  return data.pending_objectives;
}

/**
 * Resultado de ejecución de un comando aprobado
 */
export interface CommandExecutionResult {
  success: boolean;
  output: string;
  exit_code?: number;
  job_id?: string;
  status?: string;
  error?: string;
}

/**
 * Respuesta del endpoint de aprobación
 */
export interface ApprovalResponse {
  success: boolean;
  objective_id: number;
  approved: boolean;
  command: string;
  mission_id: string;
  conversation_id?: string;
  message: string;
  execution?: CommandExecutionResult;  // Solo presente si se aprobó
}

/**
 * Aprueba o rechaza un comando pendiente.
 * Si se aprueba, el comando se ejecuta automáticamente y se devuelve el resultado.
 */
export async function approveCommand(
  objectiveId: number, 
  approved: boolean,
  approvedBy: string = 'user'
): Promise<ApprovalResponse> {
  const response = await fetch(`${getBaseUrl()}/missions/objectives/${objectiveId}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ approved, approved_by: approvedBy }),
  });
  return handleResponse(response);
}

/**
 * Analiza el riesgo de un comando sin ejecutarlo
 */
export async function analyzeCommand(command: string): Promise<CommandAnalysis> {
  const response = await fetch(`${getBaseUrl()}/missions/analyze-command?command=${encodeURIComponent(command)}`, {
    method: 'POST',
  });
  return handleResponse<CommandAnalysis>(response);
}

// ============================================
// AUDIT API
// ============================================

/**
 * Obtiene logs de auditoría
 */
export async function getAuditLogs(filters?: {
  conversationId?: string;
  missionId?: string;
  status?: string;
  limit?: number;
}): Promise<AuditLog[]> {
  const params = new URLSearchParams();
  if (filters?.conversationId) params.append('conversation_id', filters.conversationId);
  if (filters?.missionId) params.append('mission_id', filters.missionId);
  if (filters?.status) params.append('status', filters.status);
  if (filters?.limit) params.append('limit', String(filters.limit));
  
  const url = `${getBaseUrl()}/missions/audit/logs${params.toString() ? `?${params}` : ''}`;
  const response = await fetch(url);
  const data = await handleResponse<{ logs: AuditLog[] }>(response);
  return data.logs;
}

/**
 * Obtiene estadísticas de auditoría
 */
export async function getAuditStatistics(conversationId?: string): Promise<AuditStatistics> {
  let url = `${getBaseUrl()}/missions/audit/statistics`;
  if (conversationId) {
    url += `?conversation_id=${conversationId}`;
  }
  const response = await fetch(url);
  return handleResponse<AuditStatistics>(response);
}

/**
 * Genera un reporte de auditoría en Markdown
 */
export async function getAuditReport(conversationId?: string): Promise<string> {
  let url = `${getBaseUrl()}/missions/audit/report`;
  if (conversationId) {
    url += `?conversation_id=${conversationId}`;
  }
  const response = await fetch(url);
  const data = await handleResponse<{ report: string }>(response);
  return data.report;
}

// ============================================
// UTILITY FUNCTIONS
// ============================================

/**
 * Obtiene el color del badge según el estado del objetivo
 */
export function getObjectiveStatusColor(status: ObjectiveStatus): string {
  const colors: Record<ObjectiveStatus, string> = {
    PENDING: 'bg-gray-500',
    IN_PROGRESS: 'bg-blue-500',
    COMPLETED: 'bg-green-500',
    FAILED: 'bg-red-500',
    SKIPPED: 'bg-yellow-500',
    AWAITING_AUTHORIZATION: 'bg-orange-500',
  };
  return colors[status] || 'bg-gray-500';
}

/**
 * Obtiene el icono según el estado del objetivo
 */
export function getObjectiveStatusIcon(status: ObjectiveStatus): string {
  const icons: Record<ObjectiveStatus, string> = {
    PENDING: '○',
    IN_PROGRESS: '◐',
    COMPLETED: '✓',
    FAILED: '✗',
    SKIPPED: '⊘',
    AWAITING_AUTHORIZATION: '⏸',
  };
  return icons[status] || '○';
}

/**
 * Obtiene el color del badge según el nivel de riesgo
 */
export function getRiskLevelColor(level: RiskLevel): string {
  const colors: Record<RiskLevel, string> = {
    safe: 'bg-green-500',
    low: 'bg-green-400',
    medium: 'bg-yellow-500',
    high: 'bg-orange-500',
    critical: 'bg-red-500',
  };
  return colors[level] || 'bg-gray-500';
}

/**
 * Obtiene el emoji según el nivel de riesgo
 */
export function getRiskLevelEmoji(level: RiskLevel): string {
  const emojis: Record<RiskLevel, string> = {
    safe: '✅',
    low: '🟢',
    medium: '🟡',
    high: '🟠',
    critical: '🔴',
  };
  return emojis[level] || '⚪';
}
