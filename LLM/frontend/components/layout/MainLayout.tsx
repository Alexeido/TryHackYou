"use client";

import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
import { useState } from "react";
import { useStore } from "@/store/useStore";
import { TerminalSquare, MessageSquare } from "lucide-react";
import { cn } from "@/lib/utils";


// Placeholder components (luego los sustituiremos por los reales)
const Sidebar = () => <div className="p-4 bg-muted/20 h-full">Sidebar</div>;
const ChatArea = () => <div className="p-4 h-full flex items-center justify-center">Chat Area</div>;
const TerminalArea = () => <div className="p-4 bg-black text-green-500 h-full font-mono text-sm">Terminal Logs...</div>;

export function MainLayout() {
  const { isTerminalOpen, setTerminalOpen } = useStore();

  return (
    <div className="h-screen w-full bg-background text-foreground overflow-hidden">
      <ResizablePanelGroup direction="horizontal">
        
        {/* COLUMNA IZQUIERDA: SIDEBAR (20% por defecto) */}
        <ResizablePanel defaultSize={20} minSize={15} maxSize={30} className="hidden md:block">
          <Sidebar />
        </ResizablePanel>
        
        <ResizableHandle />

        {/* COLUMNA CENTRAL: CHAT */}
        <ResizablePanel defaultSize={isTerminalOpen ? 55 : 80}>
          <ChatArea />
        </ResizablePanel>

        {/* COLUMNA DERECHA: TERMINAL (Condicional) */}
        {isTerminalOpen && (
          <>
            <ResizableHandle />
            <ResizablePanel defaultSize={25} minSize={20} maxSize={40}>
               <div className="h-full flex flex-col">
                 <div className="h-8 bg-zinc-900 border-b border-zinc-800 flex items-center px-2 justify-between">
                   <span className="text-xs text-zinc-400 flex items-center gap-2">
                     <TerminalSquare size={14} /> Terminal Output
                   </span>
                   <button 
                    onClick={() => setTerminalOpen(false)} // Ahora usa la función del store
                    className="text-zinc-500 hover:text-white"
                  >
                    ×
                  </button>
                 </div>
                 <div className="flex-1 overflow-auto">
                    <TerminalArea />
                 </div>
               </div>
            </ResizablePanel>
          </>
        )}
      </ResizablePanelGroup>
    </div>
  );
}