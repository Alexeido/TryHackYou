"""
database.py - Gestión de SQLite con sistema de árbol de mensajes.

Estructura:
- conversations: Metadatos de cada chat
- messages: Árbol de mensajes con parent_id para ramificaciones
"""

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from contextlib import contextmanager

# Ruta de la base de datos
DB_PATH = Path(__file__).parent / "chat_history.db"


def init_db():
    """
    Inicializa la base de datos con las tablas necesarias.
    Se llama al arrancar el servidor.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Tabla de conversaciones
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL DEFAULT 'Nueva conversación',
            system_prompt TEXT,
            active_leaf_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Tabla de mensajes con estructura de árbol
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            parent_id INTEGER,
            role TEXT NOT NULL CHECK(role IN ('system', 'user', 'assistant', 'tool')),
            content TEXT,
            tool_calls TEXT,
            tool_call_id TEXT,
            model_used TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
            FOREIGN KEY (parent_id) REFERENCES messages(id) ON DELETE SET NULL
        )
    """)
    
    # Índices para optimizar queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_parent ON messages(parent_id)")
    
    conn.commit()
    conn.close()
    print("✅ Base de datos inicializada correctamente")


@contextmanager
def get_db():
    """
    Context manager para conexión a BD.
    Uso: with get_db() as conn: ...
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Permite acceso por nombre de columna
    conn.execute("PRAGMA foreign_keys = ON")  # Activar foreign keys
    try:
        yield conn
    finally:
        conn.close()


def generate_id() -> str:
    """Genera un ID único para conversaciones."""
    return f"conv_{uuid.uuid4().hex[:12]}"


# =============================================================================
# CRUD DE CONVERSACIONES
# =============================================================================

def create_conversation(title: str = "Nueva conversación", system_prompt: Optional[str] = None) -> Dict[str, Any]:
    """
    Crea una nueva conversación con su system prompt como mensaje raíz.
    
    Returns:
        Dict con id, title, system_message_id, created_at
    """
    conv_id = generate_id()
    now = datetime.utcnow().isoformat()
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # 1. Crear conversación
        cursor.execute("""
            INSERT INTO conversations (id, title, system_prompt, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (conv_id, title, system_prompt, now, now))
        
        # 2. Crear mensaje raíz (system prompt)
        system_content = system_prompt or "Eres un asistente de ciberseguridad experto."
        cursor.execute("""
            INSERT INTO messages (conversation_id, parent_id, role, content, created_at)
            VALUES (?, NULL, 'system', ?, ?)
        """, (conv_id, system_content, now))
        
        system_msg_id = cursor.lastrowid
        
        # 3. Actualizar active_leaf_id
        cursor.execute("""
            UPDATE conversations SET active_leaf_id = ? WHERE id = ?
        """, (system_msg_id, conv_id))
        
        conn.commit()
        
        return {
            "id": conv_id,
            "title": title,
            "system_message_id": system_msg_id,
            "created_at": now
        }


def list_conversations(limit: int = 50, offset: int = 0) -> Dict[str, Any]:
    """
    Lista todas las conversaciones ordenadas por updated_at descendente.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Contar total
        cursor.execute("SELECT COUNT(*) FROM conversations")
        total = cursor.fetchone()[0]
        
        # Obtener conversaciones con conteo de mensajes
        cursor.execute("""
            SELECT c.id, c.title, c.created_at, c.updated_at,
                   COUNT(m.id) as message_count
            FROM conversations c
            LEFT JOIN messages m ON m.conversation_id = c.id
            GROUP BY c.id
            ORDER BY c.updated_at DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))
        
        conversations = [dict(row) for row in cursor.fetchall()]
        
        return {
            "total": total,
            "conversations": conversations
        }


def get_conversation(conv_id: str) -> Optional[Dict[str, Any]]:
    """Obtiene metadatos de una conversación."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, system_prompt, active_leaf_id, created_at, updated_at
            FROM conversations WHERE id = ?
        """, (conv_id,))
        
        row = cursor.fetchone()
        return dict(row) if row else None


def delete_conversation(conv_id: str) -> bool:
    """Elimina una conversación y todos sus mensajes (CASCADE)."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
        conn.commit()
        return cursor.rowcount > 0


def update_conversation_leaf(conv_id: str, leaf_id: int) -> bool:
    """Actualiza el active_leaf_id de una conversación."""
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE conversations 
            SET active_leaf_id = ?, updated_at = ?
            WHERE id = ?
        """, (leaf_id, now, conv_id))
        conn.commit()
        return cursor.rowcount > 0


def update_conversation_timestamp(conv_id: str):
    """Actualiza el updated_at de una conversación."""
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE conversations SET updated_at = ? WHERE id = ?
        """, (now, conv_id))
        conn.commit()


# =============================================================================
# CRUD DE MENSAJES (ÁRBOL)
# =============================================================================

def add_message(
    conversation_id: str,
    role: str,
    content: Optional[str] = None,
    parent_id: Optional[int] = None,
    tool_calls: Optional[str] = None,  # JSON string
    tool_call_id: Optional[str] = None,
    model_used: Optional[str] = None
) -> int:
    """
    Añade un mensaje al árbol.
    
    Args:
        conversation_id: ID de la conversación
        role: 'user', 'assistant', 'system', 'tool'
        content: Contenido del mensaje
        parent_id: ID del mensaje padre (None para system)
        tool_calls: JSON string de tool_calls (si assistant pide tools)
        tool_call_id: ID de la tool call (si role='tool')
        model_used: Modelo que generó la respuesta (para assistant)
    
    Returns:
        ID del mensaje creado
    """
    now = datetime.utcnow().isoformat()
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO messages (conversation_id, parent_id, role, content, 
                                  tool_calls, tool_call_id, model_used, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (conversation_id, parent_id, role, content, 
              tool_calls, tool_call_id, model_used, now))
        
        msg_id = cursor.lastrowid
        conn.commit()
        
        return msg_id


def get_message(message_id: int) -> Optional[Dict[str, Any]]:
    """Obtiene un mensaje por su ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, conversation_id, parent_id, role, content, 
                   tool_calls, tool_call_id, model_used, created_at
            FROM messages WHERE id = ?
        """, (message_id,))
        
        row = cursor.fetchone()
        return dict(row) if row else None


def reconstruct_thread(leaf_id: int) -> List[Dict[str, Any]]:
    """
    Reconstruye la rama desde un mensaje hoja hasta la raíz.
    
    Returns:
        Lista ordenada [system, msg1, msg2, ..., leaf]
    """
    thread = []
    current_id = leaf_id
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        while current_id is not None:
            cursor.execute("""
                SELECT id, conversation_id, parent_id, role, content, 
                       tool_calls, tool_call_id, model_used, created_at
                FROM messages WHERE id = ?
            """, (current_id,))
            
            row = cursor.fetchone()
            if not row:
                break
            
            msg = dict(row)
            thread.insert(0, msg)  # Insertar al principio
            current_id = msg['parent_id']
    
    return thread


def get_tree_structure(conversation_id: str) -> Dict[str, Any]:
    """
    Obtiene la estructura completa del árbol para mostrar ramificaciones en UI.
    
    Returns:
        {
            "nodes": [...],
            "active_leaf": int
        }
    """
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Obtener todos los nodos con conteo de hijos
        cursor.execute("""
            SELECT m.id, m.parent_id, m.role, m.content,
                   (SELECT COUNT(*) FROM messages c WHERE c.parent_id = m.id) as children_count
            FROM messages m
            WHERE m.conversation_id = ?
            ORDER BY m.created_at
        """, (conversation_id,))
        
        nodes = []
        for row in cursor.fetchall():
            node = dict(row)
            # Truncar content para no enviar todo el texto
            if node['content'] and len(node['content']) > 100:
                node['content_preview'] = node['content'][:100] + "..."
            else:
                node['content_preview'] = node['content']
            del node['content']  # No enviar content completo en tree view
            nodes.append(node)
        
        # Obtener active_leaf
        cursor.execute("SELECT active_leaf_id FROM conversations WHERE id = ?", (conversation_id,))
        result = cursor.fetchone()
        active_leaf = result['active_leaf_id'] if result else None
        
        return {
            "nodes": nodes,
            "active_leaf": active_leaf
        }


def get_last_message_id(conversation_id: str) -> Optional[int]:
    """Obtiene el ID del último mensaje (active_leaf) de una conversación."""
    conv = get_conversation(conversation_id)
    return conv['active_leaf_id'] if conv else None


def delete_descendants(message_id: int):
    """
    Elimina todos los descendientes de un mensaje (para edición destructiva).
    """
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Obtener todos los descendientes recursivamente
        descendants = []
        to_check = [message_id]
        
        while to_check:
            current = to_check.pop()
            cursor.execute("SELECT id FROM messages WHERE parent_id = ?", (current,))
            children = [row['id'] for row in cursor.fetchall()]
            descendants.extend(children)
            to_check.extend(children)
        
        # Eliminar todos los descendientes
        if descendants:
            placeholders = ','.join('?' * len(descendants))
            cursor.execute(f"DELETE FROM messages WHERE id IN ({placeholders})", descendants)
            conn.commit()
        
        return len(descendants)


def update_message_content(message_id: int, new_content: str) -> bool:
    """Actualiza el contenido de un mensaje (edición in-place)."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE messages SET content = ? WHERE id = ?
        """, (new_content, message_id))
        conn.commit()
        return cursor.rowcount > 0


# =============================================================================
# UTILIDADES
# =============================================================================

def get_conversation_for_llm(leaf_id: int) -> List[Dict[str, str]]:
    """
    Reconstruye el historial en formato para enviar al LLM.
    Solo incluye role y content (formato OpenAI).
    """
    thread = reconstruct_thread(leaf_id)
    
    messages = []
    for msg in thread:
        message = {"role": msg['role'], "content": msg['content'] or ""}
        
        # Si tiene tool_calls, añadirlo
        if msg['tool_calls']:
            import json
            message['tool_calls'] = json.loads(msg['tool_calls'])
        
        # Si es respuesta de tool, añadir tool_call_id
        if msg['tool_call_id']:
            message['tool_call_id'] = msg['tool_call_id']
        
        messages.append(message)
    
    return messages
