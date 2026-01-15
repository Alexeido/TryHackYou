"use client";

import { PendingApproval, useMissionStore } from "@/store/useStore";
import { Button } from "@/components/ui/button";
import { Shield, AlertTriangle, ChevronRight } from "lucide-react";

interface ApprovalBannerProps {
  approvals: PendingApproval[];
}

/**
 * ApprovalBanner - Banner que muestra las aprobaciones pendientes
 * Siempre visible cuando hay comandos esperando autorización
 */
export function ApprovalBanner({ approvals }: ApprovalBannerProps) {
  const { openApprovalDialog } = useMissionStore();

  if (approvals.length === 0) return null;

  const firstApproval = approvals[0];

  return (
    <div className="bg-orange-500/10 border-b border-orange-500/30 p-3">
      <div className="flex items-start gap-3">
        <div className="p-2 rounded-full bg-orange-500/20 flex-shrink-0">
          <Shield className="h-4 w-4 text-orange-600" />
        </div>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 text-orange-700 dark:text-orange-400">
            <AlertTriangle className="h-4 w-4" />
            <span className="font-medium text-sm">
              {approvals.length === 1 
                ? 'Comando pendiente de aprobación' 
                : `${approvals.length} comandos pendientes de aprobación`}
            </span>
          </div>
          
          <p className="text-xs text-muted-foreground mt-1 line-clamp-1">
            {firstApproval.task}
          </p>
          
          {firstApproval.pending_command && (
            <code className="text-xs bg-background/50 px-1.5 py-0.5 rounded mt-1 block truncate text-orange-600">
              {firstApproval.pending_command}
            </code>
          )}
        </div>

        <Button
          size="sm"
          variant="outline"
          className="flex-shrink-0 border-orange-500/50 hover:bg-orange-500/10 text-orange-700"
          onClick={() => openApprovalDialog(firstApproval)}
        >
          <ChevronRight className="h-4 w-4 mr-1" />
          Revisar
        </Button>
      </div>

      {approvals.length > 1 && (
        <p className="text-xs text-muted-foreground mt-2 ml-11">
          +{approvals.length - 1} más esperando revisión
        </p>
      )}
    </div>
  );
}
