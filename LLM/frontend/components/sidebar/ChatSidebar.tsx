"use client";

import { useEffect, useCallback, useState } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Input } from "@/components/ui/input";
import {
  useConversationsStore,
  useChatStore,
  useConfigStore,
  useUIStore,
  Conversation,
} from "@/store/useStore";
import { 
  getConversations, 
  getConversationThread, 
  getConversationTree,
  deleteConversation,
  toggleConversationPin,
  renameConversation 
} from "@/services/api";
import { 
  Plus, 
  MessageSquare, 
  Trash2, 
  Settings,
  Loader2,
  ChevronLeft,
  Search,
  Pin,
  PinOff,
  Pencil,
  Check,
  X
} from "lucide-react";
import { cn } from "@/lib/utils";
import { formatDistanceToNow } from "@/lib/dateUtils";

export function ChatSidebar() {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  
  const { 
    conversations, 
    isLoading, 
    setConversations, 
    setLoading,
    removeConversation,
    updateConversation 
  } = useConversationsStore();
  
  const { 
    conversationId, 
    setConversation, 
    setMessages, 
    resetChat,
    setActiveLeafId,
    setFullTree
  } = useChatStore();
  
  const { isSidebarOpen, toggleSidebar, setConfigModalOpen } = useUIStore();
  const { systemPrompt } = useConfigStore();

  // Cargar conversaciones al inicio
  const loadConversations = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getConversations();
      setConversations(data);
    } catch (err) {
      console.error("Error loading conversations:", err);
    } finally {
      setLoading(false);
    }
  }, [setLoading, setConversations]);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  const handleSelectConversation = async (id: string) => {
    if (id === conversationId) return;
    
    try {
      setConversation(id);
      
      // Cargar thread y tree
      const [thread, tree] = await Promise.all([
        getConversationThread(id),
        getConversationTree(id),
      ]);
      
      setMessages(thread.messages);
      setActiveLeafId(thread.active_leaf_id);
      setFullTree(tree.nodes);
    } catch (err) {
      console.error("Error loading conversation:", err);
    }
  };

  const handleNewChat = () => {
    resetChat();
  };

  const handleDeleteConversation = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    
    try {
      await deleteConversation(id);
      removeConversation(id);
      
      // Si era la conversación activa, resetear
      if (id === conversationId) {
        resetChat();
      }
    } catch (err) {
      console.error("Error deleting conversation:", err);
    }
  };

  const handlePinConversation = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    
    try {
      const result = await toggleConversationPin(id);
      updateConversation(id, { pinned: result.pinned });
      // Recargar lista para que se reordene
      loadConversations();
    } catch (err) {
      console.error("Error pinning conversation:", err);
    }
  };

  const handleRenameConversation = async (id: string, newTitle: string) => {
    if (!newTitle.trim()) return;
    
    try {
      await renameConversation(id, newTitle);
      updateConversation(id, { title: newTitle });
    } catch (err) {
      console.error("Error renaming conversation:", err);
    }
  };

  // Agrupar por fecha (separando fijadas)
  const groupedConversations = groupByDate(conversations);

  if (!isSidebarOpen) {
    return (
      <div className="h-full w-12 bg-sidebar border-r flex flex-col items-center py-4 gap-2">
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleSidebar}
          className="mb-2"
        >
          <ChevronLeft className="h-4 w-4 rotate-180" />
        </Button>
        <Separator className="w-8" />
        <Button
          variant="ghost"
          size="icon"
          onClick={handleNewChat}
          className="text-muted-foreground hover:text-foreground"
        >
          <Plus className="h-5 w-5" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setConfigModalOpen(true)}
          className="text-muted-foreground hover:text-foreground mt-auto"
        >
          <Settings className="h-5 w-5" />
        </Button>
      </div>
    );
  }

  return (
    <div className="h-full bg-sidebar border-r flex flex-col">
      {/* Header */}
      <div className="p-4 border-b">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-lg font-semibold flex items-center gap-2">
            <span className="h-6 w-6 rounded bg-black border border-green-500 text-green-400 text-sm font-bold flex items-center justify-center">
              #
            </span>
            TryHackYou
          </h1>
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleSidebar}
            className="text-muted-foreground"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
        </div>
        
        <Button 
          onClick={handleNewChat}
          className="w-full justify-start gap-2"
          variant="outline"
        >
          <Plus className="h-4 w-4" />
          Nueva conversación
        </Button>
      </div>

      {/* Conversations list */}
      <ScrollArea className="flex-1 px-2">
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : conversations.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <MessageSquare className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">No hay conversaciones</p>
            <p className="text-xs mt-1">Crea una nueva para empezar</p>
          </div>
        ) : (
          <div className="py-2 space-y-4">
            {Object.entries(groupedConversations).map(([group, convs]) => (
              <div key={group}>
                <h3 className="text-xs font-medium text-muted-foreground px-2 mb-2">
                  {group}
                </h3>
                <div className="space-y-1">
                  {convs.map((conv) => {
                    const isEditing = editingId === conv.id;
                    
                    return (
                      <div
                        key={conv.id}
                        onClick={() => !isEditing && handleSelectConversation(conv.id)}
                        className={cn(
                          "w-full text-left px-2 py-1.5 rounded-lg text-sm group transition-colors",
                          !isEditing && "cursor-pointer hover:bg-sidebar-accent",
                          conv.id === conversationId && "bg-sidebar-accent"
                        )}
                      >
                        <div className="flex items-center gap-1 w-full">
                          {/* Contenido principal - se trunca */}
                          <div className="flex-1 min-w-0">
                            {isEditing ? (
                              <div className="flex items-center gap-1">
                                <Input
                                  value={editTitle}
                                  onChange={(e) => setEditTitle(e.target.value)}
                                  onKeyDown={(e) => {
                                    if (e.key === 'Enter') {
                                      handleRenameConversation(conv.id, editTitle);
                                      setEditingId(null);
                                    } else if (e.key === 'Escape') {
                                      setEditingId(null);
                                    }
                                  }}
                                  className="h-6 text-sm py-0 px-1 w-full"
                                  autoFocus
                                  onClick={(e) => e.stopPropagation()}
                                />
                                <button
                                  className="h-6 w-6 flex items-center justify-center rounded text-green-500 hover:bg-green-500/20"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleRenameConversation(conv.id, editTitle);
                                    setEditingId(null);
                                  }}
                                >
                                  <Check className="h-3.5 w-3.5" />
                                </button>
                                <button
                                  className="h-6 w-6 flex items-center justify-center rounded text-red-500 hover:bg-red-500/20"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setEditingId(null);
                                  }}
                                >
                                  <X className="h-3.5 w-3.5" />
                                </button>
                              </div>
                            ) : (
                              <>
                                <div className="flex items-center gap-1 min-w-0">
                                  {(conv.pinned === true || conv.pinned === 1) && (
                                    <Pin className="h-3 w-3 text-amber-500 flex-shrink-0" />
                                  )}
                                  <span className="font-medium truncate">
                                    {conv.title || "Sin título"}
                                  </span>
                                </div>
                                <p className="text-xs text-muted-foreground">
                                  {conv.message_count} msgs
                                </p>
                              </>
                            )}
                          </div>
                          {/* Iconos de acciones - siempre visibles al hover */}
                          {!isEditing && (
                            <div className="flex items-center flex-shrink-0">
                              <button
                                className="h-6 w-6 flex items-center justify-center rounded opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-amber-500 transition-opacity"
                                onClick={(e) => handlePinConversation(conv.id, e)}
                                title={(conv.pinned === true || conv.pinned === 1) ? "Desfijar" : "Fijar"}
                              >
                                {(conv.pinned === true || conv.pinned === 1) ? (
                                  <PinOff className="h-3 w-3" />
                                ) : (
                                  <Pin className="h-3 w-3" />
                                )}
                              </button>
                              <button
                                className="h-6 w-6 flex items-center justify-center rounded opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-blue-500 transition-opacity"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setEditTitle(conv.title || "");
                                  setEditingId(conv.id);
                                }}
                                title="Renombrar"
                              >
                                <Pencil className="h-3 w-3" />
                              </button>
                              <button
                                className="h-6 w-6 flex items-center justify-center rounded opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive transition-opacity"
                                onClick={(e) => handleDeleteConversation(conv.id, e)}
                                title="Eliminar"
                              >
                                <Trash2 className="h-3 w-3" />
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </ScrollArea>

      {/* Footer */}
      <div className="p-4 border-t">
        <Button
          variant="ghost"
          className="w-full justify-start gap-2 text-muted-foreground"
          onClick={() => setConfigModalOpen(true)}
        >
          <Settings className="h-4 w-4" />
          Configuración
        </Button>
      </div>
    </div>
  );
}

// Utility function to group conversations by date (with pinned first)
function groupByDate(conversations: Conversation[]) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 24 * 60 * 60 * 1000);
  const lastWeek = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);

  const groups: Record<string, Conversation[]> = {
    '📌 Fijadas': [],
    'Hoy': [],
    'Ayer': [],
    'Esta semana': [],
    'Anteriores': [],
  };

  // Asegurar que es un array
  if (!Array.isArray(conversations)) {
    return groups;
  }

  conversations.forEach((conv) => {
    // Las fijadas van en su propio grupo (pinned puede ser 0/1 o boolean)
    const isPinned = conv.pinned === true || conv.pinned === 1 || conv.pinned === '1';
    if (isPinned) {
      groups['📌 Fijadas'].push(conv);
      return;
    }
    
    const date = new Date(conv.updated_at);
    
    if (date >= today) {
      groups['Hoy'].push(conv);
    } else if (date >= yesterday) {
      groups['Ayer'].push(conv);
    } else if (date >= lastWeek) {
      groups['Esta semana'].push(conv);
    } else {
      groups['Anteriores'].push(conv);
    }
  });

  // Filtrar grupos vacíos
  return Object.fromEntries(
    Object.entries(groups).filter(([_, convs]) => convs.length > 0)
  );
}
