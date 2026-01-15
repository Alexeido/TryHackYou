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
    
    # Tabla para trackear jobs en background pendientes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pending_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL UNIQUE,
            conversation_id TEXT NOT NULL,
            leaf_id INTEGER NOT NULL,
            command TEXT NOT NULL,
            tool_call_id TEXT,
            status TEXT DEFAULT 'running',
            result TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            completed_at DATETIME,
            notified INTEGER DEFAULT 0,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        )
    """)
    
    # Índices para optimizar queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_parent ON messages(parent_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pending_jobs_conv ON pending_jobs(conversation_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pending_jobs_status ON pending_jobs(status)")
    
    # Migración: añadir columna pinned si no existe
    cursor.execute("PRAGMA table_info(conversations)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'pinned' not in columns:
        cursor.execute("ALTER TABLE conversations ADD COLUMN pinned INTEGER DEFAULT 0")
        print("📌 Añadida columna 'pinned' a conversations")
    
    # Migración: añadir columna tool_call_id a pending_jobs si no existe
    cursor.execute("PRAGMA table_info(pending_jobs)")
    job_columns = [col[1] for col in cursor.fetchall()]
    if 'tool_call_id' not in job_columns:
        cursor.execute("ALTER TABLE pending_jobs ADD COLUMN tool_call_id TEXT")
        print("🔧 Añadida columna 'tool_call_id' a pending_jobs")
    
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
    Lista todas las conversaciones ordenadas por pinned (primero fijadas) y updated_at descendente.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Contar total
        cursor.execute("SELECT COUNT(*) FROM conversations")
        total = cursor.fetchone()[0]
        
        # Obtener conversaciones con conteo de mensajes
        # Ordenar: primero fijadas, luego por fecha
        cursor.execute("""
            SELECT c.id, c.title, c.created_at, c.updated_at,
                   COALESCE(c.pinned, 0) as pinned,
                   COUNT(m.id) as message_count
            FROM conversations c
            LEFT JOIN messages m ON m.conversation_id = c.id
            GROUP BY c.id
            ORDER BY c.pinned DESC, c.updated_at DESC
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


def toggle_conversation_pin(conv_id: str) -> bool:
    """Alterna el estado de fijado de una conversación. Devuelve el nuevo estado."""
    with get_db() as conn:
        cursor = conn.cursor()
        # Obtener estado actual
        cursor.execute("SELECT COALESCE(pinned, 0) FROM conversations WHERE id = ?", (conv_id,))
        row = cursor.fetchone()
        if not row:
            return False
        
        new_pinned = 0 if row[0] else 1
        cursor.execute("UPDATE conversations SET pinned = ? WHERE id = ?", (new_pinned, conv_id))
        conn.commit()
        return bool(new_pinned)


def rename_conversation(conv_id: str, new_title: str) -> bool:
    """Renombra una conversación."""
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?
        """, (new_title.strip(), now, conv_id))
        conn.commit()
        return cursor.rowcount > 0


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

# Configuración de límites para el contexto del LLM
MAX_MESSAGES_FOR_LLM = 30  # Máximo de mensajes a enviar al LLM
MAX_TOOL_RESPONSE_LENGTH = 2000  # Máximo de caracteres para respuestas de tools

def get_conversation_for_llm(leaf_id: int) -> List[Dict[str, str]]:
    """
    Reconstruye el historial en formato para enviar al LLM.
    Solo incluye role y content (formato OpenAI).
    
    OPTIMIZACIÓN: Limita el número de mensajes y trunca respuestas largas
    para evitar exceder límites de tokens.
    """
    thread = reconstruct_thread(leaf_id)
    
    messages = []
    for msg in thread:
        content = msg['content'] or ""
        
        # Truncar respuestas de tools que sean muy largas
        if msg['role'] == 'tool' and len(content) > MAX_TOOL_RESPONSE_LENGTH:
            content = content[:MAX_TOOL_RESPONSE_LENGTH] + f"\n\n[... truncado, {len(msg['content'])} chars total]"
        
        message = {"role": msg['role'], "content": content}
        
        # Si tiene tool_calls, añadirlo
        if msg['tool_calls']:
            import json
            message['tool_calls'] = json.loads(msg['tool_calls'])
        
        # Si es respuesta de tool, añadir tool_call_id
        if msg['tool_call_id']:
            message['tool_call_id'] = msg['tool_call_id']
        
        messages.append(message)
    
    # Limitar número de mensajes (mantener system prompt si existe + últimos N)
    if len(messages) > MAX_MESSAGES_FOR_LLM:
        # Preservar el system prompt si existe
        if messages and messages[0]['role'] == 'system':
            system_msg = [messages[0]]
            recent_msgs = messages[-(MAX_MESSAGES_FOR_LLM - 1):]
            messages = system_msg + recent_msgs
            print(f"⚠️ Contexto truncado: {len(thread)} msgs -> {len(messages)} msgs")
        else:
            messages = messages[-MAX_MESSAGES_FOR_LLM:]
            print(f"⚠️ Contexto truncado: {len(thread)} msgs -> {len(messages)} msgs")
    
    return messages


# =============================================================================
# PENDING JOBS (Background Jobs Tracking)
# =============================================================================

def add_pending_job(job_id: str, conversation_id: str, leaf_id: int, command: str, tool_call_id: str = None) -> int:
    """
    Registra un job que está ejecutándose en background.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO pending_jobs (job_id, conversation_id, leaf_id, command, tool_call_id)
            VALUES (?, ?, ?, ?, ?)
        """, (job_id, conversation_id, leaf_id, command, tool_call_id))
        conn.commit()
        return cursor.lastrowid


def get_pending_jobs(conversation_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Obtiene jobs pendientes (running) para una conversación o todos.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        if conversation_id:
            cursor.execute("""
                SELECT * FROM pending_jobs 
                WHERE conversation_id = ? AND status = 'running'
                ORDER BY created_at ASC
            """, (conversation_id,))
        else:
            cursor.execute("""
                SELECT * FROM pending_jobs 
                WHERE status = 'running'
                ORDER BY created_at ASC
            """)
        return [dict(row) for row in cursor.fetchall()]


def complete_pending_job(job_id: str, result: str) -> bool:
    """
    Marca un job como completado y guarda su resultado.
    """
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE pending_jobs 
            SET status = 'completed', result = ?, completed_at = ?
            WHERE job_id = ?
        """, (result, now, job_id))
        conn.commit()
        return cursor.rowcount > 0


def get_unnotified_completed_jobs(conversation_id: str, leaf_id: int) -> List[Dict[str, Any]]:
    """
    Obtiene jobs completados no notificados para una rama específica.
    Solo devuelve jobs que fueron lanzados en esa misma rama (leaf_id).
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM pending_jobs 
            WHERE conversation_id = ? AND leaf_id = ? AND status = 'completed' AND notified = 0
            ORDER BY completed_at ASC
        """, (conversation_id, leaf_id))
        return [dict(row) for row in cursor.fetchall()]


def mark_job_notified(job_id: str) -> bool:
    """
    Marca un job como notificado al LLM.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE pending_jobs SET notified = 1 WHERE job_id = ?
        """, (job_id,))
        conn.commit()
        return cursor.rowcount > 0


def delete_pending_job(job_id: str) -> bool:
    """
    Elimina un job de la tabla de pendientes.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM pending_jobs WHERE job_id = ?", (job_id,))
        conn.commit()
        return cursor.rowcount > 0
