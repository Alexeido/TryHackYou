"""
models.py - Modelos Pydantic para todas las rutas.

Centraliza todos los modelos de request/response para mantener main.py limpio.
"""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime


# =============================================================================
# HEALTH CHECK
# =============================================================================

class KeysValidationRequest(BaseModel):
    """Request para validar API keys."""
    openai_key: Optional[str] = None
    gemini_key: Optional[str] = None
    anthropic_key: Optional[str] = None
    deepseek_key: Optional[str] = None
    openrouter_key: Optional[str] = None
    ollama_url: Optional[str] = None  # URL del servidor Ollama


class KeyValidationResult(BaseModel):
    """Resultado de validación de una key."""
    valid: bool
    error: Optional[str] = None


class KeysValidationResponse(BaseModel):
    """Response de validación de todas las keys."""
    openai: Optional[KeyValidationResult] = None
    google: Optional[KeyValidationResult] = None
    anthropic: Optional[KeyValidationResult] = None
    deepseek: Optional[KeyValidationResult] = None
    openrouter: Optional[KeyValidationResult] = None
    ollama: Optional[KeyValidationResult] = None


class HealthResponse(BaseModel):
    """Response del health check básico."""
    status: str
    version: str
    database: str
    timestamp: str


# =============================================================================
# MODELS DISCOVERY (Ya existente, lo movemos aquí)
# =============================================================================

class DiscoveryRequest(BaseModel):
    """Request para descubrir modelos disponibles."""
    openai_key: Optional[str] = None
    gemini_key: Optional[str] = None
    anthropic_key: Optional[str] = None
    deepseek_key: Optional[str] = None
    openrouter_key: Optional[str] = None
    
    sorting: Literal["default", "ranking", "context"] = "default"
    group: bool = Field(default=False, description="Agrupar visualmente por proveedor")
    snapshots: bool = Field(default=False, description="Mostrar versiones antiguas/fechadas")
    openrouter_free: bool = Field(default=False, description="Mostrar solo modelos gratuitos")


class ModelInfo(BaseModel):
    """Información de un modelo."""
    id: str
    provider: str
    name: str
    elo_score: int = 0
    context_window: Optional[int] = 0
    pricing_input: Optional[float] = 0.0
    pricing_output: Optional[float] = 0.0
    details: Dict[str, Any] = {}


class DiscoveryResponse(BaseModel):
    """Response con lista de modelos."""
    total: int
    models: List[ModelInfo]


# =============================================================================
# CONVERSATIONS
# =============================================================================

class ConversationCreate(BaseModel):
    """Request para crear una conversación."""
    title: Optional[str] = "Nueva conversación"
    system_prompt: Optional[str] = None


class ConversationResponse(BaseModel):
    """Response de una conversación."""
    id: str
    title: str
    system_message_id: Optional[int] = None
    created_at: str
    updated_at: Optional[str] = None


class ConversationListItem(BaseModel):
    """Item en la lista de conversaciones."""
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int
    pinned: bool = False


class ConversationListResponse(BaseModel):
    """Response de lista de conversaciones."""
    total: int
    conversations: List[ConversationListItem]


class ActiveLeafUpdate(BaseModel):
    """Request para cambiar la rama activa."""
    leaf_id: int


# =============================================================================
# MESSAGES
# =============================================================================

class MessageResponse(BaseModel):
    """Response de un mensaje."""
    id: int
    conversation_id: str
    parent_id: Optional[int]
    role: str
    content: Optional[str]
    tool_calls: Optional[str]  # JSON string
    tool_call_id: Optional[str]
    model_used: Optional[str]
    created_at: str


class ThreadResponse(BaseModel):
    """Response del thread (rama activa)."""
    conversation_id: str
    messages: List[MessageResponse]


class TreeNode(BaseModel):
    """Nodo del árbol de mensajes."""
    id: int
    parent_id: Optional[int]
    role: str
    content_preview: Optional[str]
    children_count: int


class TreeResponse(BaseModel):
    """Response del árbol completo."""
    nodes: List[TreeNode]
    active_leaf: Optional[int]


class MessageEdit(BaseModel):
    """Request para editar un mensaje."""
    content: str
    create_branch: bool = True  # Si True, crea nueva rama; si False, edita in-place


class MessageEditResponse(BaseModel):
    """Response de edición de mensaje."""
    message_id: int
    conversation_id: str
    is_new_branch: bool
    parent_id: Optional[int]


# =============================================================================
# CHAT
# =============================================================================

class ChatMessage(BaseModel):
    """Mensaje individual para el chat."""
    role: str
    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None


class ChatRequest(BaseModel):
    """Request para el endpoint de chat."""
    # Autenticación y modelo
    provider: Literal["openai", "google", "deepseek", "openrouter", "anthropic", "ollama"]
    api_key: str
    model_id: str
    
    # Contexto de conversación
    conversation_id: Optional[str] = None  # Si None, crea nueva
    parent_message_id: Optional[int] = None  # Mensaje padre en árbol
    
    # Mensaje del usuario
    user_message: str
    
    # Regeneración
    regenerate: bool = False  # Si True, no crea nuevo mensaje de usuario
    
    # Parámetros avanzados opcionales (None = usar default del proveedor)
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None
    
    # Configuración
    tools: Optional[List[Dict[str, Any]]] = None
    stream: bool = False  # Parámetro clave para streaming
    system_prompt: Optional[str] = None  # Override system prompt para nueva conv


class ChatResponse(BaseModel):
    """Response del chat (modo normal, sin streaming)."""
    conversation_id: str
    user_message_id: int
    assistant_message_id: int
    role: str
    content: Optional[str]
    tool_calls: Optional[List[Dict[str, Any]]]
    finish_reason: str


# =============================================================================
# ERRORES
# =============================================================================

class ErrorResponse(BaseModel):
    """Response de error estandarizado."""
    error: bool = True
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


# Códigos de error
ERROR_CODES = {
    "INVALID_API_KEY": "La API Key proporcionada es inválida",
    "RATE_LIMITED": "Has excedido el límite de peticiones",
    "MODEL_NOT_FOUND": "El modelo solicitado no existe",
    "CONVERSATION_NOT_FOUND": "La conversación no existe",
    "MESSAGE_NOT_FOUND": "El mensaje no existe",
    "PROVIDER_ERROR": "Error del proveedor de LLM",
    "NETWORK_ERROR": "Error de conexión con el proveedor",
    "DATABASE_ERROR": "Error en la base de datos",
    "INTERNAL_ERROR": "Error interno del servidor",
    "STREAM_ERROR": "Error durante el streaming"
}
