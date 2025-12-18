"use client";

import { useEffect, useRef, useState } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useChatStore, Message } from "@/store/useStore";
import { 
  TerminalSquare, 
  X, 
  Trash2,
  ChevronDown,
  ChevronRight,
  Copy,
  Check
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
}

export function TerminalPanel({ onClose }: TerminalPanelProps) {
  const { messages } = useChatStore();
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Extraer tool calls de los mensajes
  useEffect(() => {
    const newLogs: LogEntry[] = [];
    
    messages.forEach(msg => {
      // Tool calls del assistant
      if (msg.tool_calls && msg.tool_calls.length > 0) {
        msg.tool_calls.forEach(tc => {
          newLogs.push({
            id: tc.id,
            type: 'tool_call',
            timestamp: new Date(msg.created_at),
            name: tc.function.name,
            content: tc.function.arguments,
          });
        });
      }
      
      // Respuestas de tools
      if (msg.role === 'tool' && msg.content) {
        newLogs.push({
          id: `tool-response-${msg.id}`,
          type: 'tool_response',
          timestamp: new Date(msg.created_at),
          name: msg.tool_call_id || 'tool',
          content: msg.content,
        });
      }
    });
    
    setLogs(newLogs);
  }, [messages]);

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

  return (
    <div className="h-full flex flex-col bg-zinc-950 text-zinc-100">
      {/* Header */}
      <div className="h-10 bg-zinc-900 border-b border-zinc-800 flex items-center px-3 justify-between shrink-0">
        <div className="flex items-center gap-2">
          <TerminalSquare className="h-4 w-4 text-green-500" />
          <span className="text-sm font-medium">Terminal</span>
          {logs.length > 0 && (
            <Badge variant="secondary" className="text-xs bg-zinc-800">
              {logs.length}
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

      {/* Content */}
      <ScrollArea className="flex-1" ref={scrollRef}>
        <div className="p-3 font-mono text-xs space-y-2">
          {logs.length === 0 ? (
            <div className="text-zinc-500 text-center py-8">
              <TerminalSquare className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p>No hay actividad de herramientas</p>
              <p className="text-xs mt-1">
                Los tool calls aparecerán aquí
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
                <div className="flex items-center justify-between mb-1">
                  <button
                    onClick={() => toggleExpand(log.id)}
                    className="flex items-center gap-2 text-left"
                  >
                    {log.expanded ? (
                      <ChevronDown className="h-3 w-3" />
                    ) : (
                      <ChevronRight className="h-3 w-3" />
                    )}
                    <Badge 
                      variant="outline" 
                      className={cn(
                        "text-xs",
                        log.type === 'tool_call' && "border-blue-500/50 text-blue-400",
                        log.type === 'tool_response' && "border-green-500/50 text-green-400"
                      )}
                    >
                      {log.type === 'tool_call' ? 'CALL' : 'RESPONSE'}
                    </Badge>
                    {log.name && (
                      <span className="text-zinc-300">{log.name}</span>
                    )}
                  </button>
                  
                  <div className="flex items-center gap-2">
                    <span className="text-zinc-600">
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
                
                {log.expanded && (
                  <pre className="mt-2 p-2 bg-black/30 rounded overflow-x-auto text-zinc-300">
                    {formatJson(log.content)}
                  </pre>
                )}
                
                {!log.expanded && (
                  <p className="text-zinc-500 truncate mt-1">
                    {log.content.slice(0, 100)}...
                  </p>
                )}
              </div>
            ))
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
