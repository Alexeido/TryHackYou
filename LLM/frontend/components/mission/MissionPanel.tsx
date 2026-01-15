"use client";

import { useEffect, useCallback } from "react";
import { 
  useMissionStore, 
  useChatStore,
  MissionObjective,
  MissionProgress 
} from "@/store/useStore";
import { 
  getActiveMission, 
  getPendingApprovals,
  getObjectives
} from "@/services/missions";
import { ObjectivesList } from "./ObjectivesList";
import { ApprovalBanner } from "./ApprovalBanner";
import { 
  Target, 
  ChevronDown, 
  ChevronUp, 
  Loader2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  RefreshCw
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

/**
 * MissionPanel - Panel lateral/colapsable que muestra el estado de la misión activa
 * 
 * Características:
 * - Muestra el objetivo de la misión
 * - Lista de objetivos con estado
 * - Progreso visual
 * - Banner de aprobaciones pendientes
 */
export function MissionPanel() {
  const { conversationId } = useChatStore();
  const {
    activeMissions,
    objectives,
    progress,
    pendingApprovals,
    isPanelOpen,
    isLoading,
    error,
    setActiveMission,
    setObjectives,
    setProgress,
    setPendingApprovals,
    setPanelOpen,
    setLoading,
    setError,
  } = useMissionStore();

  const mission = conversationId ? activeMissions[conversationId] : null;
  const missionObjectives = mission ? objectives[mission.id] || [] : [];
  const missionProgress = mission ? progress[mission.id] : null;
  const conversationApprovals = pendingApprovals.filter(
    (a) => a.conversation_id === conversationId
  );

  // Cargar misión activa cuando cambia la conversación
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
        
        // Si hay misión activa, abrir el panel automáticamente
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
      console.error('[MissionPanel] Error loading mission:', err);
      setError(err instanceof Error ? err.message : 'Error loading mission');
    } finally {
      setLoading(false);
    }
  }, [conversationId, setActiveMission, setObjectives, setProgress, setPendingApprovals, setPanelOpen, setLoading, setError]);

  useEffect(() => {
    loadMission();
  }, [loadMission]);

  // Polling para actualizar el estado (cada 5 segundos si hay misión activa)
  useEffect(() => {
    if (!mission || mission.status === 'COMPLETED' || mission.status === 'FAILED' || mission.status === 'CANCELLED') {
      return;
    }

    const interval = setInterval(loadMission, 5000);
    return () => clearInterval(interval);
  }, [mission, loadMission]);

  // Si no hay misión activa y no hay aprobaciones pendientes, no mostrar nada
  if (!mission && conversationApprovals.length === 0) {
    return null;
  }

  const getStatusIcon = () => {
    if (!mission) return null;
    switch (mission.status) {
      case 'COMPLETED':
        return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      case 'FAILED':
        return <XCircle className="h-4 w-4 text-red-500" />;
      case 'CANCELLED':
        return <XCircle className="h-4 w-4 text-gray-500" />;
      case 'IN_PROGRESS':
        return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />;
      default:
        return <Target className="h-4 w-4 text-orange-500" />;
    }
  };

  const getStatusBadge = () => {
    if (!mission) return null;
    const variants: Record<string, string> = {
      PLANNING: 'bg-yellow-500',
      IN_PROGRESS: 'bg-blue-500',
      COMPLETED: 'bg-green-500',
      FAILED: 'bg-red-500',
      CANCELLED: 'bg-gray-500',
    };
    return (
      <Badge className={cn("text-xs", variants[mission.status] || 'bg-gray-500')}>
        {mission.status}
      </Badge>
    );
  };

  return (
    <div className="border-l border-border bg-background/50 backdrop-blur-sm">
      {/* Banner de aprobaciones pendientes (siempre visible si hay) */}
      {conversationApprovals.length > 0 && (
        <ApprovalBanner approvals={conversationApprovals} />
      )}

      {/* Cabecera del panel de misión */}
      {mission && (
        <>
          <button
            onClick={() => setPanelOpen(!isPanelOpen)}
            className="w-full p-3 flex items-center justify-between hover:bg-accent/50 transition-colors"
          >
            <div className="flex items-center gap-2 min-w-0">
              {getStatusIcon()}
              <span className="font-medium text-sm truncate">
                {mission.goal.length > 40 
                  ? `${mission.goal.slice(0, 40)}...` 
                  : mission.goal}
              </span>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              {getStatusBadge()}
              {isPanelOpen ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </div>
          </button>

          {/* Contenido colapsable */}
          {isPanelOpen && (
            <div className="border-t border-border">
              {/* Barra de progreso */}
              {missionProgress && (
                <div className="p-3 border-b border-border">
                  <div className="flex items-center justify-between text-xs text-muted-foreground mb-2">
                    <span>Progreso</span>
                    <span>
                      {missionProgress.completed}/{missionProgress.total} objetivos
                    </span>
                  </div>
                  <Progress 
                    value={missionProgress.percentage} 
                    className="h-2"
                  />
                  <div className="flex gap-2 mt-2 flex-wrap">
                    {missionProgress.completed > 0 && (
                      <Badge variant="outline" className="text-xs bg-green-500/10 text-green-600">
                        ✓ {missionProgress.completed}
                      </Badge>
                    )}
                    {missionProgress.in_progress > 0 && (
                      <Badge variant="outline" className="text-xs bg-blue-500/10 text-blue-600">
                        ◐ {missionProgress.in_progress}
                      </Badge>
                    )}
                    {missionProgress.awaiting_authorization > 0 && (
                      <Badge variant="outline" className="text-xs bg-orange-500/10 text-orange-600">
                        ⏸ {missionProgress.awaiting_authorization}
                      </Badge>
                    )}
                    {missionProgress.failed > 0 && (
                      <Badge variant="outline" className="text-xs bg-red-500/10 text-red-600">
                        ✗ {missionProgress.failed}
                      </Badge>
                    )}
                    {missionProgress.skipped > 0 && (
                      <Badge variant="outline" className="text-xs bg-yellow-500/10 text-yellow-600">
                        ⊘ {missionProgress.skipped}
                      </Badge>
                    )}
                  </div>
                </div>
              )}

              {/* Fase actual */}
              {mission.current_phase && (
                <div className="px-3 py-2 border-b border-border bg-accent/30">
                  <span className="text-xs text-muted-foreground">Fase actual:</span>
                  <span className="text-sm font-medium ml-2">{mission.current_phase}</span>
                </div>
              )}

              {/* Lista de objetivos */}
              <div className="max-h-[400px] overflow-y-auto">
                {isLoading && missionObjectives.length === 0 ? (
                  <div className="flex items-center justify-center p-4">
                    <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                  </div>
                ) : (
                  <ObjectivesList objectives={missionObjectives} />
                )}
              </div>

              {/* Footer con acciones */}
              <div className="p-2 border-t border-border flex justify-end gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={loadMission}
                  disabled={isLoading}
                >
                  <RefreshCw className={cn("h-4 w-4 mr-1", isLoading && "animate-spin")} />
                  Actualizar
                </Button>
              </div>

              {/* Error */}
              {error && (
                <div className="p-3 bg-red-500/10 border-t border-red-500/20">
                  <div className="flex items-center gap-2 text-red-600 text-sm">
                    <AlertTriangle className="h-4 w-4" />
                    {error}
                  </div>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
