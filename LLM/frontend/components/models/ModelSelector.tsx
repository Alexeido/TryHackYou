"use client";

import { useState, useEffect, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { 
  useModelsStore, 
  useConfigStore, 
  useUIStore,
  Model,
  Provider,
  BackendSorting,
} from "@/store/useStore";
import { discoverModels, getOllamaModels } from "@/services/api";
import { 
  ChevronDown, 
  Star, 
  Search, 
  Loader2,
  Sparkles,
  Brain,
  Globe,
  Bot,
  RefreshCw,
  ArrowUpDown,
  Layers,
  Fish,
  Gift,
  Lock,
  Settings2,
  Server
} from "lucide-react";
import { cn } from "@/lib/utils";

// 🐟 DeepSeek usa un icono de pez (animal marino)
// 🦙 Ollama usa un icono de servidor (local)
const PROVIDER_INFO: Record<Provider, { name: string; icon: React.ReactNode; color: string }> = {
  openai: { name: 'OpenAI', icon: <Bot className="h-4 w-4" />, color: 'text-emerald-500' },
  google: { name: 'Google', icon: <Sparkles className="h-4 w-4" />, color: 'text-blue-500' },
  anthropic: { name: 'Anthropic', icon: <Brain className="h-4 w-4" />, color: 'text-orange-500' },
  deepseek: { name: 'DeepSeek', icon: <Fish className="h-4 w-4" />, color: 'text-cyan-500' },
  openrouter: { name: 'OpenRouter', icon: <Globe className="h-4 w-4" />, color: 'text-pink-500' },
  ollama: { name: 'Ollama', icon: <Server className="h-4 w-4" />, color: 'text-purple-500' },
};

const SORT_OPTIONS: { value: BackendSorting; label: string }[] = [
  { value: 'ranking', label: 'ELO (mejor primero)' },
  { value: 'context', label: 'Contexto (mayor)' },
  { value: 'default', label: 'Por defecto' },
];

// Función de búsqueda tolerante a espacios
function fuzzyMatch(text: string, query: string): boolean {
  if (!query) return true;
  
  const normalizedText = text.toLowerCase().trim();
  const normalizedQuery = query.toLowerCase().trim();
  const queryNoSpaces = normalizedQuery.replace(/\s+/g, '');
  const queryWithDashes = normalizedQuery.replace(/\s+/g, '-');
  
  // Match directo
  if (normalizedText.includes(normalizedQuery)) return true;
  if (normalizedText.includes(queryNoSpaces)) return true;
  if (normalizedText.includes(queryWithDashes)) return true;
  
  // Match por palabras
  const queryWords = normalizedQuery.split(/\s+/).filter(w => w.length > 0);
  return queryWords.every(word => 
    normalizedText.includes(word) || 
    normalizedText.replace(/-/g, '').includes(word)
  );
}

export function ModelSelector() {
  const { 
    models, 
    selectedModel, 
    favorites, 
    isLoadingModels,
    filters,
    modelsUsingDefaults,
    setModels, 
    setSelectedModel, 
    toggleFavorite,
    setLoadingModels,
    setSorting,
    setGroupBy,
    setOnlyFree,
    toggleModelDefaults
  } = useModelsStore();
  
  const { apiKeys } = useConfigStore();
  const { isModelSelectorOpen, setModelSelectorOpen } = useUIStore();
  
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState<string>("all");

  // Cargar modelos - usa los filtros del backend
  const loadModels = async () => {
    setLoadingModels(true);
    try {
      const request: Parameters<typeof discoverModels>[0] = {
        sorting: filters.sorting,
        openrouter_free: filters.onlyFree,
        group: false,
        snapshots: false,
      };
      
      if (apiKeys.openai) request.openai_key = apiKeys.openai;
      if (apiKeys.google) request.gemini_key = apiKeys.google;
      if (apiKeys.anthropic) request.anthropic_key = apiKeys.anthropic;
      if (apiKeys.deepseek) request.deepseek_key = apiKeys.deepseek;
      if (apiKeys.openrouter) request.openrouter_key = apiKeys.openrouter;
      
      // Verificar si hay API keys (excepto ollama que usa URL)
      const hasApiKeys = Object.entries(apiKeys)
        .filter(([key]) => key !== 'ollama')
        .some(([, value]) => value && value.length > 5);
      const hasOllama = apiKeys.ollama && apiKeys.ollama.length > 5;
      
      if (!hasApiKeys && !hasOllama) {
        setModels([]);
        return;
      }
      
      let loadedModels: Model[] = [];
      
      // Cargar modelos de APIs cloud
      if (hasApiKeys) {
        const result = await discoverModels(request);
        loadedModels = result.models.map(m => ({
          id: m.id,
          name: m.name,
          provider: m.provider as Provider,
          elo_score: m.elo_score,
          context_window: m.context_window,
          pricing_input: m.pricing_input,
          pricing_output: m.pricing_output,
          isFavorite: favorites.includes(m.id),
        }));
      }
      
      // Cargar modelos de Ollama si hay URL configurada
      if (hasOllama) {
        try {
          const ollamaResult = await getOllamaModels(apiKeys.ollama);
          if (ollamaResult.connected && ollamaResult.models) {
            const ollamaModels: Model[] = ollamaResult.models.map(m => ({
              id: m.model,
              name: m.name,
              provider: 'ollama' as Provider,
              elo_score: undefined,
              context_window: undefined,
              pricing_input: 0,
              pricing_output: 0,
              isFavorite: favorites.includes(m.model),
            }));
            loadedModels = [...loadedModels, ...ollamaModels];
          }
        } catch (err) {
          console.error("Error loading Ollama models:", err);
        }
      }
      
      setModels(loadedModels);
      
      // Si no hay modelo seleccionado, seleccionar el primero con mejor ELO
      if (!selectedModel && loadedModels.length > 0) {
        setSelectedModel(loadedModels[0]);
      }
    } catch (err) {
      console.error("Error loading models:", err);
    } finally {
      setLoadingModels(false);
    }
  };

  // Cargar al montar
  useEffect(() => {
    loadModels();
  }, []);

  // Recargar cuando cambian los filtros del backend
  useEffect(() => {
    if (models.length > 0) {
      loadModels();
    }
  }, [filters.sorting, filters.onlyFree]);

  // Recargar cuando se abre el modal
  useEffect(() => {
    if (isModelSelectorOpen) {
      loadModels();
    }
  }, [isModelSelectorOpen]);

  // Modelos favoritos
  const favoriteModels = useMemo(() => 
    models.filter(m => favorites.includes(m.id)),
    [models, favorites]
  );

  // Filtrar modelos localmente (búsqueda y tabs)
  const filteredModels = useMemo(() => {
    let result = models;
    
    // Filtrar por proveedor/favoritos
    if (activeTab !== "all" && activeTab !== "favorites") {
      result = result.filter(m => m.provider === activeTab);
    } else if (activeTab === "favorites") {
      result = result.filter(m => favorites.includes(m.id));
    }
    
    // Búsqueda local
    if (searchQuery) {
      result = result.filter(m => 
        fuzzyMatch(m.name, searchQuery) || 
        fuzzyMatch(m.id, searchQuery) ||
        fuzzyMatch(m.provider, searchQuery)
      );
    }
    
    return result;
  }, [models, activeTab, searchQuery, favorites]);

  // Agrupar modelos por proveedor
  const groupedModels = useMemo(() => {
    if (filters.groupBy === 'none') return null;
    
    const groups: Record<Provider, Model[]> = {
      openai: [],
      google: [],
      anthropic: [],
      deepseek: [],
      openrouter: [],
      ollama: [],
    };
    
    filteredModels.forEach(m => {
      groups[m.provider].push(m);
    });
    
    return Object.entries(groups)
      .filter(([, models]) => models.length > 0)
      .map(([provider, models]) => ({
        provider: provider as Provider,
        models,
      }));
  }, [filteredModels, filters.groupBy]);

  // Providers disponibles
  const availableProviders = useMemo(() => 
    [...new Set(models.map(m => m.provider))],
    [models]
  );

  const handleSelectModel = (model: Model) => {
    setSelectedModel(model);
    setModelSelectorOpen(false);
  };

  // Determinar si el modelo es gratis
  const isModelFree = (model: Model) => {
    return model.pricing_input === 0 && model.pricing_output === 0;
  };

  const renderModelCard = (model: Model) => {
    const usesDefaults = modelsUsingDefaults.includes(model.id);
    
    return (
      <div
        key={model.id}
        role="button"
        tabIndex={0}
        onClick={() => handleSelectModel(model)}
        onKeyDown={(e) => e.key === 'Enter' && handleSelectModel(model)}
        className={cn(
          "w-full text-left p-3 rounded-lg border transition-all cursor-pointer",
          "hover:bg-muted/50 hover:border-primary/50",
          selectedModel?.id === model.id && "border-primary bg-primary/5"
        )}
      >
        <div className="flex items-center gap-3">
          <div className={cn(
            "w-10 h-10 rounded-lg flex items-center justify-center",
            "bg-muted"
          )}>
            <span className={PROVIDER_INFO[model.provider]?.color}>
              {PROVIDER_INFO[model.provider]?.icon}
            </span>
          </div>
          
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-medium truncate">
                {model.name}
              </span>
              {model.elo_score > 0 && (
                <Badge variant="outline" className="shrink-0">
                  ELO: {model.elo_score}
                </Badge>
              )}
              {isModelFree(model) && model.provider === 'openrouter' && (
                <Badge variant="secondary" className="shrink-0 text-xs bg-green-500/20 text-green-500">
                  <Gift className="h-3 w-3 mr-1" />
                  Gratis
                </Badge>
              )}
              {/* Badge de modo por defecto */}
              {usesDefaults && (
                <Badge variant="secondary" className="shrink-0 text-xs bg-amber-500/20 text-amber-600 dark:text-amber-400">
                  <Lock className="h-3 w-3 mr-1" />
                  Default
                </Badge>
              )}
            </div>
            <p className="text-sm text-muted-foreground truncate">
              {model.id}
            </p>
          </div>
          
          {/* Toggle para usar defaults */}
          <Button
            variant="ghost"
            size="icon"
            className={cn(
              "shrink-0",
              usesDefaults ? "text-amber-500" : "text-muted-foreground"
            )}
            onClick={(e) => {
              e.stopPropagation();
              toggleModelDefaults(model.id);
            }}
            title={usesDefaults ? "Usar parámetros avanzados" : "Usar valores por defecto"}
          >
            {usesDefaults ? (
              <Lock className="h-4 w-4" />
            ) : (
              <Settings2 className="h-4 w-4" />
            )}
          </Button>
          
          <Button
            variant="ghost"
            size="icon"
            className="shrink-0"
            onClick={(e) => {
              e.stopPropagation();
              toggleFavorite(model.id);
            }}
          >
            <Star className={cn(
              "h-4 w-4",
              favorites.includes(model.id) 
                ? "fill-yellow-500 text-yellow-500" 
                : "text-muted-foreground"
            )} />
          </Button>
        </div>
        
        {/* Solo mostrar info adicional si hay datos válidos */}
        {((model.context_window ?? 0) > 0 || (model.pricing_input !== undefined && model.pricing_input > 0)) && (
          <div className="mt-2 flex items-center gap-4 text-xs text-muted-foreground">
            {(model.context_window ?? 0) > 0 && (
              <span>Contexto: {((model.context_window ?? 0) / 1000).toFixed(0)}K tokens</span>
            )}
            {model.pricing_input !== undefined && model.pricing_input > 0 && (
              <span>${model.pricing_input.toFixed(2)}/1M in</span>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <>
      {/* Dropdown simple */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button 
            variant="outline" 
            className="gap-2 min-w-[180px] justify-between"
            disabled={isLoadingModels}
          >
            {isLoadingModels ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Cargando...
              </>
            ) : selectedModel ? (
              <>
                <span className={PROVIDER_INFO[selectedModel.provider]?.color}>
                  {PROVIDER_INFO[selectedModel.provider]?.icon}
                </span>
                <span className="truncate flex-1 text-left">
                  {selectedModel.name}
                </span>
              </>
            ) : (
              <span className="text-muted-foreground">Seleccionar modelo</span>
            )}
            <ChevronDown className="h-4 w-4 shrink-0 opacity-50" />
          </Button>
        </DropdownMenuTrigger>
        
        <DropdownMenuContent align="start" className="w-[280px]">
          {favoriteModels.length > 0 && (
            <>
              <DropdownMenuLabel className="flex items-center gap-2">
                <Star className="h-3 w-3 fill-yellow-500 text-yellow-500" />
                Favoritos
              </DropdownMenuLabel>
              {favoriteModels.slice(0, 5).map(model => (
                <DropdownMenuItem 
                  key={model.id}
                  onClick={() => handleSelectModel(model)}
                  className="gap-2"
                >
                  <span className={PROVIDER_INFO[model.provider]?.color}>
                    {PROVIDER_INFO[model.provider]?.icon}
                  </span>
                  <span className="flex-1 truncate">{model.name}</span>
                  {model.elo_score > 0 && (
                    <Badge variant="secondary" className="text-xs">
                      {model.elo_score}
                    </Badge>
                  )}
                </DropdownMenuItem>
              ))}
              <DropdownMenuSeparator />
            </>
          )}
          
          <DropdownMenuLabel>Top modelos</DropdownMenuLabel>
          {models.slice(0, 5).map(model => (
            <DropdownMenuItem 
              key={model.id}
              onClick={() => handleSelectModel(model)}
              className="gap-2"
            >
              <span className={PROVIDER_INFO[model.provider]?.color}>
                {PROVIDER_INFO[model.provider]?.icon}
              </span>
              <span className="flex-1 truncate">{model.name}</span>
            </DropdownMenuItem>
          ))}
          
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => setModelSelectorOpen(true)}>
            <Search className="h-4 w-4 mr-2" />
            Ver todos los modelos...
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Modal completo */}
      <Dialog open={isModelSelectorOpen} onOpenChange={setModelSelectorOpen}>
        <DialogContent className="min-w-[48rem] max-w-[90vw] w-fit h-[80vh] flex flex-col">
          <DialogHeader className="shrink-0">
            <DialogTitle className="flex items-center justify-between">
              <span>Seleccionar Modelo ({models.length})</span>
              <Button 
                variant="ghost" 
                size="sm"
                onClick={loadModels}
                disabled={isLoadingModels}
              >
                <RefreshCw className={cn(
                  "h-4 w-4 mr-2",
                  isLoadingModels && "animate-spin"
                )} />
                Actualizar
              </Button>
            </DialogTitle>
          </DialogHeader>

          {/* Search + Filters */}
          <div className="flex gap-2 shrink-0 flex-wrap">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Buscar modelos... (ej: gemini 2.5)"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            
            {/* Sort dropdown - usa backend */}
            <Select value={filters.sorting} onValueChange={(v: BackendSorting) => setSorting(v)}>
              <SelectTrigger className="w-[160px]">
                <ArrowUpDown className="h-4 w-4 mr-2" />
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SORT_OPTIONS.map(opt => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            
            {/* Group toggle */}
            <Button
              variant={filters.groupBy === 'provider' ? 'default' : 'outline'}
              size="icon"
              onClick={() => setGroupBy(filters.groupBy === 'none' ? 'provider' : 'none')}
              title={filters.groupBy === 'provider' ? 'Desagrupar' : 'Agrupar por proveedor'}
            >
              <Layers className="h-4 w-4" />
            </Button>
          </div>

          {/* Only Free toggle */}
          <div className="flex items-center gap-2 shrink-0">
            <Switch
              id="only-free"
              checked={filters.onlyFree}
              onCheckedChange={setOnlyFree}
            />
            <Label htmlFor="only-free" className="text-sm cursor-pointer flex items-center gap-2">
              <Gift className="h-4 w-4 text-green-500" />
              Solo modelos gratis (OpenRouter)
            </Label>
          </div>

          {/* Tabs por proveedor */}
          <div className="flex-1 flex flex-col min-h-0 mt-2">
            <div className="flex gap-2 flex-wrap shrink-0 pb-4 border-b">
              <Button
                variant={activeTab === "all" ? "default" : "outline"}
                size="sm"
                onClick={() => setActiveTab("all")}
                className="gap-1"
              >
                Todos
                <Badge variant="secondary" className="ml-1">
                  {filteredModels.length}
                </Badge>
              </Button>
              <Button
                variant={activeTab === "favorites" ? "default" : "outline"}
                size="sm"
                onClick={() => setActiveTab("favorites")}
                className="gap-1"
              >
                <Star className="h-3 w-3" />
                Favoritos
              </Button>
              {availableProviders.map(provider => (
                <Button
                  key={provider}
                  variant={activeTab === provider ? "default" : "outline"}
                  size="sm"
                  onClick={() => setActiveTab(provider)}
                  className="gap-1"
                >
                  <span className={PROVIDER_INFO[provider]?.color}>
                    {PROVIDER_INFO[provider]?.icon}
                  </span>
                  {PROVIDER_INFO[provider]?.name}
                </Button>
              ))}
            </div>

            <div className="flex-1 overflow-y-auto mt-4">
              {isLoadingModels ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
              ) : filteredModels.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground">
                  <Search className="h-8 w-8 mx-auto mb-2 opacity-50" />
                  <p>No se encontraron modelos</p>
                  {activeTab === "favorites" && (
                    <p className="text-sm mt-1">
                      Marca modelos como favoritos con la estrella
                    </p>
                  )}
                </div>
              ) : filters.groupBy === 'provider' && groupedModels ? (
                // Vista agrupada
                <div className="space-y-6">
                  {groupedModels.map(group => (
                    <div key={group.provider}>
                      <div className="flex items-center gap-2 mb-3 sticky top-0 bg-background py-2">
                        <span className={PROVIDER_INFO[group.provider]?.color}>
                          {PROVIDER_INFO[group.provider]?.icon}
                        </span>
                        <span className="font-semibold">
                          {PROVIDER_INFO[group.provider]?.name}
                        </span>
                        <Badge variant="secondary" className="text-xs">
                          {group.models.length}
                        </Badge>
                      </div>
                      <div className="grid gap-2">
                        {group.models.map(renderModelCard)}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                // Vista plana
                <div className="grid gap-2">
                  {filteredModels.map(renderModelCard)}
                </div>
              )}
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
