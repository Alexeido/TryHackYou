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
  RotateCcw
} from "lucide-react";
import { cn } from "@/lib/utils";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";

interface MessageBubbleProps {
  message: Message;
  isStreaming?: boolean;
  streamContent?: string;
  onEdit?: (messageId: number, newContent: string) => void;
  onRegenerate?: (messageId: number) => void;
}

// Helper para parsear tool_calls que pueden venir como string JSON o array
function parseToolCalls(toolCalls: ToolCall[] | string | null | undefined): ToolCall[] {
  if (!toolCalls) return [];
  if (Array.isArray(toolCalls)) return toolCalls;
  if (typeof toolCalls === 'string') {
    try {
      const parsed = JSON.parse(toolCalls);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }
  return [];
}

export function MessageBubble({ message, isStreaming, streamContent, onEdit, onRegenerate }: MessageBubbleProps) {
  const [copied, setCopied] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState(message.content || '');
  const [showToolCalls, setShowToolCalls] = useState(false);
  const { fullTree } = useChatStore();

  const content = isStreaming ? streamContent : message.content;
  const isUser = message.role === 'user';
  const isTool = message.role === 'tool';
  
  // Parsear tool_calls correctamente
  const toolCallsArray = useMemo(() => parseToolCalls(message.tool_calls), [message.tool_calls]);
  const hasToolCalls = toolCallsArray.length > 0;

  // Verificar si tiene ramas hermanas (para saber si mostrar el indicador)
  const siblings = fullTree?.filter(n => n.parent_id === message.parent_id) || [];
  const hasBranches = siblings.length > 1;

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
    return (
      <div className="flex justify-start my-2">
        <div className="max-w-[85%] rounded-xl bg-amber-500/10 border border-amber-500/20 p-3">
          <div className="flex items-center gap-2 mb-2">
            <Wrench className="h-4 w-4 text-amber-500" />
            <span className="text-sm font-medium text-amber-500">
              Tool: {message.tool_call_id}
            </span>
          </div>
          <pre className="text-xs bg-black/20 rounded p-2 overflow-x-auto">
            {content}
          </pre>
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

        {/* Tool calls */}
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
              <Wrench className="h-3 w-3 mr-1" />
              {toolCallsArray.length} herramienta(s)
            </Button>
            
            {showToolCalls && (
              <div className="mt-2 space-y-2">
                {toolCallsArray.map((tc, i) => (
                  <div 
                    key={tc.id || i}
                    className="bg-muted/30 rounded-lg p-3 text-sm"
                  >
                    <div className="font-mono text-xs text-muted-foreground mb-1">
                      {tc.function.name}
                    </div>
                    <pre className="text-xs overflow-x-auto">
                      {(() => {
                        try {
                          return JSON.stringify(JSON.parse(tc.function.arguments), null, 2);
                        } catch {
                          return tc.function.arguments;
                        }
                      })()}
                    </pre>
                  </div>
                ))}
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
