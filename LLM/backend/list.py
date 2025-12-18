import re
from typing import List
# Asumimos que ModelInfo está definido en main o en un archivo types.py compartido. 
# Para simplificar, importaremos dinámicamente o trabajaremos con objetos.

def is_snapshot(model_id: str) -> bool:
    """
    Detecta si un modelo es una versión antigua/fija (snapshot).
    Ej: 'gpt-4-0613', 'claude-3-20240229' -> True
    Ej: 'gpt-4', 'claude-3-opus' -> False
    """
    # Patrones comunes de fechas o versiones numéricas largas
    patterns = [
        r"-\d{4}$",           # termina en -0613
        r"-\d{8}$",           # termina en -20240229
        r"-\d{4}-\d{2}-\d{2}" # contiene fecha completa
    ]
    for p in patterns:
        if re.search(p, model_id):
            return True
    return False

def process_models(
    models: List[any], 
    sort_by: str = "default", 
    group_by_provider: bool = False, 
    show_snapshots: bool = False,
    only_free: bool = False
) -> List[any]:
    """
    Aplica filtros y ordenación a la lista de modelos.
    """
    processed = []

    # --- 1. FILTRADO ---
    for m in models:
        # Filtro: OpenRouter Free (Precio Input y Output deben ser 0)
        if only_free:
            p_in = m.pricing_input or 0
            p_out = m.pricing_output or 0
            if p_in > 0 or p_out > 0:
                continue

        # Filtro: Snapshots (Versiones con fecha)
        if not show_snapshots:
            if is_snapshot(m.id):
                continue
        
        processed.append(m)

    # --- 2. ORDENACIÓN ---
    
    # Helper para obtener valor seguro
    def get_score(x): return x.elo_score or 0
    def get_context(x): return x.context_window or 0

    if sort_by == "ranking":
        # Ordenar por ELO Score (Mayor a menor)
        processed.sort(key=get_score, reverse=True)
    
    elif sort_by == "context":
        # Ordenar por Context Window (Mayor a menor)
        processed.sort(key=get_context, reverse=True)
        
    else: # "default"
        # Por defecto ordenamos alfabéticamente por nombre
        processed.sort(key=lambda x: x.name)

    # --- 3. AGRUPADO (Grouping) ---
    # Si group=True, forzamos que el criterio PRIMARIO sea el proveedor.
    # Esto mantiene el orden secundario (ranking/context) pero dentro de cada proveedor.
    if group_by_provider:
        processed.sort(key=lambda x: x.provider)

    return processed