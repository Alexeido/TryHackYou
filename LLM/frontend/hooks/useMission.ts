/**
 * useMission - Hook para gestionar el estado de la misión activa
 * 
 * Proporciona:
 * - Estado de la misión activa
 * - Funciones para cargar/actualizar misión
 * - Gestión de aprobaciones pendientes
 */

import { useCallback, useEffect } from 'react';
import { useChatStore, useMissionStore } from '@/store/useStore';
import {
  getActiveMission,
  getPendingApprovals,
  approveCommand,
  cancelMission,
  updateObjective,
  type ObjectiveStatus,
} from '@/services/missions';

export function useMission() {
  const { conversationId } = useChatStore();
  const {
    activeMissions,
    objectives,
    progress,
    pendingApprovals,
    isLoading,
    error,
    isPanelOpen,
    setActiveMission,
    setObjectives,
    setProgress,
    setPendingApprovals,
    removePendingApproval,
    setLoading,
    setError,
    setPanelOpen,
    clearMission,
  } = useMissionStore();

  // Misión activa de la conversación actual
  const mission = conversationId ? activeMissions[conversationId] : null;
  const missionObjectives = mission ? objectives[mission.id] || [] : [];
  const missionProgress = mission ? progress[mission.id] : null;
  const conversationApprovals = pendingApprovals.filter(
    (a) => a.conversation_id === conversationId
  );

  // Cargar misión activa
  const loadMission = useCallback(async () => {
    if (!conversationId) return;

    setLoading(true);
    setError(null);

    try {
      const missionData = await getActiveMission(conversationId);
      
      if (missionData) {
        setActiveMission(conversationId, missionData);
        setObjectives(missionData.id, missionData.objectives);
        setProgress(missionData.id, missionData.progress);
        
        // Abrir panel automáticamente si hay misión activa
        if (missionData.status === 'IN_PROGRESS' || missionData.status === 'PLANNING') {
          setPanelOpen(true);
        }
      } else {
        setActiveMission(conversationId, null);
      }

      // Cargar aprobaciones pendientes
      const approvals = await getPendingApprovals(conversationId);
      setPendingApprovals(approvals);
    } catch (err) {
      console.error('[useMission] Error loading mission:', err);
      setError(err instanceof Error ? err.message : 'Error loading mission');
    } finally {
      setLoading(false);
    }
  }, [conversationId, setActiveMission, setObjectives, setProgress, setPendingApprovals, setPanelOpen, setLoading, setError]);

  // Aprobar un comando
  const approve = useCallback(async (objectiveId: number, approved: boolean) => {
    try {
      await approveCommand(objectiveId, approved, 'user');
      removePendingApproval(objectiveId);
      
      // Recargar misión para actualizar estado
      await loadMission();
      
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error approving command');
      return false;
    }
  }, [removePendingApproval, loadMission, setError]);

  // Cancelar misión
  const cancel = useCallback(async () => {
    if (!mission) return false;

    try {
      await cancelMission(mission.id);
      clearMission(conversationId!);
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error cancelling mission');
      return false;
    }
  }, [mission, conversationId, clearMission, setError]);

  // Actualizar estado de un objetivo
  const updateObjectiveStatus = useCallback(async (
    objectiveId: number,
    status: ObjectiveStatus,
    result?: string
  ) => {
    if (!mission) return false;

    try {
      const response = await updateObjective(objectiveId, { status, result });
      
      // Actualizar estado local
      setObjectives(mission.id, 
        missionObjectives.map((obj) =>
          obj.id === objectiveId 
            ? { ...obj, status, result_summary: result ?? obj.result_summary }
            : obj
        )
      );
      setProgress(mission.id, response.progress);
      
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error updating objective');
      return false;
    }
  }, [mission, missionObjectives, setObjectives, setProgress, setError]);

  // Cargar al cambiar de conversación
  useEffect(() => {
    if (conversationId) {
      loadMission();
    }
  }, [conversationId, loadMission]);

  return {
    // Estado
    mission,
    objectives: missionObjectives,
    progress: missionProgress,
    pendingApprovals: conversationApprovals,
    isLoading,
    error,
    isPanelOpen,
    
    // Computed
    hasMission: !!mission,
    hasApprovals: conversationApprovals.length > 0,
    isActive: mission?.status === 'IN_PROGRESS',
    
    // Acciones
    loadMission,
    approve,
    cancel,
    updateObjectiveStatus,
    setPanelOpen,
  };
}
