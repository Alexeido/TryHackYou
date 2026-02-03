"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useChatStore, useTerminalStore, Message } from "@/store/useStore";
import { 
  getRunningJobsForConversation, 
  getSessionInfo,
  cancelJob,
  type JobInfo,
  type SessionInfo 
} from "@/services/terminal";
import { 
  TerminalSquare, 
  X, 
  Trash2,
  ChevronDown,
  ChevronRight,
  Copy,
  Check,
  Loader2,
  Play,
  Square,
  GitBranch,
  Clock,
  Wifi,
  WifiOff
} from "lucide-react";
import { cn } from "@/lib/utils";

interface TerminalPanelProps {
  onClose: () => void;
}

interface LogEntry {
  id: string;
  type: 'tool_call' | 'tool_response' | 'info' | 'error';
  timestamp: Date;
  content: string;
  name?: string;
  expanded?: boolean;
  // Datos parseados para tool_calls
  command?: string;
  waitTime?: number;
  exitTime?: number;
}

export function TerminalPanel({ onClose }: TerminalPanelProps) {
  const { messages, conversationId, streamingToolCalls } = useChatStore();
  const { isConnected, sessions } = useTerminalStore();
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [runningJobs, setRunningJobs] = useState<JobInfo[]>([]);
  const [sessionInfo, setSessionInfo] = useState<SessionInfo | null>(null);
  const [activeTab, setActiveTab] = useState<string>("activity");
  const scrollRef = useRef<HTMLDivElement>(null);

  // Poll jobs cada 3 segundos - SIN dependencias que causen re-renders
  useEffect(() => {
    // Resetear jobs inmediatamente al cambiar de conversación
    setRunningJobs([]);
    setSessionInfo(null);
    
    if (!conversationId) return;
    
    // Función interna para evitar dependencias
    const fetchData = async () => {
      try {
        const jobs = await getRunningJobsForConversation(conversationId);
        setRunningJobs(jobs);
        
        // Solo cargar session info si hay jobs
        if (jobs.length > 0) {
          try {
            const info = await getSessionInfo(conversationId);
            setSessionInfo(info);
          } catch {
            // Ignorar errores de session info
          }
        }
      } catch (err) {
        console.log('[Terminal] Error cargando jobs:', err);
        setRunningJobs([]);
      }
    };
    
    // Cargar inmediatamente
    fetchData();
    
    // Poll cada 3 segundos
    const interval = setInterval(fetchData, 3000);
    
    return () => clearInterval(interval);
  }, [conversationId]); // SOLO conversationId como dependencia

  // Cancelar un job
  const handleCancelJob = async (jobId: string) => {
    try {
      await cancelJob(jobId);
      // Recargar después de cancelar
      const jobs = await getRunningJobsForConversation(conversationId || '');
      setRunningJobs(jobs);
    } catch (err) {
      console.error('[Terminal] Error cancelando job:', err);
    }
  };

  // Extraer tool calls de los mensajes - mantener orden call -> response
  useEffect(() => {
    const newLogs: LogEntry[] = [];
    const seenToolCallIds = new Set<string>();
    
    // Crear mapa de tool_call_id -> mensaje de respuesta
    const toolResponseMap = new Map<string, Message>();
    messages.forEach(msg => {
      if (msg.role === 'tool' && msg.tool_call_id) {
        toolResponseMap.set(msg.tool_call_id, msg);
      }
    });
    
    // Procesar mensajes en orden
    messages.forEach(msg => {
      // Tool calls del assistant
      if (msg.tool_calls) {
        let toolCallsArray = msg.tool_calls;
        if (typeof toolCallsArray === 'string') {
          try {
            toolCallsArray = JSON.parse(toolCallsArray);
          } catch {
            toolCallsArray = [];
          }
        }
        
        if (Array.isArray(toolCallsArray) && toolCallsArray.length > 0) {
          toolCallsArray.forEach((tc: { id?: string; function?: { name?: string; arguments?: string } }) => {
            if (tc.id && tc.function) {
              seenToolCallIds.add(tc.id);
              
              // Parsear argumentos para extraer comando y tiempos
              let command = '';
              let waitTime: number | undefined;
              let exitTime: number | undefined;
              const rawArgs = tc.function.arguments || '{}';
              
              try {
                const args = JSON.parse(rawArgs);
                command = args.command || '';
                waitTime = args.wait_time;
                exitTime = args.exit_time;
                
                // Fallback: si es manage_mission, mostrar action
                if (!command && args.action) {
                  command = `[manage_mission] ${args.action}`;
                }
                // Fallback: si es check_job_status, mostrar job_id
                if (!command && args.job_id) {
                  command = `[check_job_status] ${args.job_id}`;
                }
              } catch {
                // Si falla el parse, intentar extraer command con regex
                const cmdMatch = rawArgs.match(/"command"\s*:\s*"([^"]+)"/);
                if (cmdMatch) {
                  command = cmdMatch[1];
                }
              }
              
              // Agregar el tool call
              newLogs.push({
                id: tc.id,
                type: 'tool_call',
                timestamp: new Date(msg.created_at),
                name: tc.function.name || 'unknown',
                content: tc.function.arguments || '{}',
                command,
                waitTime,
                exitTime,
              });
              
              // Buscar y agregar su respuesta inmediatamente después
              const response = toolResponseMap.get(tc.id);
              if (response) {
                newLogs.push({
                  id: `tool-response-${response.id}`,
                  type: 'tool_response',
                  timestamp: new Date(response.created_at),
                  name: response.tool_call_id || 'tool',
                  content: response.content || '',
                });
              }
            }
          });
        }
      }
    });
    
    // Agregar streaming tool calls que aún no están en messages (al final)
    streamingToolCalls.forEach(tc => {
      if (!seenToolCallIds.has(tc.id)) {
        let command = '';
        let waitTime: number | undefined;
        let exitTime: number | undefined;
        const rawArgs = tc.function.arguments || '{}';
        
        try {
          const args = JSON.parse(rawArgs);
          command = args.command || '';
          waitTime = args.wait_time;
          exitTime = args.exit_time;
          
          // Fallback para otros tipos de tools
          if (!command && args.action) {
            command = `[manage_mission] ${args.action}`;
          }
          if (!command && args.job_id) {
            command = `[check_job_status] ${args.job_id}`;
          }
        } catch {
          // Los argumentos pueden estar incompletos durante streaming
          // Intentar regex como fallback
          const cmdMatch = rawArgs.match(/"command"\s*:\s*"([^"]+)"/);
          if (cmdMatch) {
            command = cmdMatch[1];
          }
        }
        
        newLogs.push({
          id: tc.id,
          type: 'tool_call',
          timestamp: new Date(),
          name: tc.function.name || 'unknown',
          content: tc.function.arguments || '{}',
          command,
          waitTime,
          exitTime,
        });
      }
    });
    
    setLogs(newLogs);
  }, [messages, streamingToolCalls]);

  // Auto-scroll
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  const toggleExpand = (id: string) => {
    setLogs(prev => prev.map(log => 
      log.id === id ? { ...log, expanded: !log.expanded } : log
    ));
  };

  const copyContent = async (id: string, content: string) => {
    await navigator.clipboard.writeText(content);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const clearLogs = () => {
    setLogs([]);
  };

  const formatJson = (str: string) => {
    try {
      return JSON.stringify(JSON.parse(str), null, 2);
    } catch {
      return str;
    }
  };

  const currentSession = conversationId ? sessions[conversationId] : null;

  return (
    <div className="h-full flex flex-col bg-zinc-950 text-zinc-100">
      {/* Header */}
      <div className="h-10 bg-zinc-900 border-b border-zinc-800 flex items-center px-3 justify-between shrink-0">
        <div className="flex items-center gap-2">
          <TerminalSquare className="h-4 w-4 text-green-500" />
          <span className="text-sm font-medium">Terminal</span>
          {isConnected ? (
            <Wifi className="h-3 w-3 text-green-500" />
          ) : (
            <WifiOff className="h-3 w-3 text-red-500" />
          )}
          {runningJobs.length > 0 && (
            <Badge variant="secondary" className="text-xs bg-amber-500/20 text-amber-400">
              {runningJobs.length} running
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-zinc-400 hover:text-zinc-100"
            onClick={clearLogs}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-zinc-400 hover:text-zinc-100"
            onClick={onClose}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col overflow-hidden">
        <TabsList className="w-full bg-zinc-900 border-b border-zinc-800 rounded-none h-8 px-2">
          <TabsTrigger value="activity" className="text-xs text-zinc-400 data-[state=active]:text-zinc-100 data-[state=active]:bg-zinc-800">
            Actividad
          </TabsTrigger>
          <TabsTrigger value="jobs" className="text-xs text-zinc-400 data-[state=active]:text-zinc-100 data-[state=active]:bg-zinc-800">
            Jobs {runningJobs.length > 0 && `(${runningJobs.length})`}
          </TabsTrigger>
          <TabsTrigger value="session" className="text-xs text-zinc-400 data-[state=active]:text-zinc-100 data-[state=active]:bg-zinc-800">
            Sesión
          </TabsTrigger>
        </TabsList>

        {/* Tab: Actividad (Tool Calls) */}
        <TabsContent value="activity" className="flex-1 overflow-hidden m-0">
          <ScrollArea className="h-full" ref={scrollRef}>
            <div className="p-3 font-mono text-xs space-y-2">
              {logs.length === 0 ? (
                <div className="text-zinc-500 text-center py-8">
                  <TerminalSquare className="h-8 w-8 mx-auto mb-2 opacity-50" />
                  <p>No hay actividad de herramientas</p>
                  <p className="text-xs mt-1">
                    Los comandos ejecutados aparecerán aquí
                  </p>
                </div>
              ) : (
                logs.map(log => (
                  <div
                    key={log.id}
                    className={cn(
                      "rounded-lg border p-2",
                      log.type === 'tool_call' && "border-blue-500/30 bg-blue-500/5",
                      log.type === 'tool_response' && "border-green-500/30 bg-green-500/5",
                      log.type === 'error' && "border-red-500/30 bg-red-500/5"
                    )}
                  >
                    {log.type === 'tool_call' ? (
                      // Renderizado mejorado para Terminal Call
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <TerminalSquare className="h-3.5 w-3.5 text-blue-400" />
                            <span className="text-blue-400 font-medium text-xs">Terminal Call</span>
                            {log.waitTime && (
                              <span className="flex items-center gap-1 text-zinc-500 text-xs">
                                <Clock className="h-3 w-3" />
                                {log.waitTime}s
                              </span>
                            )}
                          </div>
                          <span className="text-zinc-600 text-xs">
                            {log.timestamp.toLocaleTimeString()}
                          </span>
                        </div>
                        {log.command ? (
                          <div className="bg-black/40 rounded px-2 py-1.5 text-zinc-200">
                            <span className="text-green-400">$</span> {log.command}
                          </div>
                        ) : (
                          <button
                            onClick={() => toggleExpand(log.id)}
                            className="w-full text-left"
                          >
                            <div className="flex items-center gap-1 text-zinc-500 text-xs">
                              {log.expanded ? (
                                <ChevronDown className="h-3 w-3" />
                              ) : (
                                <ChevronRight className="h-3 w-3" />
                              )}
                              <span>Ver argumentos ({log.name})</span>
                            </div>
                            {log.expanded && (
                              <pre className="mt-2 p-2 bg-black/30 rounded overflow-x-auto text-zinc-400 whitespace-pre-wrap text-xs">
                                {formatJson(log.content)}
                              </pre>
                            )}
                          </button>
                        )}
                      </div>
                    ) : (
                      // Renderizado para Terminal Response
                      <div>
                        <div className="flex items-center justify-between mb-1">
                          <button
                            onClick={() => toggleExpand(log.id)}
                            className="flex items-center gap-2 text-left"
                          >
                            {log.expanded ? (
                              <ChevronDown className="h-3 w-3 text-zinc-400" />
                            ) : (
                              <ChevronRight className="h-3 w-3 text-zinc-400" />
                            )}
                            <TerminalSquare className="h-3.5 w-3.5 text-green-400" />
                            <span className="text-green-400 font-medium text-xs">Terminal Response</span>
                          </button>
                          
                          <div className="flex items-center gap-2">
                            <span className="text-zinc-600 text-xs">
                              {log.timestamp.toLocaleTimeString()}
                            </span>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-6 w-6 text-zinc-500 hover:text-zinc-300"
                              onClick={() => copyContent(log.id, log.content)}
                            >
                              {copiedId === log.id ? (
                                <Check className="h-3 w-3 text-green-500" />
                              ) : (
                                <Copy className="h-3 w-3" />
                              )}
                            </Button>
                          </div>
                        </div>
                        
                        {log.expanded ? (
                          <pre className="mt-2 p-2 bg-black/30 rounded overflow-x-auto text-zinc-300 whitespace-pre-wrap text-xs">
                            {log.content}
                          </pre>
                        ) : (
                          <p className="text-zinc-400 text-xs mt-1 truncate">
                            {log.content.split('\n')[0]?.slice(0, 80) || '(vacío)'}
                            {log.content.length > 80 && '...'}
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </ScrollArea>
        </TabsContent>

        {/* Tab: Jobs en ejecución */}
        <TabsContent value="jobs" className="flex-1 overflow-hidden m-0">
          <ScrollArea className="h-full">
            <div className="p-3 font-mono text-xs space-y-2">
              {!isConnected ? (
                <div className="text-zinc-500 text-center py-8">
                  <WifiOff className="h-8 w-8 mx-auto mb-2 opacity-50" />
                  <p>Sandbox desconectado</p>
                  <p className="text-xs mt-1">
                    Esperando conexión con Kali...
                  </p>
                </div>
              ) : runningJobs.length === 0 ? (
                <div className="text-zinc-500 text-center py-8">
                  <Play className="h-8 w-8 mx-auto mb-2 opacity-50" />
                  <p>Sin procesos activos</p>
                  <p className="text-xs mt-1">
                    Los comandos en ejecución aparecerán aquí
                  </p>
                </div>
              ) : (
                runningJobs.map(job => (
                  <div
                    key={job.id}
                    className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <Loader2 className="h-3 w-3 animate-spin text-amber-500" />
                        <Badge variant="outline" className="text-xs border-amber-500/50 text-amber-400">
                          RUNNING
                        </Badge>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 px-2 text-xs text-red-400 hover:text-red-300 hover:bg-red-500/10"
                        onClick={() => handleCancelJob(job.id)}
                      >
                        <Square className="h-3 w-3 mr-1" />
                        Stop
                      </Button>
                    </div>
                    
                    <p className="text-zinc-300 font-medium mb-1 truncate" title={job.command}>
                      $ {job.command}
                    </p>
                    
                    <div className="flex items-center gap-3 text-zinc-500 text-xs">
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {job.elapsed || 'iniciando...'}
                      </span>
                      {job.job_id_short && (
                        <span className="font-mono">
                          #{job.job_id_short}
                        </span>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </ScrollArea>
        </TabsContent>

        {/* Tab: Información de sesión */}
        <TabsContent value="session" className="flex-1 overflow-hidden m-0">
          <ScrollArea className="h-full">
            <div className="p-3 font-mono text-xs space-y-3">
              {!conversationId ? (
                <div className="text-zinc-500 text-center py-8">
                  <TerminalSquare className="h-8 w-8 mx-auto mb-2 opacity-50" />
                  <p>Sin conversación activa</p>
                  <p className="text-xs mt-1">
                    Inicia una conversación para ver la sesión
                  </p>
                </div>
              ) : !currentSession?.initialized ? (
                <div className="text-zinc-500 text-center py-8">
                  <Loader2 className="h-8 w-8 mx-auto mb-2 opacity-50 animate-spin" />
                  <p>Inicializando sesión...</p>
                </div>
              ) : (
                <>
                  {/* Estado de conexión */}
                  <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-3">
                    <h4 className="text-zinc-400 text-xs uppercase mb-2">Estado</h4>
                    <div className="flex items-center gap-2">
                      {isConnected ? (
                        <>
                          <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
                          <span className="text-green-400">Conectado</span>
                        </>
                      ) : (
                        <>
                          <div className="h-2 w-2 rounded-full bg-red-500" />
                          <span className="text-red-400">Desconectado</span>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Info de sesión */}
                  <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-3">
                    <h4 className="text-zinc-400 text-xs uppercase mb-2">Sesión</h4>
                    <div className="space-y-2 text-zinc-300">
                      <div className="flex items-center gap-2">
                        <span className="text-zinc-500">ID:</span>
                        <span className="truncate">{conversationId.slice(0, 8)}...</span>
                      </div>
                      {currentSession.repoPath && (
                        <div className="flex items-center gap-2">
                          <span className="text-zinc-500">Workspace:</span>
                          <span className="truncate">{currentSession.repoPath}</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Git Branches */}
                  {sessionInfo && (
                    <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-3">
                      <h4 className="text-zinc-400 text-xs uppercase mb-2 flex items-center gap-2">
                        <GitBranch className="h-3 w-3" />
                        Workspace
                      </h4>
                      <div className="space-y-1">
                        <p className="text-zinc-300">
                          Commit: {sessionInfo.commit?.slice(0, 8) || 'N/A'}
                        </p>
                        <p className="text-zinc-500 text-xs">
                          CWD: {sessionInfo.cwd || 'N/A'}
                        </p>
                        {sessionInfo.files && sessionInfo.files.length > 0 && (
                          <div className="mt-2">
                            <p className="text-zinc-400 text-xs">Archivos ({sessionInfo.files.length}):</p>
                            {sessionInfo.files.slice(0, 5).map((file: string, i: number) => (
                              <div key={i} className="flex items-center gap-2 text-zinc-500 text-xs">
                                <span className="text-green-500">•</span>
                                <span>{file}</span>
                              </div>
                            ))}
                            {sessionInfo.files.length > 5 && (
                              <p className="text-zinc-600 text-xs">...y {sessionInfo.files.length - 5} más</p>
                            )}
                          </div>
                        )}
                        {sessionInfo.tags && sessionInfo.tags.length > 0 && (
                          <div className="mt-2">
                            <p className="text-zinc-400 text-xs">Tags ({sessionInfo.tags.length}):</p>
                            {sessionInfo.tags.slice(-3).map((tag: string, i: number) => (
                              <div key={i} className="flex items-center gap-2 text-zinc-500 text-xs">
                                <span className="text-blue-500">⚑</span>
                                <span>{tag}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </ScrollArea>
        </TabsContent>
      </Tabs>
    </div>
  );
}
