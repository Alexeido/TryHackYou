"use client";

import { useState, useEffect } from "react";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
import { useUIStore, useMissionStore } from "@/store/useStore";
import { ChatSidebar } from "@/components/sidebar/ChatSidebar";
import { ChatArea } from "@/components/chat/ChatArea";
import { TerminalPanel } from "@/components/terminal/TerminalPanel";
import { ConfigModal } from "@/components/config/ConfigModal";
import { ModelSelector } from "@/components/models/ModelSelector";
import { MissionPanel, ApprovalDialog } from "@/components/mission";
import { Button } from "@/components/ui/button";
import { Settings, PanelRight, Target, Loader2 } from "lucide-react";

export function MainLayout() {
  const [isMounted, setIsMounted] = useState(false);
  const { 
    isTerminalOpen, 
    setTerminalOpen,
    isSidebarOpen,
    setConfigModalOpen 
  } = useUIStore();
  
  const { isPanelOpen, setPanelOpen } = useMissionStore();

  // Evitar errores de hidratación esperando al cliente
  useEffect(() => {
    setIsMounted(true);
  }, []);

  // Loading state mientras se monta en el cliente
  if (!isMounted) {
    return (
      <div className="h-screen w-full bg-background flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <span className="text-sm text-muted-foreground">Cargando...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen w-full bg-background text-foreground overflow-hidden">
      <ResizablePanelGroup direction="horizontal">
        
        {/* COLUMNA IZQUIERDA: SIDEBAR */}
        <ResizablePanel 
          defaultSize={isSidebarOpen ? 20 : 4} 
          minSize={isSidebarOpen ? 15 : 4} 
          maxSize={isSidebarOpen ? 30 : 4}
          className="hidden md:block"
        >
          <ChatSidebar />
        </ResizablePanel>
        
        <ResizableHandle className="hidden md:flex" />

        {/* COLUMNA CENTRAL: CHAT */}
        <ResizablePanel defaultSize={isTerminalOpen ? 55 : 76}>
          <div className="h-full flex flex-col">
            {/* Header del chat */}
            <div className="h-14 border-b flex items-center justify-between px-4 bg-background/80 backdrop-blur-sm">
              <div className="flex items-center gap-4">
                <ModelSelector />
              </div>
              
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setPanelOpen(!isPanelOpen)}
                  className="text-muted-foreground"
                  title="Panel de misión"
                >
                  <Target className="h-5 w-5" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setTerminalOpen(!isTerminalOpen)}
                  className="text-muted-foreground"
                >
                  <PanelRight className="h-5 w-5" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setConfigModalOpen(true)}
                  className="text-muted-foreground"
                >
                  <Settings className="h-5 w-5" />
                </Button>
              </div>
            </div>
            
            {/* Área de chat */}
            <div className="flex-1 overflow-hidden flex">
              <div className="flex-1">
                <ChatArea />
              </div>
              {/* Panel de misión (lado derecho del chat) */}
              {isPanelOpen && (
                <div className="w-80 border-l overflow-hidden">
                  <MissionPanel />
                </div>
              )}
            </div>
          </div>
        </ResizablePanel>

        {/* COLUMNA DERECHA: TERMINAL (Condicional) */}
        {isTerminalOpen && (
          <>
            <ResizableHandle />
            <ResizablePanel defaultSize={25} minSize={20} maxSize={40}>
              <TerminalPanel onClose={() => setTerminalOpen(false)} />
            </ResizablePanel>
          </>
        )}
      </ResizablePanelGroup>

      {/* Modales */}
      <ConfigModal />
      <ApprovalDialog />
    </div>
  );
}