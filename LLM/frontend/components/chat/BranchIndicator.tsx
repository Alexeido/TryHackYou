"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useChatStore, TreeNode } from "@/store/useStore";
import { setActiveLeaf, getConversationThread } from "@/services/api";
import { 
  GitBranch, 
  ChevronLeft, 
  ChevronRight,
  MessageSquare,
  Loader2
} from "lucide-react";
import { cn } from "@/lib/utils";

interface BranchIndicatorProps {
  messageId: number;
  parentId: number | null;
}

export function BranchIndicator({ messageId, parentId }: BranchIndicatorProps) {
  const [isLoading, setIsLoading] = useState(false);
  const { 
    fullTree, 
    conversationId, 
    setMessages, 
    setActiveLeafId,
    activeLeafId 
  } = useChatStore();

  if (!fullTree || !parentId) return null;

  // Encontrar hermanos (nodos con el mismo parent_id)
  const siblings = fullTree.filter(n => n.parent_id === parentId);
  
  if (siblings.length <= 1) return null;

  const currentIndex = siblings.findIndex(n => n.id === messageId);
  const hasPrev = currentIndex > 0;
  const hasNext = currentIndex < siblings.length - 1;

  const switchToBranch = async (targetNode: TreeNode) => {
    if (!conversationId) return;
    
    setIsLoading(true);
    try {
      // Encontrar la hoja de esta rama
      let leafId = targetNode.id;
      let current = targetNode;
      
      // Navegar hasta la hoja más profunda de esta rama
      while (true) {
        const children = fullTree.filter(n => n.parent_id === current.id);
        if (children.length === 0) break;
        current = children[0]; // Tomar el primer hijo
        leafId = current.id;
      }
      
      // Cambiar active_leaf en el backend
      await setActiveLeaf(conversationId, leafId);
      
      // Recargar thread
      const thread = await getConversationThread(conversationId);
      setMessages(thread.messages);
      setActiveLeafId(thread.active_leaf_id);
    } catch (err) {
      console.error("Error switching branch:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const handlePrev = () => {
    if (hasPrev) {
      switchToBranch(siblings[currentIndex - 1]);
    }
  };

  const handleNext = () => {
    if (hasNext) {
      switchToBranch(siblings[currentIndex + 1]);
    }
  };

  return (
    <div className="flex items-center gap-1">
      <Popover>
        <PopoverTrigger asChild>
          <Badge 
            variant="outline" 
            className="gap-1 cursor-pointer hover:bg-muted transition-colors"
          >
            {isLoading ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <GitBranch className="h-3 w-3" />
            )}
            {currentIndex + 1}/{siblings.length}
          </Badge>
        </PopoverTrigger>
        <PopoverContent className="w-64 p-2" align="start">
          <div className="space-y-2">
            <div className="text-xs font-medium text-muted-foreground px-2">
              Ramas disponibles
            </div>
            {siblings.map((node, idx) => (
              <button
                key={node.id}
                onClick={() => switchToBranch(node)}
                disabled={isLoading}
                className={cn(
                  "w-full text-left px-3 py-2 rounded-md text-sm transition-colors",
                  "hover:bg-muted",
                  node.id === messageId && "bg-primary/10 text-primary"
                )}
              >
                <div className="flex items-center gap-2">
                  <MessageSquare className="h-3 w-3 shrink-0" />
                  <span className="flex-1 truncate">
                    {node.content_preview || `Rama ${idx + 1}`}
                  </span>
                  {node.id === messageId && (
                    <Badge variant="secondary" className="text-xs">
                      Actual
                    </Badge>
                  )}
                </div>
              </button>
            ))}
          </div>
        </PopoverContent>
      </Popover>

      {/* Navegación rápida */}
      <div className="flex items-center">
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          onClick={handlePrev}
          disabled={!hasPrev || isLoading}
        >
          <ChevronLeft className="h-3 w-3" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          onClick={handleNext}
          disabled={!hasNext || isLoading}
        >
          <ChevronRight className="h-3 w-3" />
        </Button>
      </div>
    </div>
  );
}
