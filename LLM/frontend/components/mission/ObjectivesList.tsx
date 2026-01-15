"use client";

import { MissionObjective } from "@/store/useStore";
import { useMissionStore } from "@/store/useStore";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { 
  Circle, 
  CircleDot, 
  CheckCircle2, 
  XCircle, 
  Ban,
  PauseCircle,
  Shield,
  ChevronRight
} from "lucide-react";
import { cn } from "@/lib/utils";

interface ObjectivesListProps {
  objectives: MissionObjective[];
}

/**
 * ObjectivesList - Lista de objetivos de una misión con estados visuales
 */
export function ObjectivesList({ objectives }: ObjectivesListProps) {
  const { openApprovalDialog, pendingApprovals } = useMissionStore();

  if (objectives.length === 0) {
    return (
      <div className="p-4 text-center text-muted-foreground text-sm">
        No hay objetivos definidos
      </div>
    );
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'COMPLETED':
        return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      case 'FAILED':
        return <XCircle className="h-4 w-4 text-red-500" />;
      case 'SKIPPED':
        return <Ban className="h-4 w-4 text-yellow-500" />;
      case 'IN_PROGRESS':
        return <CircleDot className="h-4 w-4 text-blue-500 animate-pulse" />;
      case 'AWAITING_AUTHORIZATION':
        return <PauseCircle className="h-4 w-4 text-orange-500" />;
      default:
        return <Circle className="h-4 w-4 text-muted-foreground" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'COMPLETED':
        return 'border-l-green-500';
      case 'FAILED':
        return 'border-l-red-500';
      case 'SKIPPED':
        return 'border-l-yellow-500';
      case 'IN_PROGRESS':
        return 'border-l-blue-500';
      case 'AWAITING_AUTHORIZATION':
        return 'border-l-orange-500';
      default:
        return 'border-l-muted';
    }
  };

  return (
    <TooltipProvider>
      <div className="divide-y divide-border">
        {objectives.map((obj, index) => {
          const pendingApproval = pendingApprovals.find((a) => a.id === obj.id);
          const isAwaitingAuth = obj.status === 'AWAITING_AUTHORIZATION';

          return (
            <div
              key={obj.id}
              className={cn(
                "p-3 border-l-2 transition-colors",
                getStatusColor(obj.status),
                isAwaitingAuth && "bg-orange-500/5"
              )}
            >
              <div className="flex items-start gap-2">
                {/* Número e icono de estado */}
                <div className="flex items-center gap-1.5 flex-shrink-0 mt-0.5">
                  <span className="text-xs text-muted-foreground font-mono w-4">
                    {index + 1}.
                  </span>
                  <Tooltip>
                    <TooltipTrigger>
                      {getStatusIcon(obj.status)}
                    </TooltipTrigger>
                    <TooltipContent>
                      <p>{obj.status.replace('_', ' ')}</p>
                    </TooltipContent>
                  </Tooltip>
                </div>

                {/* Contenido */}
                <div className="flex-1 min-w-0">
                  <p className={cn(
                    "text-sm",
                    obj.status === 'COMPLETED' && "text-muted-foreground line-through",
                    obj.status === 'SKIPPED' && "text-muted-foreground"
                  )}>
                    {obj.task}
                  </p>

                  {/* Resultado si existe */}
                  {obj.result_summary && (
                    <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                      {obj.result_summary}
                    </p>
                  )}

                  {/* Reflexión si existe */}
                  {obj.reflection && (
                    <p className="text-xs text-blue-500/80 mt-1 italic">
                      💭 {obj.reflection}
                    </p>
                  )}

                  {/* Comando pendiente de aprobación */}
                  {isAwaitingAuth && obj.pending_command && (
                    <div className="mt-2 p-2 rounded bg-orange-500/10 border border-orange-500/20">
                      <div className="flex items-center gap-2 text-orange-600 text-xs mb-1">
                        <Shield className="h-3 w-3" />
                        <span className="font-medium">Comando pendiente de aprobación</span>
                      </div>
                      <code className="text-xs bg-background/50 p-1 rounded block truncate">
                        {obj.pending_command}
                      </code>
                      {pendingApproval && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="mt-2 h-7 text-xs border-orange-500/50 hover:bg-orange-500/10"
                          onClick={() => openApprovalDialog(pendingApproval)}
                        >
                          <ChevronRight className="h-3 w-3 mr-1" />
                          Revisar y aprobar
                        </Button>
                      )}
                    </div>
                  )}

                  {/* Badge de aprobación */}
                  {obj.approval_status && obj.approval_status !== 'AWAITING_AUTHORIZATION' && (
                    <Badge
                      variant="outline"
                      className={cn(
                        "mt-1 text-xs",
                        obj.approval_status === 'APPROVED' && "bg-green-500/10 text-green-600",
                        obj.approval_status === 'REJECTED' && "bg-red-500/10 text-red-600"
                      )}
                    >
                      {obj.approval_status === 'APPROVED' ? '✓ Aprobado' : '✗ Rechazado'}
                      {obj.approved_by && ` por ${obj.approved_by}`}
                    </Badge>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </TooltipProvider>
  );
}
