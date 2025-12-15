

import os
import re
import requests
import pandas as pd
import io
from colorama import Fore
from thefuzz import process

# URL del CSV de fboulnois (actualizado periódicamente)
LMARENA_CSV_URL = "https://raw.githubusercontent.com/fboulnois/llm-leaderboard-csv/main/csv/lmarena_text.csv"


# ---------------------------------------------------------
# 1. FALLBACK (EL "INVENT" DE SEGURIDAD)
# ---------------------------------------------------------
# Se usa SOLO si falla la conexión a internet o GitHub se cae.
FALLBACK_SCORES = {
    "gpt-4o": 1287,
    "gemini-1.5-pro": 1261,
    "claude-3-5-sonnet": 1258,
    "gpt-4-turbo": 1255,
    "gpt-4": 1248,
    "claude-3-opus": 1246,
    "llama-3-70b": 1200,
    "deepseek-coder": 1230,
    "deepseek-chat": 1180,
    "mistral-large": 1159,
    "gpt-3.5-turbo": 1105,
    "gemini-flash": 1100,
}

# ---------------------------------------------------------
# 2. HERENCIA DE MODELOS NUEVOS (NO EN CSV)
# ---------------------------------------------------------
# Si un modelo nuevo no existe en el CSV, heredamos del "padre" + bonus
MODEL_INHERITANCE = {
    # OpenAI: modelos futuros heredan de gpt-4o
    r"gpt-5": ("ChatGPT-4o-latest (2025-03-26)", 100),
    r"gpt-6": ("ChatGPT-4o-latest (2025-03-26)", 200),
    r"o1-pro": ("o1-preview", 50),
    r"o4": ("o3-2025-04-16", 50),
    
    # Google: modelos futuros heredan de gemini-2.5-pro
    r"gemini-3": ("gemini-2.5-pro", 100),
    r"gemini-4": ("gemini-2.5-pro", 150),
    
    # Anthropic: modelos futuros heredan de claude-3.5-sonnet
    r"claude-4": ("claude-3.5-sonnet", 100),
    r"claude-5": ("claude-3.5-sonnet", 150),
    
    # DeepSeek: modelos futuros
    r"deepseek-v3": ("deepseek-chat", 50),
    r"deepseek-v4": ("deepseek-chat", 100),
}

# Variable global que guardará las notas
LIVE_SCORES = {}


def update_scores_from_internet():
    """Descarga el CSV de fboulnois/llm-leaderboard-csv y parsea los scores."""
    global LIVE_SCORES
    print(Fore.CYAN + "📡 Conectando con LMArena Leaderboard (fboulnois/llm-leaderboard-csv)...")

    try:
        response = requests.get(LMARENA_CSV_URL, timeout=15)
        
        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.text))
            
            # Columnas esperadas: "model" y "arena_score"
            col_model = next((c for c in df.columns if c.lower() == 'model'), None)
            col_score = next((c for c in df.columns if 'arena' in c.lower() and 'score' in c.lower()), None)
            
            if col_model and col_score:
                new_scores = {}
                for _, row in df.iterrows():
                    try:
                        name = str(row[col_model]).lower().strip()
                        score = int(float(row[col_score]))
                        new_scores[name] = score
                    except:
                        continue
                
                LIVE_SCORES = new_scores
                print(Fore.GREEN + f"✅ Base de datos actualizada: {len(LIVE_SCORES)} modelos cargados.")
            else:
                print(Fore.YELLOW + f"⚠️ No se encontraron columnas esperadas. Columnas: {list(df.columns)}")
                LIVE_SCORES = FALLBACK_SCORES
        else:
            print(Fore.RED + f"❌ Fallo HTTP ({response.status_code}): {response.reason}")
            LIVE_SCORES = FALLBACK_SCORES
    
    except Exception as e:
        print(Fore.RED + f"❌ Error de conexión: {e}")
        LIVE_SCORES = FALLBACK_SCORES


def _normalize_model_name(name: str) -> str:
    """Normaliza el nombre del modelo para comparaciones."""
    name = name.lower().strip()
    # Quitar prefijos de proveedor (openai/, google/, etc.)
    if "/" in name:
        name = name.split("/")[-1]
    # Quitar sufijos de fecha comunes (-20240620, -0613, etc.)
    name = re.sub(r'-\d{8}$', '', name)
    name = re.sub(r'-\d{4}$', '', name)
    return name


def _find_family_match(clean_name: str, db: dict) -> int | None:
    """
    Busca coincidencias por familia de modelo.
    Ej: 'gpt-3.5-turbo-instruct' -> busca 'gpt-3.5-turbo' en el CSV
    """
    # Extraer la familia base (ej: gpt-3.5-turbo, claude-3.5-sonnet)
    parts = clean_name.split('-')
    
    # Intentar con diferentes longitudes de prefijo
    for i in range(len(parts), 1, -1):
        prefix = '-'.join(parts[:i])
        
        # Buscar modelos que empiecen con este prefijo
        matches = [(k, v) for k, v in db.items() if k.startswith(prefix)]
        
        if matches:
            # Devolver la mejor nota de la familia (el más alto)
            best = max(matches, key=lambda x: x[1])
            return best[1]
    
    return None


def _check_inheritance(clean_name: str, db: dict) -> int | None:
    """
    Comprueba si el modelo es un "modelo futuro" y hereda nota del padre.
    Ej: gpt-5.2 -> hereda de gpt-4o + 100
    """
    for pattern, (parent, bonus) in MODEL_INHERITANCE.items():
        if re.search(pattern, clean_name):
            # Buscar el padre en la DB
            parent_score = db.get(parent.lower())
            if parent_score:
                return parent_score + bonus
            
            # Si el padre tampoco está, buscar por familia
            family_score = _find_family_match(parent.lower(), db)
            if family_score:
                return family_score + bonus
    
    return None


def assign_score(model_name: str) -> int:
    """
    Busca la nota del modelo con la siguiente prioridad:
    1. Match exacto
    2. Match exacto normalizado (sin fechas)
    3. Herencia de modelos nuevos (gpt-5 -> gpt-4o + 100)
    4. Match por familia (gpt-3.5-turbo-instruct -> gpt-3.5-turbo)
    5. Fuzzy match (umbral alto, >85%)
    6. Return 0 si no hay match
    """
    # Lazy loading
    if not LIVE_SCORES:
        update_scores_from_internet()
        
    db = LIVE_SCORES if LIVE_SCORES else FALLBACK_SCORES
    
    clean_name = _normalize_model_name(model_name)
    
    # 1. Match exacto
    if clean_name in db:
        return db[clean_name]
    
    # 2. Match exacto con nombre original (por si el CSV tiene fechas)
    original_lower = model_name.lower().split("/")[-1]
    if original_lower in db:
        return db[original_lower]
    
    # 3. Herencia de modelos nuevos (gpt-5, gemini-3, etc.)
    inherited = _check_inheritance(clean_name, db)
    if inherited:
        return inherited
    
    # 4. Match por familia
    family_score = _find_family_match(clean_name, db)
    if family_score:
        return family_score
    
    # 5. Fuzzy match (SOLO si hay alta confianza, >85%)
    if db:
        result = process.extractOne(clean_name, db.keys())
        if result:
            best_match, score_similarity = result
            if score_similarity > 85:
                return db[best_match]
    
    # 6. No encontrado
    return 0


# (Opcional) Si quieres que se actualice solo al importar el archivo:
# update_scores_from_internet()
