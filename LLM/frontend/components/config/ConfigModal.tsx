"use client";

import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { 
  useConfigStore, 
  useUIStore, 
  useModelsStore,
  Provider 
} from "@/store/useStore";
import { validateApiKeys } from "@/services/api";
import { 
  Key, 
  Palette, 
  FileText, 
  Server,
  CheckCircle2, 
  XCircle, 
  Loader2,
  Eye,
  EyeOff,
  Shield,
  Sparkles
} from "lucide-react";
import { cn } from "@/lib/utils";

interface ProviderConfig {
  key: Provider;
  name: string;
  placeholder: string;
  apiKeyField: string;
  color: string;
  icon: string;
}

const PROVIDERS: ProviderConfig[] = [
  { 
    key: 'openai', 
    name: 'OpenAI', 
    placeholder: 'sk-...', 
    apiKeyField: 'openai_key',
    color: 'bg-emerald-500',
    icon: '🤖'
  },
  { 
    key: 'google', 
    name: 'Google Gemini', 
    placeholder: 'AIza...', 
    apiKeyField: 'gemini_key',
    color: 'bg-blue-500',
    icon: '💎'
  },
  { 
    key: 'anthropic', 
    name: 'Anthropic', 
    placeholder: 'sk-ant-...', 
    apiKeyField: 'anthropic_key',
    color: 'bg-orange-500',
    icon: '🧠'
  },
  { 
    key: 'deepseek', 
    name: 'DeepSeek', 
    placeholder: 'sk-...', 
    apiKeyField: 'deepseek_key',
    color: 'bg-purple-500',
    icon: '🔮'
  },
  { 
    key: 'openrouter', 
    name: 'OpenRouter', 
    placeholder: 'sk-or-...', 
    apiKeyField: 'openrouter_key',
    color: 'bg-pink-500',
    icon: '🌐'
  },
];

export function ConfigModal() {
  const { isConfigModalOpen, setConfigModalOpen } = useUIStore();
  const { 
    apiKeys, 
    setApiKey, 
    keyValidation, 
    setKeyValidation,
    theme, 
    setTheme, 
    systemPrompt, 
    setSystemPrompt,
    backendUrl,
    setBackendUrl
  } = useConfigStore();
  
  const { filters, setOnlyFree } = useModelsStore();
  
  const [showKeys, setShowKeys] = useState<Record<Provider, boolean>>({
    openai: false,
    google: false,
    anthropic: false,
    deepseek: false,
    openrouter: false,
  });
  
  const [isValidating, setIsValidating] = useState(false);
  const [localBackendUrl, setLocalBackendUrl] = useState(backendUrl);

  // Sincronizar URL local con store
  useEffect(() => {
    setLocalBackendUrl(backendUrl);
  }, [backendUrl]);

  const handleValidateKeys = async () => {
    setIsValidating(true);
    
    // Marcar todas las keys con contenido como "checking"
    PROVIDERS.forEach(provider => {
      if (apiKeys[provider.key]) {
        setKeyValidation(provider.key, { valid: false, error: null, checking: true });
      }
    });
    
    try {
      const keysToValidate: Record<string, string> = {};
      PROVIDERS.forEach(provider => {
        if (apiKeys[provider.key]) {
          keysToValidate[provider.apiKeyField] = apiKeys[provider.key];
        }
      });
      
      const results = await validateApiKeys(keysToValidate);
      
      // Actualizar resultados
      if (results.openai) {
        setKeyValidation('openai', { 
          valid: results.openai.valid, 
          error: results.openai.error, 
          checking: false 
        });
      }
      if (results.google) {
        setKeyValidation('google', { 
          valid: results.google.valid, 
          error: results.google.error, 
          checking: false 
        });
      }
      if (results.anthropic) {
        setKeyValidation('anthropic', { 
          valid: results.anthropic.valid, 
          error: results.anthropic.error, 
          checking: false 
        });
      }
      if (results.deepseek) {
        setKeyValidation('deepseek', { 
          valid: results.deepseek.valid, 
          error: results.deepseek.error, 
          checking: false 
        });
      }
      if (results.openrouter) {
        setKeyValidation('openrouter', { 
          valid: results.openrouter.valid, 
          error: results.openrouter.error, 
          checking: false 
        });
      }
    } catch {
      // Si falla la conexión, marcar todas como error
      PROVIDERS.forEach(provider => {
        if (apiKeys[provider.key]) {
          setKeyValidation(provider.key, { 
            valid: false, 
            error: 'No se pudo conectar al servidor', 
            checking: false 
          });
        }
      });
    } finally {
      setIsValidating(false);
    }
  };

  const getValidationBadge = (provider: Provider) => {
    const validation = keyValidation[provider];
    const hasKey = !!apiKeys[provider];
    
    if (!hasKey) return null;
    
    if (validation.checking) {
      return (
        <Badge variant="secondary" className="gap-1">
          <Loader2 className="h-3 w-3 animate-spin" />
          Verificando
        </Badge>
      );
    }
    
    if (validation.valid) {
      return (
        <Badge className="gap-1 bg-green-500/20 text-green-400 border-green-500/30">
          <CheckCircle2 className="h-3 w-3" />
          Válida
        </Badge>
      );
    }
    
    if (validation.error) {
      return (
        <Badge variant="destructive" className="gap-1">
          <XCircle className="h-3 w-3" />
          Inválida
        </Badge>
      );
    }
    
    return (
      <Badge variant="outline" className="gap-1 text-muted-foreground">
        Sin verificar
      </Badge>
    );
  };

  const toggleShowKey = (provider: Provider) => {
    setShowKeys(prev => ({ ...prev, [provider]: !prev[provider] }));
  };

  // Aplicar tema
  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
    } else if (theme === 'light') {
      root.classList.remove('dark');
    } else {
      // System preference
      if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
        root.classList.add('dark');
      } else {
        root.classList.remove('dark');
      }
    }
  }, [theme]);

  return (
    <Dialog open={isConfigModalOpen} onOpenChange={setConfigModalOpen}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-hidden flex flex-col">
        <DialogHeader className="pb-2">
          <DialogTitle className="flex items-center gap-2 text-xl">
            <Sparkles className="h-5 w-5 text-primary" />
            Configuración
          </DialogTitle>
        </DialogHeader>
        
        <Tabs defaultValue="keys" className="flex-1 overflow-hidden flex flex-col">
          <TabsList className="grid w-full grid-cols-4 mb-4">
            <TabsTrigger value="keys" className="gap-2">
              <Key className="h-4 w-4" />
              <span className="hidden sm:inline">API Keys</span>
            </TabsTrigger>
            <TabsTrigger value="appearance" className="gap-2">
              <Palette className="h-4 w-4" />
              <span className="hidden sm:inline">Apariencia</span>
            </TabsTrigger>
            <TabsTrigger value="instructions" className="gap-2">
              <FileText className="h-4 w-4" />
              <span className="hidden sm:inline">Instrucciones</span>
            </TabsTrigger>
            <TabsTrigger value="server" className="gap-2">
              <Server className="h-4 w-4" />
              <span className="hidden sm:inline">Servidor</span>
            </TabsTrigger>
          </TabsList>
          
          {/* API Keys Tab */}
          <TabsContent value="keys" className="flex-1 overflow-auto space-y-4 pr-2">
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                Introduce tus API keys para conectar con los proveedores de LLM.
                Las keys se guardan localmente en tu navegador.
              </p>
              <Button 
                onClick={handleValidateKeys} 
                disabled={isValidating}
                size="sm"
                className="shrink-0 ml-4"
              >
                {isValidating ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Validando...
                  </>
                ) : (
                  <>
                    <Shield className="h-4 w-4 mr-2" />
                    Validar Keys
                  </>
                )}
              </Button>
            </div>
            
            <div className="space-y-3">
              {PROVIDERS.map((provider) => (
                <div 
                  key={provider.key}
                  className="p-4 rounded-lg border bg-card/50 space-y-3"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className={cn(
                        "w-8 h-8 rounded-lg flex items-center justify-center text-lg",
                        provider.color + "/20"
                      )}>
                        {provider.icon}
                      </div>
                      <div>
                        <Label className="font-medium">{provider.name}</Label>
                      </div>
                    </div>
                    {getValidationBadge(provider.key)}
                  </div>
                  
                  <div className="relative">
                    <Input
                      type={showKeys[provider.key] ? "text" : "password"}
                      placeholder={provider.placeholder}
                      value={apiKeys[provider.key]}
                      onChange={(e) => setApiKey(provider.key, e.target.value)}
                      className="pr-10 font-mono text-sm"
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="absolute right-0 top-0 h-full px-3 hover:bg-transparent"
                      onClick={() => toggleShowKey(provider.key)}
                    >
                      {showKeys[provider.key] ? (
                        <EyeOff className="h-4 w-4 text-muted-foreground" />
                      ) : (
                        <Eye className="h-4 w-4 text-muted-foreground" />
                      )}
                    </Button>
                  </div>
                  
                  {keyValidation[provider.key].error && (
                    <p className="text-xs text-destructive">
                      {keyValidation[provider.key].error}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </TabsContent>
          
          {/* Appearance Tab */}
          <TabsContent value="appearance" className="space-y-6">
            <div className="space-y-4">
              <div>
                <Label className="text-base font-medium">Tema</Label>
                <p className="text-sm text-muted-foreground mb-4">
                  Selecciona el tema de la interfaz
                </p>
              </div>
              
              <div className="grid grid-cols-3 gap-4">
                {(['light', 'dark', 'system'] as const).map((t) => (
                  <button
                    key={t}
                    onClick={() => setTheme(t)}
                    className={cn(
                      "p-4 rounded-lg border-2 transition-all",
                      theme === t 
                        ? "border-primary bg-primary/5" 
                        : "border-transparent bg-muted/50 hover:bg-muted"
                    )}
                  >
                    <div className="text-center">
                      <div className="text-2xl mb-2">
                        {t === 'light' ? '☀️' : t === 'dark' ? '🌙' : '💻'}
                      </div>
                      <span className="text-sm font-medium capitalize">{t}</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Opciones de modelos */}
            <div className="space-y-4 pt-4 border-t">
              <div>
                <Label className="text-base font-medium">Selector de Modelos</Label>
                <p className="text-sm text-muted-foreground mb-4">
                  Configura cómo se muestran los modelos disponibles
                </p>
              </div>
              
              <div className="flex items-center justify-between p-4 rounded-lg bg-muted/50 border">
                <div className="space-y-0.5">
                  <Label className="font-medium">Mostrar solo modelos gratis</Label>
                  <p className="text-sm text-muted-foreground">
                    Filtra OpenRouter para mostrar solo modelos con precio $0
                  </p>
                </div>
                <Switch
                  checked={filters.onlyFree}
                  onCheckedChange={setOnlyFree}
                />
              </div>
            </div>
          </TabsContent>
          
          {/* Instructions Tab */}
          <TabsContent value="instructions" className="space-y-4">
            <div>
              <Label className="text-base font-medium">System Prompt</Label>
              <p className="text-sm text-muted-foreground mb-4">
                Define las instrucciones base que recibirá el asistente en cada conversación.
              </p>
            </div>
            
            <Textarea
              placeholder="Ej: Eres un experto en ciberseguridad..."
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              className="min-h-[200px] font-mono text-sm"
            />
            
            <div className="flex items-center justify-between text-sm text-muted-foreground">
              <span>{systemPrompt.length} caracteres</span>
              <Button 
                variant="outline" 
                size="sm"
                onClick={() => setSystemPrompt("Eres un experto en Ciberseguridad ofensiva y defensiva. Ayuda al usuario con escaneos, análisis de logs y scripts de pentesting ético. Responde siempre en español.")}
              >
                Restaurar predeterminado
              </Button>
            </div>
          </TabsContent>
          
          {/* Server Tab */}
          <TabsContent value="server" className="space-y-4">
            <div>
              <Label className="text-base font-medium">URL del Backend</Label>
              <p className="text-sm text-muted-foreground mb-4">
                Dirección del servidor backend. Solo cambiar si tienes una instalación personalizada.
              </p>
            </div>
            
            <div className="flex gap-2">
              <Input
                placeholder="http://localhost:8000"
                value={localBackendUrl}
                onChange={(e) => setLocalBackendUrl(e.target.value)}
                className="font-mono text-sm"
              />
              <Button 
                onClick={() => setBackendUrl(localBackendUrl)}
                disabled={localBackendUrl === backendUrl}
              >
                Guardar
              </Button>
            </div>
            
            <div className="p-4 rounded-lg bg-muted/50 border">
              <div className="flex items-center gap-2 mb-2">
                <Server className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm font-medium">Estado del servidor</span>
              </div>
              <p className="text-sm text-muted-foreground">
                Usa el botón &quot;Validar Keys&quot; en la pestaña de API Keys para verificar la conexión.
              </p>
            </div>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
