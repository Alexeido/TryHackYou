"use client";

import { useState, useMemo } from "react";
import { Message, useChatStore, ToolCall } from "@/store/useStore";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { BranchIndicator } from "./BranchIndicator";
import { 
  Pencil, 
  Copy, 
  Check, 
  Bot,
  User,
  Wrench,
  ChevronDown,
  ChevronRight,
  RotateCcw,
  TerminalSquare,
  Clock,
  Target,
  CheckCircle2,
  XCircle,
  AlertCircle,
  ListTodo
} from "lucide-react";
import { cn } from "@/lib/utils";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";

// ============================================================================
// GEMINI 3 FIX: Parser seguro para JSONs concatenados
// Gemini a veces envía: {"action":"create"}{"command":"nmap..."}
// ============================================================================
function safeParseToolArgs(jsonStr: string): Record<string, unknown> {
  if (!jsonStr || !jsonStr.trim()) return {};
  
  // Intento directo
  try {
    return JSON.parse(jsonStr);
  } catch {
    // Si falla, puede ser JSONs concatenados - extraer el primero
    let depth = 0;
    let start = -1;
    let inString = false;
    let escapeNext = false;
    
    for (let i = 0; i < jsonStr.length; i++) {
      const char = jsonStr[i];
      
      if (escapeNext) {
        escapeNext = false;
        continue;
      }
      
      if (char === '\\' && inString) {
        escapeNext = true;
        continue;
      }
      
      if (char === '"' && !escapeNext) {
        inString = !inString;
        continue;
      }
      
      if (inString) continue;
      
      if (char === '{') {
        if (depth === 0) start = i;
        depth++;
      } else if (char === '}') {
        depth--;
        if (depth === 0 && start >= 0) {
          // Primer objeto JSON completo encontrado
          const firstJson = jsonStr.substring(start, i + 1);
          try {
            return JSON.parse(firstJson);
          } catch {
            return {};
          }
        }
      }
    }
  }
  
  return {};
}

interface MessageBubbleProps {
  message: Message;
  isStreaming?: boolean;
  streamContent?: string;
  toolResponseContent?: string; // Contenido del tool response si existe
  onEdit?: (messageId: number, newContent: string) => void;
  onRegenerate?: (messageId: number) => void;
}

// Helper para parsear el contenido de un tool response
function parseToolResponse(content: string | undefined): {
  jobId?: string;
  status?: string;
  exitCode?: number;
  stdout?: string;
  stderr?: string;
  error?: string;
  isRunning: boolean;
  isCompleted: boolean;
  isError: boolean;
} {
  if (!content) return { isRunning: false, isCompleted: false, isError: false };
  
  const lines = content.split('\n');
  const result: ReturnType<typeof parseToolResponse> = { isRunning: false, isCompleted: false, isError: false };
  
  let currentSection = '';
  const sectionContent: string[] = [];
  
  for (const line of lines) {
    if (line.startsWith('JOB_ID:')) {
      result.jobId = line.replace('JOB_ID:', '').trim();
    } else if (line.startsWith('STATUS:')) {
      result.status = line.replace('STATUS:', '').trim();
      result.isRunning = result.status.includes('running');
      result.isError = result.status.includes('error') || result.status.includes('not_found');
    } else if (line.startsWith('ERROR:')) {
      result.error = line.replace('ERROR:', '').trim();
      result.isError = true;
      result.isCompleted = true; // Un error es un estado final
    } else if (line.startsWith('EXIT_CODE:') || line.startsWith('EXIT CODE:')) {
      // Soportar ambos formatos: EXIT_CODE: y EXIT CODE:
      const code = parseInt(line.replace(/EXIT[_ ]CODE:/i, '').trim());
      result.exitCode = isNaN(code) ? undefined : code;
      result.isCompleted = true;
    } else if (line.startsWith('STDOUT:')) {
      if (currentSection === 'stderr') result.stderr = sectionContent.join('\n');
      currentSection = 'stdout';
      sectionContent.length = 0;
    } else if (line.startsWith('STDERR:')) {
      if (currentSection === 'stdout') result.stdout = sectionContent.join('\n');
      currentSection = 'stderr';
      sectionContent.length = 0;
    } else if (currentSection) {
      sectionContent.push(line);
    }
  }
  
  // Guardar última sección
  if (currentSection === 'stdout') result.stdout = sectionContent.join('\n').trim();
  if (currentSection === 'stderr') result.stderr = sectionContent.join('\n').trim();
  
  return result;
}

// Helper para detectar y parsear responses de manage_mission
interface MissionResponse {
  isMissionResponse: boolean;
  status?: string;
  message?: string;
  missionId?: string;
  progress?: {
    total: number;
    completed: number;
    failed: number;
    pending: number;
    in_progress: number;
  };
  newPhase?: string;
  objectiveIds?: number[];
  objectivesCount?: number;
  nextAction?: string;
  error?: string;
}

function parseMissionResponse(content: string | undefined): MissionResponse {
  if (!content) return { isMissionResponse: false };
  
  // Intentar parsear como JSON
  try {
    const parsed = JSON.parse(content);
    
    // Verificar si es un response de manage_mission
    if (parsed.status === 'success' || parsed.error) {
      const isMissionRelated = 
        parsed.mission_id || 
        parsed.message?.includes('Misión') || 
        parsed.message?.includes('Objetivo') ||
        parsed.message?.includes('Fase') ||
        parsed.progress ||
        parsed.objective_ids;
      
      if (isMissionRelated || parsed.error) {
        return {
          isMissionResponse: true,
          status: parsed.status,
          message: parsed.message,
          missionId: parsed.mission_id,
          progress: parsed.progress || parsed.final_progress,
          newPhase: parsed.new_phase,
          objectiveIds: parsed.objective_ids,
          objectivesCount: parsed.objectives_count,
          nextAction: parsed.NEXT_ACTION,
          error: parsed.error
        };
      }
    }
  } catch {
    // No es JSON válido, probablemente es output de terminal
  }
  
  return { isMissionResponse: false };
}

// Helper para parsear tool_calls que pueden venir como string JSON o array
function parseToolCalls(toolCalls: ToolCall[] | string | null | undefined): ToolCall[] {
  if (!toolCalls) return [];
  let parsed: unknown[] = [];
  
  if (Array.isArray(toolCalls)) {
    parsed = toolCalls;
  } else if (typeof toolCalls === 'string') {
    try {
      const result = JSON.parse(toolCalls);
      parsed = Array.isArray(result) ? result : [];
    } catch {
      return [];
    }
  }
  
  // Filtrar elementos de metadata (reasoning_content) que no son tool calls reales
  // Estos tienen estructura { _metadata: { ... } } en lugar de { id, function, ... }
  return parsed.filter((tc): tc is ToolCall => {
    if (!tc || typeof tc !== 'object') return false;
    // Si tiene _metadata, es un elemento de metadata, no un tool call
    if ('_metadata' in tc) return false;
    // Un tool call real tiene 'function' con 'name'
    const toolCall = tc as ToolCall;
    return !!toolCall.function?.name;
  });
}

export function MessageBubble({ message, isStreaming, streamContent, toolResponseContent, onEdit, onRegenerate }: MessageBubbleProps) {
  // Parsear el tool response para saber si el comando está corriendo o completado
  const toolResponse = useMemo(() => parseToolResponse(toolResponseContent), [toolResponseContent]);
  const toolExecuted = !!toolResponseContent && (toolResponse.isCompleted || toolResponse.isError);
  const [copied, setCopied] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState(message.content || '');
  const [showToolCalls, setShowToolCalls] = useState(false);
  const [expandedToolContent, setExpandedToolContent] = useState(false);
  const { fullTree } = useChatStore();

  const content = isStreaming ? streamContent : message.content;
  const isUser = message.role === 'user';
  const isTool = message.role === 'tool';
  
  // Ocultar mensajes internos del sistema (como notificaciones de jobs)
  const isInternalMessage = isUser && content?.startsWith('[BACKGROUND_JOB_COMPLETED]');
  
  // Parsear tool_calls correctamente
  const toolCallsArray = useMemo(() => parseToolCalls(message.tool_calls), [message.tool_calls]);
  const hasToolCalls = toolCallsArray.length > 0;

  // Verificar si tiene ramas hermanas (para saber si mostrar el indicador)
  const siblings = fullTree?.filter(n => n.parent_id === message.parent_id) || [];
  const hasBranches = siblings.length > 1;

  // No renderizar mensajes internos del sistema
  if (isInternalMessage) {
    return null;
  }

  const handleCopy = async () => {
    if (!content) return;
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleStartEdit = () => {
    setEditContent(message.content || '');
    setIsEditing(true);
  };

  const handleCancelEdit = () => {
    setEditContent(message.content || '');
    setIsEditing(false);
  };

  const handleSaveEdit = () => {
    if (editContent.trim() && onEdit) {
      onEdit(message.id, editContent.trim());
    }
    setIsEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSaveEdit();
    } else if (e.key === 'Escape') {
      handleCancelEdit();
    }
  };

  if (isTool) {
    // Primero verificar si es un response de manage_mission
    const missionParsed = parseMissionResponse(content);
    
    if (missionParsed.isMissionResponse) {
      // Render especial para responses de misión
      const isError = !!missionParsed.error;
      const isSuccess = missionParsed.status === 'success';
      
      return (
        <div className="flex justify-start my-2">
          <div className={cn(
            "max-w-[85%] rounded-xl p-3",
            isError 
              ? "bg-red-500/10 border border-red-500/20"
              : "bg-blue-500/10 border border-blue-500/20"
          )}>
            {/* Header */}
            <div className="flex items-center gap-2 mb-2">
              {isError ? (
                <XCircle className="h-4 w-4 text-red-500" />
              ) : missionParsed.progress ? (
                <Target className="h-4 w-4 text-blue-500" />
              ) : (
                <ListTodo className="h-4 w-4 text-blue-500" />
              )}
              <span className={cn(
                "text-sm font-medium",
                isError ? "text-red-500" : "text-blue-500"
              )}>
                {isError ? "Error de Misión" : 
                 missionParsed.newPhase ? "Cambio de Fase" :
                 missionParsed.objectivesCount ? "Misión Creada" :
                 missionParsed.progress ? "Estado de Misión" : "Actualización"}
              </span>
            </div>
            
            {/* Mensaje principal */}
            {(missionParsed.message || missionParsed.error) && (
              <p className={cn(
                "text-sm mb-2",
                isError ? "text-red-400" : "text-foreground"
              )}>
                {missionParsed.message || missionParsed.error}
              </p>
            )}
            
            {/* Progreso si existe */}
            {missionParsed.progress && (
              <div className="flex flex-wrap gap-2 text-xs">
                <span className="px-2 py-1 rounded bg-green-500/20 text-green-400">
                  ✓ {missionParsed.progress.completed} completados
                </span>
                {missionParsed.progress.in_progress > 0 && (
                  <span className="px-2 py-1 rounded bg-amber-500/20 text-amber-400">
                    ⏳ {missionParsed.progress.in_progress} en progreso
                  </span>
                )}
                {missionParsed.progress.pending > 0 && (
                  <span className="px-2 py-1 rounded bg-zinc-500/20 text-zinc-400">
                    ○ {missionParsed.progress.pending} pendientes
                  </span>
                )}
                {missionParsed.progress.failed > 0 && (
                  <span className="px-2 py-1 rounded bg-red-500/20 text-red-400">
                    ✗ {missionParsed.progress.failed} fallidos
                  </span>
                )}
              </div>
            )}
            
            {/* Nueva fase */}
            {missionParsed.newPhase && (
              <div className="text-xs text-blue-400 mt-1">
                Nueva fase: <span className="font-medium">{missionParsed.newPhase}</span>
              </div>
            )}
          </div>
        </div>
      );
    }
    
    // Parsear el contenido del tool response (terminal)
    const parsed = parseToolResponse(content);
    
    // Si está running y no hay stdout ni error, no mostrar nada
    if (parsed.isRunning && !parsed.stdout && !parsed.stderr && !parsed.error) {
      return null;
    }
    
    const isError = parsed.isError || (parsed.exitCode !== undefined && parsed.exitCode !== 0);
    const hasOutput = !!(parsed.stdout || parsed.stderr || parsed.error);
    
    // Determinar qué mostrar
    const outputLines = (parsed.stdout || parsed.stderr || '').split('\n');
    const isLongContent = outputLines.length > 6;
    const previewLines = isLongContent ? outputLines.slice(0, 6) : outputLines;
    
    return (
      <div className="flex justify-start my-2">
        <div className={cn(
          "max-w-[85%] rounded-xl p-3",
          parsed.isRunning 
            ? "bg-amber-500/10 border border-amber-500/20"
            : isError 
              ? "bg-red-500/10 border border-red-500/20"
              : "bg-green-500/10 border border-green-500/20"
        )}>
          {/* Header */}
          <div className="flex items-center justify-between gap-3 mb-2">
            <div className="flex items-center gap-2">
              <TerminalSquare className={cn(
                "h-4 w-4",
                parsed.isRunning ? "text-amber-500" : isError ? "text-red-500" : "text-green-500"
              )} />
              <span className={cn(
                "text-sm font-medium",
                parsed.isRunning ? "text-amber-500" : isError ? "text-red-500" : "text-green-500"
              )}>
                {parsed.isRunning ? "Respuesta temporal" : isError ? "Error" : "Terminal Response"}
              </span>
              {parsed.isRunning && (
                <span className="flex gap-1">
                  <span className="w-1.5 h-1.5 bg-amber-500 rounded-full animate-pulse" />
                  <span className="w-1.5 h-1.5 bg-amber-500 rounded-full animate-pulse [animation-delay:0.2s]" />
                  <span className="w-1.5 h-1.5 bg-amber-500 rounded-full animate-pulse [animation-delay:0.4s]" />
                </span>
              )}
            </div>
            {parsed.exitCode !== undefined && (
              <span className={cn(
                "text-xs font-mono px-2 py-0.5 rounded",
                isError ? "bg-red-500/20 text-red-400" : "bg-zinc-700/50 text-zinc-400"
              )}>
                exit: {parsed.exitCode}
              </span>
            )}
          </div>
          
          {/* Error message */}
          {parsed.error && (
            <div className="text-xs bg-red-500/10 rounded p-2 text-red-400 mb-2">
              {parsed.error}
            </div>
          )}
          
          {/* Output content */}
          {(parsed.stdout || parsed.stderr) && (
            <>
              {/* STDERR en rojo */}
              {parsed.stderr && (
                <pre className="text-xs bg-black/30 rounded p-2 overflow-x-auto whitespace-pre-wrap text-red-400 mb-2">
                  {parsed.stderr}
                </pre>
              )}
              
              {/* STDOUT normal */}
              {parsed.stdout && (
                <pre className="text-xs bg-black/20 rounded p-2 overflow-x-auto whitespace-pre-wrap text-foreground">
                  {expandedToolContent ? parsed.stdout : previewLines.join('\n')}
                  {isLongContent && !expandedToolContent && '\n...'}
                </pre>
              )}
              
              {isLongContent && (
                <Button
                  variant="ghost"
                  size="sm"
                  className={cn(
                    "mt-2 h-6 px-2 text-xs",
                    parsed.isRunning ? "text-amber-400 hover:text-amber-300" : "text-green-400 hover:text-green-300"
                  )}
                  onClick={() => setExpandedToolContent(!expandedToolContent)}
                >
                  {expandedToolContent ? (
                    <><ChevronDown className="h-3 w-3 mr-1" /> Ver menos</>
                  ) : (
                    <><ChevronRight className="h-3 w-3 mr-1" /> Ver más ({outputLines.length - 6} líneas más)</>
                  )}
                </Button>
              )}
            </>
          )}
          
          {/* Mensaje de running sin output */}
          {parsed.isRunning && !hasOutput && (
            <p className="text-xs text-muted-foreground italic">
              Ejecutando en segundo plano...
            </p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "group flex gap-3 py-4 px-2 rounded-xl transition-colors",
        isUser ? "flex-row-reverse" : "",
        !isStreaming && "hover:bg-muted/30"
      )}
    >
      {/* Avatar */}
      <div className={cn(
        "w-8 h-8 rounded-lg flex items-center justify-center shrink-0",
        isUser 
          ? "bg-primary text-primary-foreground" 
          : "bg-gradient-to-br from-violet-500 to-purple-600 text-white"
      )}>
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      {/* Content */}
      <div className={cn(
        "flex-1 min-w-0",
        isUser ? "items-end" : "items-start"
      )}>
        {/* Header con modelo y branch indicator */}
        <div className={cn(
          "flex items-center gap-2 mb-1",
          isUser ? "justify-end" : "justify-start"
        )}>
          {!isUser && message.model_used && (
            <Badge variant="secondary" className="text-xs font-normal">
              {message.model_used}
            </Badge>
          )}
          
          {/* Indicador de ramas con flechas de navegación */}
          {hasBranches && (
            <BranchIndicator 
              messageId={message.id} 
              parentId={message.parent_id} 
            />
          )}
        </div>

        {/* Message content */}
        <div className={cn(
          "rounded-2xl px-4 py-3",
          isUser 
            ? "bg-primary text-primary-foreground ml-12" 
            : "bg-muted/50 mr-12",
          isStreaming && "animate-pulse"
        )}>
          {/* Tool call status indicator - siempre mostrar si hay tool_calls */}
          {hasToolCalls && !isEditing && (
            <div className="mb-3">
              {(() => {
                const firstTool = toolCallsArray[0];
                const toolName = firstTool?.function?.name || '';
                // Usar parser seguro para JSONs concatenados (Gemini 3 fix)
                const rawArgs = firstTool?.function?.arguments || '{}';
                const args = safeParseToolArgs(rawArgs) as { command?: string; job_id?: string };
                
                const isCheckJob = toolName === 'check_job_status';
                
                // ========== CHECK_JOB_STATUS ==========
                if (isCheckJob) {
                  // Completado (con resultado o error)
                  if (toolExecuted) {
                    return (
                      <div className="flex items-center gap-3 text-sm">
                        <Clock className="h-5 w-5 text-blue-500" />
                        <span className="text-blue-400">Estado del job consultado</span>
                      </div>
                    );
                  }
                  // En progreso
                  return (
                    <>
                      <div className="flex items-center gap-3 text-sm">
                        <div className="relative">
                          <Clock className="h-5 w-5 text-blue-500" />
                          <span className="absolute -top-0.5 -right-0.5 h-2 w-2 bg-blue-500 rounded-full animate-ping" />
                        </div>
                        <span className="text-muted-foreground">
                          Consultando estado del job...
                        </span>
                      </div>
                      <div className="bg-zinc-900/50 rounded-lg p-2 font-mono text-xs text-blue-400 overflow-hidden mt-2">
                        <div className="flex items-center gap-2">
                          <span className="text-zinc-500">job_id:</span>
                          <span className="animate-pulse">{args.job_id || 'checking...'}</span>
                        </div>
                      </div>
                    </>
                  );
                }
                
                // ========== EXECUTE_COMMAND ==========
                // Completado
                if (toolExecuted) {
                  return (
                    <div className="flex flex-col gap-1">
                      <div className="flex items-center gap-2 text-sm">
                        <TerminalSquare className="h-5 w-5 text-green-500" />
                        <span className="text-green-400">Comando ejecutado</span>
                      </div>
                      <div className="font-mono text-xs text-muted-foreground bg-zinc-800/50 px-2 py-1 rounded ml-7">
                        $ {args.command}
                      </div>
                    </div>
                  );
                }
                
                // Running en segundo plano (tiene response pero sigue corriendo)
                if (toolResponseContent && toolResponse.isRunning) {
                  return (
                    <div className="flex flex-col gap-1">
                      <div className="flex items-center gap-2 text-sm">
                        <div className="relative">
                          <TerminalSquare className="h-5 w-5 text-amber-500" />
                          <span className="absolute -top-0.5 -right-0.5 h-2 w-2 bg-amber-500 rounded-full animate-ping" />
                        </div>
                        <span className="text-amber-400">Ejecutando en segundo plano</span>
                      </div>
                      <div className="font-mono text-xs text-muted-foreground bg-zinc-800/50 px-2 py-1 rounded ml-7">
                        $ {args.command}
                      </div>
                    </div>
                  );
                }
                
                // Animación inicial (sin tool response aún)
                return (
                  <>
                    <div className="flex items-center gap-3 text-sm">
                      <div className="relative">
                        <TerminalSquare className="h-5 w-5 text-amber-500" />
                        <span className="absolute -top-0.5 -right-0.5 h-2 w-2 bg-amber-500 rounded-full animate-ping" />
                      </div>
                      <span className="text-muted-foreground">
                        Ejecutando comando{toolCallsArray.length > 1 ? 's' : ''} en terminal...
                      </span>
                    </div>
                    <div className="bg-zinc-900/50 rounded-lg p-2 font-mono text-xs text-green-400 overflow-hidden mt-2">
                      <div className="flex items-center gap-2">
                        <span className="text-zinc-500">$</span>
                        <span className="animate-pulse">
                          {args.command?.slice(0, 50) || 'ejecutando...'}
                          {(args.command?.length || 0) > 50 ? '...' : ''}
                        </span>
                        <span className="inline-flex ml-1">
                          <span className="animate-[blink_1s_infinite]">_</span>
                        </span>
                      </div>
                      <div className="flex gap-1.5 mt-1.5">
                        <span className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse [animation-delay:0s]" />
                        <span className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse [animation-delay:0.2s]" />
                        <span className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse [animation-delay:0.4s]" />
                      </div>
                    </div>
                  </>
                );
              })()}
            </div>
          )}
          
          {isEditing ? (
            // Modo edición
            <div className="space-y-2">
              <textarea
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                onKeyDown={handleKeyDown}
                className={cn(
                  "w-full min-h-[80px] p-2 rounded-lg resize-none",
                  "bg-background/50 text-foreground border border-border",
                  "focus:outline-none focus:ring-2 focus:ring-primary"
                )}
                autoFocus
              />
              <div className="flex gap-2 justify-end">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleCancelEdit}
                >
                  Cancelar
                </Button>
                <Button
                  size="sm"
                  onClick={handleSaveEdit}
                  disabled={!editContent.trim()}
                >
                  Guardar y enviar
                </Button>
              </div>
            </div>
          ) : content ? (
            <div className={cn(
              "prose prose-sm dark:prose-invert max-w-none",
              isUser && "prose-invert"
            )}>
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  code: ({ className, children, ...props }) => {
                    const match = /language-(\w+)/.exec(className || '');
                    const isInline = !match;
                    
                    if (isInline) {
                      return (
                        <code 
                          className={cn(
                            "px-1.5 py-0.5 rounded text-sm font-mono",
                            isUser 
                              ? "bg-white/20" 
                              : "bg-black/10 dark:bg-white/10"
                          )} 
                          {...props}
                        >
                          {children}
                        </code>
                      );
                    }
                    
                    return (
                      <div className="relative group/code my-3">
                        <div className="absolute right-2 top-2 opacity-0 group-hover/code:opacity-100 transition-opacity">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 px-2 text-xs"
                            onClick={() => {
                              navigator.clipboard.writeText(String(children).replace(/\n$/, ''));
                            }}
                          >
                            <Copy className="h-3 w-3 mr-1" />
                            Copiar
                          </Button>
                        </div>
                        <SyntaxHighlighter
                          style={oneDark}
                          language={match[1]}
                          PreTag="div"
                          className="rounded-lg !my-0 text-sm"
                        >
                          {String(children).replace(/\n$/, '')}
                        </SyntaxHighlighter>
                      </div>
                    );
                  },
                  p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                  ul: ({ children }) => <ul className="mb-2 list-disc pl-4">{children}</ul>,
                  ol: ({ children }) => <ol className="mb-2 list-decimal pl-4">{children}</ol>,
                  li: ({ children }) => <li className="mb-1">{children}</li>,
                  a: ({ href, children }) => (
                    <a 
                      href={href} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="text-blue-400 hover:underline"
                    >
                      {children}
                    </a>
                  ),
                }}
              >
                {content}
              </ReactMarkdown>
            </div>
          ) : isStreaming ? (
            <div className="flex items-center gap-2">
              <div className="flex gap-1">
                <span className="w-2 h-2 bg-current rounded-full animate-bounce [animation-delay:-0.3s]" />
                <span className="w-2 h-2 bg-current rounded-full animate-bounce [animation-delay:-0.15s]" />
                <span className="w-2 h-2 bg-current rounded-full animate-bounce" />
              </div>
              <span className="text-sm text-muted-foreground">Pensando...</span>
            </div>
          ) : null}
        </div>

        {/* Tool calls - Terminal Calls */}
        {hasToolCalls && (
          <div className="mt-2 ml-4">
            <Button
              variant="ghost"
              size="sm"
              className="text-xs text-muted-foreground"
              onClick={() => setShowToolCalls(!showToolCalls)}
            >
              {showToolCalls ? (
                <ChevronDown className="h-3 w-3 mr-1" />
              ) : (
                <ChevronRight className="h-3 w-3 mr-1" />
              )}
              <TerminalSquare className="h-3 w-3 mr-1" />
              {toolCallsArray.length} Terminal Call{toolCallsArray.length > 1 ? 's' : ''}
            </Button>
            
            {showToolCalls && (
              <div className="mt-2 space-y-2">
                {toolCallsArray.map((tc, i) => {
                  // Parsear argumentos con parser seguro (Gemini 3 fix)
                  const args = safeParseToolArgs(tc.function.arguments) as { 
                    command?: string; 
                    wait_time?: number; 
                    exit_time?: number; 
                    job_id?: string 
                  };
                  
                  const isCheckJob = tc.function.name === 'check_job_status';
                  // Si el mensaje ya tiene contenido, el comando ya se completó
                  const isCompleted = !!content;
                  
                  return (
                    <div 
                      key={tc.id || i}
                      className={cn(
                        "rounded-lg p-3 text-sm",
                        isCheckJob 
                          ? "bg-blue-500/10 border border-blue-500/20"
                          : isCompleted
                            ? "bg-green-500/10 border border-green-500/20"
                            : "bg-amber-500/10 border border-amber-500/20"
                      )}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        {isCheckJob ? (
                          <>
                            <Clock className="h-3.5 w-3.5 text-blue-400" />
                            <span className="text-xs text-blue-400 font-medium">Job Status Check</span>
                          </>
                        ) : isCompleted ? (
                          <>
                            <TerminalSquare className="h-3.5 w-3.5 text-green-500" />
                            <span className="text-xs text-green-500 font-medium">Comando ejecutado</span>
                            {args.wait_time && (
                              <span className="flex items-center gap-1 text-xs text-muted-foreground">
                                <Clock className="h-3 w-3" />
                                {args.wait_time}s
                              </span>
                            )}
                          </>
                        ) : (
                          <>
                            <TerminalSquare className="h-3.5 w-3.5 text-amber-400" />
                            <span className="text-xs text-amber-400 font-medium">Terminal Call</span>
                            {args.wait_time && (
                              <span className="flex items-center gap-1 text-xs text-muted-foreground">
                                <Clock className="h-3 w-3" />
                                {args.wait_time}s
                              </span>
                            )}
                          </>
                        )}
                      </div>
                      {isCheckJob && args.job_id && (
                        <div className="font-mono text-sm bg-black/20 rounded px-2 py-1.5 text-foreground">
                          <span className="text-blue-400">job_id:</span> {args.job_id}
                        </div>
                      )}
                      {!isCheckJob && args.command && (
                        <div className="font-mono text-sm bg-black/20 rounded px-2 py-1.5 text-foreground">
                          <span className="text-green-400">$</span> {args.command}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Actions */}
        {!isStreaming && content && (
          <div className={cn(
            "flex items-center gap-1 mt-1 opacity-0 group-hover:opacity-100 transition-opacity",
            isUser ? "justify-end mr-12" : "justify-start ml-4"
          )}>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs text-muted-foreground"
              onClick={handleCopy}
            >
              {copied ? (
                <>
                  <Check className="h-3 w-3 mr-1" />
                  Copiado
                </>
              ) : (
                <>
                  <Copy className="h-3 w-3 mr-1" />
                  Copiar
                </>
              )}
            </Button>
            
            {isUser && !isEditing && (
              <Button
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-xs text-muted-foreground"
                onClick={handleStartEdit}
              >
                <Pencil className="h-3 w-3 mr-1" />
                Editar
              </Button>
            )}
            
            {!isUser && onRegenerate && (
              <Button
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-xs text-muted-foreground"
                onClick={() => onRegenerate(message.id)}
              >
                <RotateCcw className="h-3 w-3 mr-1" />
                Regenerar
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
