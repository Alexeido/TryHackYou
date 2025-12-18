"use client";

import { useEffect, useCallback } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
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
  deleteConversation 
} from "@/services/api";
import { 
  Plus, 
  MessageSquare, 
  Trash2, 
  Settings,
  Loader2,
  ChevronLeft,
  Search
} from "lucide-react";
import { cn } from "@/lib/utils";
import { formatDistanceToNow } from "@/lib/dateUtils";

export function ChatSidebar() {
  const { 
    conversations, 
    isLoading, 
    setConversations, 
    setLoading,
    removeConversation 
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

  // Agrupar por fecha
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
            🧠 Cerebro
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
                  {convs.map((conv) => (
                    <div
                      key={conv.id}
                      onClick={() => handleSelectConversation(conv.id)}
                      className={cn(
                        "w-full text-left px-3 py-2.5 rounded-lg text-sm group transition-colors cursor-pointer",
                        "hover:bg-sidebar-accent",
                        conv.id === conversationId && "bg-sidebar-accent"
                      )}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1 min-w-0">
                          <p className="font-medium truncate">
                            {conv.title || "Sin título"}
                          </p>
                          <p className="text-xs text-muted-foreground mt-0.5">
                            {conv.message_count} mensajes
                          </p>
                        </div>
                        <button
                          className="h-7 w-7 flex items-center justify-center rounded-md opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive hover:bg-muted shrink-0 transition-all"
                          onClick={(e) => handleDeleteConversation(conv.id, e)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  ))}
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

// Utility function to group conversations by date
function groupByDate(conversations: Conversation[]) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 24 * 60 * 60 * 1000);
  const lastWeek = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);

  const groups: Record<string, Conversation[]> = {
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
