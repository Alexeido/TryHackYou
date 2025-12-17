import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// Definimos qué forma tienen nuestros datos
interface AppState {
  // Configuración de UI
  isSidebarOpen: boolean;
  isTerminalOpen: boolean;
  toggleSidebar: () => void;
  toggleTerminal: () => void;
  setTerminalOpen: (open: boolean) => void;

  // API Keys (Se guardan en LocalStorage)
  apiKeys: {
    openai: string;
    google: string;
    deepseek: string;
    openrouter: string;
  };
  setApiKey: (provider: 'openai' | 'google' | 'deepseek' | 'openrouter', key: string) => void;
  
  // Configuración del Modelo
  selectedProvider: string;
  selectedModelId: string;
  setModel: (provider: string, modelId: string) => void;
  
  // System Prompt
  systemPrompt: string;
  setSystemPrompt: (prompt: string) => void;
}

export const useStore = create<AppState>()(
  persist(
    (set) => ({
      // Valores iniciales
      isSidebarOpen: true,
      isTerminalOpen: false, // Empieza cerrado
      
      apiKeys: {
        openai: '',
        google: '',
        deepseek: '',
        openrouter: '',
      },

      selectedProvider: 'google', // Default
      selectedModelId: 'gemini-1.5-flash', // Default
      
      systemPrompt: "Eres un experto en Ciberseguridad ofensiva y defensiva. Ayuda al usuario con escaneos, análisis de logs y scripts de pentesting ético.",

      // Acciones (Funciones para cambiar los datos)
      toggleSidebar: () => set((state) => ({ isSidebarOpen: !state.isSidebarOpen })),
      toggleTerminal: () => set((state) => ({ isTerminalOpen: !state.isTerminalOpen })),
      setTerminalOpen: (open) => set({ isTerminalOpen: open }),
      
      setApiKey: (provider, key) => set((state) => ({
        apiKeys: { ...state.apiKeys, [provider]: key }
      })),

      setModel: (provider, modelId) => set({ selectedProvider: provider, selectedModelId: modelId }),
      setSystemPrompt: (prompt) => set({ systemPrompt: prompt }),
    }),
    {
      name: 'cerebro-storage', // Nombre clave en LocalStorage
      partialize: (state) => ({ 
        // Solo guardamos esto en el disco duro del navegador
        apiKeys: state.apiKeys, 
        systemPrompt: state.systemPrompt,
        selectedProvider: state.selectedProvider,
        selectedModelId: state.selectedModelId
      }), 
    }
  )
);