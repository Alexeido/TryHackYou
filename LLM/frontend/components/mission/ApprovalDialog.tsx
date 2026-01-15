"use client";

import { useState } from "react";
import { useMissionStore, useChatStore, useConfigStore, useModelsStore } from "@/store/useStore";
import { approveCommand, analyzeCommand, type CommandAnalysis, type ApprovalResponse } from "@/services/missions";
import { sendMessageStream } from "@/services/api";
import { getToolsForAPI } from "@/services/tools";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { 
  Shield, 
  ShieldAlert, 
  ShieldCheck,
  ShieldX,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Loader2,
  Terminal,
  Info
} from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * ApprovalDialog - Diálogo modal para aprobar/rechazar comandos peligrosos
 * 
 * Muestra:
 * - El comando a ejecutar
 * - Análisis de riesgo
 * - Patrones detectados
 * - Botones de aprobar/rechazar
 */
export function ApprovalDialog() {
  const [isLoading, setIsLoading] = useState(false);
  const [analysis, setAnalysis] = useState<CommandAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);

  const {
    approvalDialogOpen,
    selectedApproval,
    closeApprovalDialog,
    removePendingApproval,
    setPendingApprovals,
    pendingApprovals,
  } = useMissionStore();

  const { 
    conversationId, 
    addMessage, 
    setLoading: setChatLoading,
    isLoading: chatIsLoading,
    appendChunk,
    clearChunk,
    setStreamingMessageId,
  } = useChatStore();
  
  const { apiKeys, systemPrompt } = useConfigStore();
  const { selectedModel } = useModelsStore();

  // Cargar análisis del comando cuando se abre el diálogo
  const loadAnalysis = async () => {
    if (!selectedApproval?.pending_command) return;

    try {
      const result = await analyzeCommand(selectedApproval.pending_command);
      setAnalysis(result);
    } catch (err) {
      console.error('[ApprovalDialog] Error analyzing command:', err);
    }
  };

  // Cargar análisis al abrir
  if (approvalDialogOpen && selectedApproval && !analysis && !isLoading) {
    loadAnalysis();
  }

  // Función auxiliar para obtener API key
  const getApiKey = () => {
    if (!selectedModel) return null;
    return apiKeys[selectedModel.provider] || null;
  };

  // Función para enviar mensaje de continuación al LLM
  const sendContinuationMessage = async (approvalResult: ApprovalResponse) => {
    if (!conversationId || chatIsLoading || !selectedModel) {
      console.log('[ApprovalDialog] Skip continuation - no conversation, loading, or no model');
      return;
    }

    const apiKey = getApiKey();
    if (!apiKey) {
      console.log('[ApprovalDialog] Skip continuation - no API key');
      return;
    }

    // Construir mensaje de continuación
    let message: string;
    if (approvalResult.approved && approvalResult.execution) {
      const exec = approvalResult.execution;
      message = `[SISTEMA] El comando fue APROBADO y ejecutado.

**Resultado de la ejecución:**
\`\`\`
${exec.output || 'Comando ejecutado exitosamente'}
\`\`\`
${exec.exit_code !== undefined ? `EXIT_CODE: ${exec.exit_code}` : ''}

**Instrucciones:**
- Analiza el resultado del comando
- Actualiza el estado del objetivo según corresponda
- CONTINÚA con el siguiente paso del plan de ataque
- NO esperes confirmación del usuario, actúa de forma AUTÓNOMA`;
    } else if (!approvalResult.approved) {
      message = `[SISTEMA] El comando fue RECHAZADO por el usuario.

**Instrucciones:**
- El objetivo actual debe ser marcado como SKIPPED
- Busca una alternativa o continúa con el siguiente objetivo
- CONTINÚA con el plan de ataque de forma AUTÓNOMA
- NO esperes confirmación del usuario`;
    } else {
      message = `[SISTEMA] El comando fue aprobado. Continúa con la ejecución de forma AUTÓNOMA.`;
    }

    console.log('[ApprovalDialog] Sending continuation message:', message.substring(0, 100));

    // Preparar parámetros
    const tools = getToolsForAPI();

    // Crear mensaje placeholder del usuario (como número temporal negativo)
    const userMsgId = -Date.now();
    addMessage({
      id: userMsgId,
      conversation_id: conversationId,
      parent_id: null,
      role: 'user',
      content: message,
      created_at: new Date().toISOString(),
    });

    // Crear mensaje placeholder del asistente
    const assistantMsgId = -(Date.now() + 1);
    addMessage({
      id: assistantMsgId,
      conversation_id: conversationId,
      parent_id: userMsgId,
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString(),
    });
    setStreamingMessageId(assistantMsgId);
    setChatLoading(true);

    try {
      sendMessageStream(
        {
          conversation_id: conversationId,
          user_message: message,
          provider: selectedModel.provider,
          model_id: selectedModel.id,
          api_key: apiKey,
          system_prompt: systemPrompt,
          tools: tools,
        },
        {
          onMessage: (chunk: string) => {
            appendChunk(chunk);
          },
          onToolCall: (toolCall) => {
            console.log('[ApprovalDialog] Tool call:', toolCall);
          },
          onToolResult: (result) => {
            console.log('[ApprovalDialog] Tool result received:', result.tool_call_id);
          },
          onDone: (data) => {
            console.log('[ApprovalDialog] Stream done:', data.assistant_message_id);
            setChatLoading(false);
            clearChunk();
            setStreamingMessageId(null);
          },
          onError: (error: string) => {
            console.error('[ApprovalDialog] Stream error:', error);
            setChatLoading(false);
            clearChunk();
            setStreamingMessageId(null);
          },
        }
      );
    } catch (err) {
      console.error('[ApprovalDialog] Error sending continuation:', err);
      setChatLoading(false);
      clearChunk();
      setStreamingMessageId(null);
    }
  };

  const handleApprove = async () => {
    if (!selectedApproval) return;

    setIsLoading(true);
    setError(null);

    try {
      const result = await approveCommand(selectedApproval.id, true, 'user');
      console.log('[ApprovalDialog] Approval result:', result);
      
      removePendingApproval(selectedApproval.id);
      closeApprovalDialog();
      setAnalysis(null);
      
      // Enviar mensaje de continuación para reanudar el loop autónomo
      // Pequeño delay para que el diálogo se cierre primero
      setTimeout(() => {
        sendContinuationMessage(result);
      }, 100);
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error approving command');
    } finally {
      setIsLoading(false);
    }
  };

  const handleReject = async () => {
    if (!selectedApproval) return;

    setIsLoading(true);
    setError(null);

    try {
      const result = await approveCommand(selectedApproval.id, false, 'user');
      console.log('[ApprovalDialog] Rejection result:', result);
      
      removePendingApproval(selectedApproval.id);
      closeApprovalDialog();
      setAnalysis(null);
      
      // También enviar mensaje de continuación para el rechazo
      setTimeout(() => {
        sendContinuationMessage(result);
      }, 100);
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error rejecting command');
    } finally {
      setIsLoading(false);
    }
  };

  const handleOpenChange = (open: boolean) => {
    if (!open) {
      closeApprovalDialog();
      setAnalysis(null);
      setError(null);
    }
  };

  const getRiskIcon = (level: string) => {
    switch (level) {
      case 'critical':
        return <ShieldAlert className="h-5 w-5 text-red-500" />;
      case 'high':
        return <ShieldX className="h-5 w-5 text-orange-500" />;
      case 'medium':
        return <Shield className="h-5 w-5 text-yellow-500" />;
      default:
        return <ShieldCheck className="h-5 w-5 text-green-500" />;
    }
  };

  const getRiskColor = (level: string) => {
    switch (level) {
      case 'critical':
        return 'bg-red-500';
      case 'high':
        return 'bg-orange-500';
      case 'medium':
        return 'bg-yellow-500';
      case 'low':
        return 'bg-green-400';
      default:
        return 'bg-green-500';
    }
  };

  return (
    <Dialog open={approvalDialogOpen} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5 text-orange-500" />
            Aprobación de Comando Requerida
          </DialogTitle>
          <DialogDescription>
            El agente quiere ejecutar un comando que requiere tu autorización.
          </DialogDescription>
        </DialogHeader>

        {selectedApproval && (
          <div className="space-y-4">
            {/* Información del objetivo */}
            <div className="rounded-lg border bg-muted/30 p-3">
              <p className="text-sm font-medium mb-1">Objetivo:</p>
              <p className="text-sm text-muted-foreground">{selectedApproval.task}</p>
              <p className="text-xs text-muted-foreground mt-2">
                Misión: {selectedApproval.mission_goal}
              </p>
            </div>

            {/* Comando a ejecutar */}
            <div className="rounded-lg border bg-background p-3">
              <div className="flex items-center gap-2 text-sm font-medium mb-2">
                <Terminal className="h-4 w-4" />
                Comando a ejecutar:
              </div>
              <pre className="text-sm bg-muted p-3 rounded overflow-x-auto whitespace-pre-wrap break-all">
                {selectedApproval.pending_command}
              </pre>
            </div>

            {/* Análisis de riesgo */}
            {analysis && (
              <>
                <Separator />
                
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Análisis de Riesgo:</span>
                    <div className="flex items-center gap-2">
                      {getRiskIcon(analysis.risk_level)}
                      <Badge className={cn("uppercase", getRiskColor(analysis.risk_level))}>
                        {analysis.risk_level}
                      </Badge>
                    </div>
                  </div>

                  <p className="text-sm text-muted-foreground">
                    {analysis.reason}
                  </p>

                  {/* Patrones detectados */}
                  {analysis.matched_patterns.length > 0 && (
                    <div className="space-y-2">
                      <p className="text-sm font-medium flex items-center gap-2">
                        <AlertTriangle className="h-4 w-4 text-orange-500" />
                        Patrones de riesgo detectados:
                      </p>
                      <ul className="space-y-1">
                        {analysis.matched_patterns.map((pattern, idx) => (
                          <li 
                            key={idx} 
                            className="text-sm text-muted-foreground flex items-start gap-2 ml-6"
                          >
                            <span className="text-orange-500">•</span>
                            <span>
                              <span className="font-medium">{pattern.description}</span>
                              <Badge 
                                variant="outline" 
                                className={cn("ml-2 text-xs", getRiskColor(pattern.risk_level))}
                              >
                                {pattern.risk_level}
                              </Badge>
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </>
            )}

            {/* Advertencia */}
            <div className="rounded-lg bg-orange-500/10 border border-orange-500/30 p-3">
              <div className="flex items-start gap-2">
                <Info className="h-4 w-4 text-orange-600 mt-0.5 flex-shrink-0" />
                <div className="text-sm text-orange-700 dark:text-orange-400">
                  <p className="font-medium mb-1">Importante:</p>
                  <ul className="list-disc ml-4 space-y-1 text-xs">
                    <li>Este comando se ejecutará en el sandbox aislado</li>
                    <li>Si rechazas, el agente buscará una alternativa o saltará el objetivo</li>
                    <li>Todas las ejecuciones quedan registradas en el log de auditoría</li>
                  </ul>
                </div>
              </div>
            </div>

            {/* Error */}
            {error && (
              <div className="rounded-lg bg-red-500/10 border border-red-500/30 p-3">
                <p className="text-sm text-red-600 flex items-center gap-2">
                  <XCircle className="h-4 w-4" />
                  {error}
                </p>
              </div>
            )}
          </div>
        )}

        <DialogFooter className="gap-2 sm:gap-0">
          <Button
            variant="outline"
            onClick={handleReject}
            disabled={isLoading}
            className="border-red-500/50 hover:bg-red-500/10 text-red-600"
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <XCircle className="h-4 w-4 mr-2" />
            )}
            Rechazar
          </Button>
          <Button
            onClick={handleApprove}
            disabled={isLoading}
            className="bg-green-600 hover:bg-green-700"
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <CheckCircle2 className="h-4 w-4 mr-2" />
            )}
            Aprobar y Ejecutar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
