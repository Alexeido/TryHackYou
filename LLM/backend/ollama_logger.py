"""
ollama_logger.py - Sistema de logging de tokens para modelos Ollama.

Registra el consumo de tokens por conversación en un archivo CSV
para facilitar el benchmarking de modelos locales vs APIs en la nube.

Formato CSV:
- Cada fila es un registro de tokens para una petición
- Columnas: conversation_id, timestamp, model, prompt_tokens, completion_tokens, 
            total_tokens, cumulative_prompt, cumulative_completion, cumulative_total

Activar/desactivar con OLLAMA_TOKEN_LOGGING_ENABLED.
"""

import os
import csv
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from threading import Lock

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

# Flag para activar/desactivar el logging (cambiar a True para activar)
OLLAMA_TOKEN_LOGGING_ENABLED = False

# Directorio donde se guardan los logs
LOGS_DIR = Path(__file__).parent / "ollama_logs"

# Nombre del archivo CSV
CSV_FILENAME = "ollama_tokens.csv"

# Lock para escritura thread-safe
_csv_lock = Lock()

# Cache de tokens acumulados por conversación (en memoria)
_conversation_totals: Dict[str, Dict[str, int]] = {}


# =============================================================================
# FUNCIONES PRINCIPALES
# =============================================================================

def is_logging_enabled() -> bool:
    """Retorna si el logging de tokens está habilitado."""
    return OLLAMA_TOKEN_LOGGING_ENABLED


def enable_logging():
    """Activa el logging de tokens."""
    global OLLAMA_TOKEN_LOGGING_ENABLED
    OLLAMA_TOKEN_LOGGING_ENABLED = True
    print("📊 Ollama token logging: ACTIVADO")


def disable_logging():
    """Desactiva el logging de tokens."""
    global OLLAMA_TOKEN_LOGGING_ENABLED
    OLLAMA_TOKEN_LOGGING_ENABLED = False
    print("📊 Ollama token logging: DESACTIVADO")


def _ensure_csv_exists():
    """Crea el directorio y archivo CSV si no existen."""
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        print(f"📊 Directorio creado/verificado: {LOGS_DIR}")
        
        csv_path = LOGS_DIR / CSV_FILENAME
        
        if not csv_path.exists():
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'conversation_id',
                    'timestamp',
                    'model',
                    'prompt_tokens',
                    'completion_tokens', 
                    'total_tokens',
                    'cumulative_prompt',
                    'cumulative_completion',
                    'cumulative_total'
                ])
            print(f"📊 Creado archivo de log: {csv_path}")
        else:
            print(f"📊 Archivo CSV ya existe: {csv_path}")
    except Exception as e:
        print(f"❌ Error creando CSV: {e}")


def log_ollama_tokens(
    conversation_id: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: Optional[int] = None
) -> None:
    """
    Registra el consumo de tokens de una petición Ollama.
    
    Args:
        conversation_id: ID de la conversación
        model: Nombre del modelo Ollama usado
        prompt_tokens: Tokens de entrada (prompt)
        completion_tokens: Tokens de salida (completion)
        total_tokens: Total de tokens (opcional, se calcula si no se provee)
    """
    if not OLLAMA_TOKEN_LOGGING_ENABLED:
        return
    
    if total_tokens is None:
        total_tokens = prompt_tokens + completion_tokens
    
    timestamp = datetime.now().isoformat()
    
    # Actualizar totales acumulados
    if conversation_id not in _conversation_totals:
        _conversation_totals[conversation_id] = {
            'prompt': 0,
            'completion': 0,
            'total': 0
        }
    
    _conversation_totals[conversation_id]['prompt'] += prompt_tokens
    _conversation_totals[conversation_id]['completion'] += completion_tokens
    _conversation_totals[conversation_id]['total'] += total_tokens
    
    cumulative = _conversation_totals[conversation_id]
    
    # Escribir al CSV
    with _csv_lock:
        _ensure_csv_exists()
        csv_path = LOGS_DIR / CSV_FILENAME
        
        with open(csv_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                conversation_id,
                timestamp,
                model,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                cumulative['prompt'],
                cumulative['completion'],
                cumulative['total']
            ])
    
    print(f"📊 Ollama tokens logged: conv={conversation_id[:8]}... "
          f"prompt={prompt_tokens}, completion={completion_tokens}, "
          f"cumulative_total={cumulative['total']}")


def get_conversation_totals(conversation_id: str) -> Dict[str, int]:
    """
    Obtiene los totales acumulados para una conversación.
    
    Returns:
        Dict con 'prompt', 'completion', 'total' acumulados
    """
    return _conversation_totals.get(conversation_id, {
        'prompt': 0,
        'completion': 0,
        'total': 0
    })


def get_all_conversations_summary() -> Dict[str, Dict[str, Any]]:
    """
    Retorna un resumen de todas las conversaciones registradas.
    
    Returns:
        Dict con conversation_id como clave y totales como valor
    """
    return dict(_conversation_totals)


def reset_conversation_totals(conversation_id: Optional[str] = None):
    """
    Resetea los totales acumulados en memoria.
    
    Args:
        conversation_id: Si se provee, resetea solo esa conversación.
                        Si es None, resetea todas.
    """
    global _conversation_totals
    
    if conversation_id:
        _conversation_totals.pop(conversation_id, None)
        print(f"📊 Reseteados totales para conversación: {conversation_id[:8]}...")
    else:
        _conversation_totals = {}
        print("📊 Reseteados todos los totales de conversación")


def get_csv_path() -> Path:
    """Retorna la ruta al archivo CSV de logs."""
    return LOGS_DIR / CSV_FILENAME


def read_csv_as_dict() -> list:
    """
    Lee el CSV completo y lo retorna como lista de diccionarios.
    Útil para análisis o exportación.
    """
    csv_path = LOGS_DIR / CSV_FILENAME
    
    if not csv_path.exists():
        return []
    
    with open(csv_path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader)


# =============================================================================
# FUNCIONES DE UTILIDAD PARA EXTRACCIÓN DE TOKENS
# =============================================================================

def extract_usage_from_chunk(chunk: Any) -> Optional[Dict[str, int]]:
    """
    Extrae información de usage de un chunk de streaming.
    
    Ollama (via OpenAI compatible API) puede enviar usage en:
    - chunk.usage (último chunk del stream)
    - chunk.x_groq (para Groq)
    
    Args:
        chunk: Chunk del stream de OpenAI/Ollama
        
    Returns:
        Dict con prompt_tokens, completion_tokens, total_tokens o None
    """
    usage = None
    
    # Intentar obtener usage directamente
    if hasattr(chunk, 'usage') and chunk.usage is not None:
        usage = chunk.usage
    
    # Algunos modelos lo envían en el campo x_groq
    if usage is None and hasattr(chunk, 'x_groq') and chunk.x_groq:
        if hasattr(chunk.x_groq, 'usage'):
            usage = chunk.x_groq.usage
    
    if usage is None:
        return None
    
    # Extraer valores
    result = {}
    
    if hasattr(usage, 'prompt_tokens'):
        result['prompt_tokens'] = usage.prompt_tokens or 0
    elif isinstance(usage, dict):
        result['prompt_tokens'] = usage.get('prompt_tokens', 0)
    
    if hasattr(usage, 'completion_tokens'):
        result['completion_tokens'] = usage.completion_tokens or 0
    elif isinstance(usage, dict):
        result['completion_tokens'] = usage.get('completion_tokens', 0)
    
    if hasattr(usage, 'total_tokens'):
        result['total_tokens'] = usage.total_tokens or 0
    elif isinstance(usage, dict):
        result['total_tokens'] = usage.get('total_tokens', 0)
    
    # Solo retornar si tenemos al menos algún dato
    if result.get('prompt_tokens') or result.get('completion_tokens'):
        return result
    
    return None


def extract_usage_from_response(response: Any) -> Optional[Dict[str, int]]:
    """
    Extrae información de usage de una respuesta completa (no-streaming).
    
    Args:
        response: Respuesta completa de OpenAI/Ollama
        
    Returns:
        Dict con prompt_tokens, completion_tokens, total_tokens o None
    """
    return extract_usage_from_chunk(response)  # Misma lógica aplica


def estimate_tokens_from_text(text: str) -> int:
    """
    Estimación mejorada de tokens basada en longitud de texto.
    Usa heurísticas más precisas para diferentes tipos de contenido.
    
    Args:
        text: Texto para estimar
        
    Returns:
        Número estimado de tokens
    """
    if not text:
        return 0
    
    text = str(text).strip()
    if not text:
        return 0
    
    # Contar palabras y caracteres especiales
    words = len(text.split())
    chars = len(text)
    
    # Heurística mejorada:
    # - Inglés/Español promedio: ~3.5-4 caracteres por token
    # - JSON/código: más tokens por carácter
    # - Texto natural: menos tokens por carácter
    
    # Detectar tipo de contenido
    json_indicators = text.count('{') + text.count('[') + text.count('"')
    code_indicators = text.count('=') + text.count(';') + text.count('function')
    
    if json_indicators > chars * 0.05:  # Más del 5% son caracteres JSON
        # JSON: ~2.5-3 chars por token
        estimated = max(1, int(chars / 2.8))
    elif code_indicators > chars * 0.02:  # Código
        # Código: ~3 chars por token
        estimated = max(1, int(chars / 3.2))
    else:
        # Texto natural: ~4 chars por token, pero mínimo basado en palabras
        char_based = max(1, int(chars / 4.0))
        word_based = max(1, int(words * 1.3))  # ~1.3 tokens por palabra
        estimated = max(char_based, word_based)
    
    return estimated


def log_ollama_tokens_with_estimation(
    conversation_id: str,
    model: str,
    prompt_text: str = "",
    completion_text: str = "",
    actual_usage: Optional[Dict[str, int]] = None
) -> None:
    """
    Registra tokens de Ollama con fallback a estimación si no hay usage real.
    
    Args:
        conversation_id: ID de la conversación
        model: Modelo Ollama
        prompt_text: Texto del prompt (para estimar si no hay usage)
        completion_text: Texto de la completion (para estimar si no hay usage)
        actual_usage: Usage real si está disponible
    """
    if not OLLAMA_TOKEN_LOGGING_ENABLED:
        return
    
    if actual_usage:
        # Usar datos reales
        log_ollama_tokens(
            conversation_id=conversation_id,
            model=model,
            prompt_tokens=actual_usage.get('prompt_tokens', 0),
            completion_tokens=actual_usage.get('completion_tokens', 0),
            total_tokens=actual_usage.get('total_tokens')
        )
        print(f"📊 Tokens registrados (real usage)")
    else:
        # Fallback a estimación
        estimated_prompt = estimate_tokens_from_text(prompt_text)
        estimated_completion = estimate_tokens_from_text(completion_text)
        
        log_ollama_tokens(
            conversation_id=conversation_id,
            model=model,
            prompt_tokens=estimated_prompt,
            completion_tokens=estimated_completion
        )
        print(f"📊 Tokens registrados (estimados) - prompt: {estimated_prompt}, completion: {estimated_completion}, chars: {len(prompt_text + completion_text)}")
