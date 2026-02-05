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
    
    # ==========================================================================
    # TABLAS PARA MODO AGÉNTICO (Sprint 1)
    # ==========================================================================
    
    # Tabla de misiones - Estado global de una tarea autónoma
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS missions (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            goal TEXT NOT NULL,
            current_phase TEXT,
            status TEXT DEFAULT 'PLANNING',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            completed_at DATETIME,
            metadata TEXT,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        )
    """)
    
    # Tabla de objetivos - Checklist de la misión
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS objectives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mission_id TEXT NOT NULL,
            order_index INTEGER NOT NULL,
            task TEXT NOT NULL,
            status TEXT DEFAULT 'PENDING',
            result_summary TEXT,
            reflection TEXT,
            requires_approval INTEGER DEFAULT 0,
            approval_status TEXT,
            pending_command TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            completed_at DATETIME,
            FOREIGN KEY (mission_id) REFERENCES missions(id) ON DELETE CASCADE
        )
    """)
    
    # Tabla de resúmenes de tools - Cache para optimización de contexto
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tool_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL,
            tool_call_id TEXT NOT NULL,
            original_output TEXT NOT NULL,
            original_length INTEGER NOT NULL,
            summary TEXT NOT NULL,
            compression_ratio REAL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
        )
    """)
    
    # Tabla de jobs de misión - Tracking de comandos en background
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mission_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            mission_id TEXT NOT NULL,
            objective_id INTEGER NOT NULL,
            command TEXT NOT NULL,
            status TEXT DEFAULT 'RUNNING',
            started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            completed_at DATETIME,
            FOREIGN KEY (mission_id) REFERENCES missions(id) ON DELETE CASCADE,
            FOREIGN KEY (objective_id) REFERENCES objectives(id) ON DELETE CASCADE
        )
    """)
    
    # Tabla de auditoría de comandos - Sprint 3: Security
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS command_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            mission_id TEXT,
            objective_id INTEGER,
            command TEXT NOT NULL,
            risk_level TEXT NOT NULL,
            requires_approval INTEGER DEFAULT 0,
            reason TEXT,
            status TEXT DEFAULT 'PENDING',
            result_summary TEXT,
            approved_by TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            executed_at DATETIME
        )
    """)
    
    # =========================================================================
    # TABLA: conversation_summaries - Sistema de Memoria Jerárquica (Cascading Context)
    # Permite almacenar resúmenes de bloques de mensajes en niveles de abstracción
    # L0 = Resumen de mensajes RAW, L1 = Resumen de resúmenes, etc.
    # =========================================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversation_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            start_message_id INTEGER NOT NULL,
            end_message_id INTEGER NOT NULL,
            summary_text TEXT NOT NULL,
            recursive_level INTEGER DEFAULT 0,
            token_count INTEGER,
            anchor_user_message_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        )
    """)
    
    # Índices para tablas agénticas
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_missions_conversation ON missions(conversation_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_missions_status ON missions(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_objectives_mission ON objectives(mission_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_objectives_status ON objectives(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tool_summaries_tool_call ON tool_summaries(tool_call_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_mission_jobs_mission ON mission_jobs(mission_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_command_audit_conversation ON command_audit(conversation_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_command_audit_status ON command_audit(status)")
    
    # Índices para memoria jerárquica
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_summaries_conversation ON conversation_summaries(conversation_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_summaries_range ON conversation_summaries(start_message_id, end_message_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_summaries_level ON conversation_summaries(recursive_level)")
    
    # =========================================================================
    # MIGRACIÓN: Añadir columna scratchpad a missions (si no existe)
    # =========================================================================
    try:
        cursor.execute("ALTER TABLE missions ADD COLUMN scratchpad TEXT")
        print("📝 Columna 'scratchpad' añadida a tabla missions")
    except sqlite3.OperationalError:
        # La columna ya existe, ignorar
        pass
    
    print("🎯 Tablas de modo agéntico inicializadas")
    
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
    """Elimina una conversación, todos sus mensajes (CASCADE) y resúmenes asociados."""
    with get_db() as conn:
        cursor = conn.cursor()
        # Eliminar resúmenes del sistema de memoria jerárquica
        cursor.execute("DELETE FROM conversation_summaries WHERE conversation_id = ?", (conv_id,))
        # Eliminar la conversación (mensajes se eliminan por CASCADE)
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


def find_and_update_awaiting_tool_message(conversation_id: str, objective_id: int, new_content: str) -> bool:
    """
    Busca el mensaje tool más reciente que contiene AWAITING_AUTHORIZATION
    para un objetivo específico y lo actualiza con el resultado real de la ejecución.
    
    Esto es necesario para que cuando el loop de chat se reanude después de
    una aprobación, el LLM reciba el resultado real del comando en lugar
    del mensaje de "esperando aprobación".
    
    Args:
        conversation_id: ID de la conversación
        objective_id: ID del objetivo que fue aprobado
        new_content: Nuevo contenido (resultado de la ejecución)
    
    Returns:
        True si se actualizó un mensaje, False si no se encontró
    """
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Buscar mensajes tool recientes de esta conversación que contengan AWAITING
        cursor.execute("""
            SELECT id, content FROM messages 
            WHERE conversation_id = ? 
            AND role = 'tool'
            AND content LIKE '%AWAITING_AUTHORIZATION%'
            ORDER BY created_at DESC
            LIMIT 10
        """, (conversation_id,))
        
        rows = cursor.fetchall()
        
        for row in rows:
            msg_id, content = row
            # Verificar si este mensaje corresponde al objetivo
            if content and (f'"objective_id": {objective_id}' in content or 
                           f'"objective_id":{objective_id}' in content or
                           'AWAITING_AUTHORIZATION' in content):
                # Actualizar este mensaje
                cursor.execute("""
                    UPDATE messages SET content = ? WHERE id = ?
                """, (new_content, msg_id))
                conn.commit()
                print(f"✅ Mensaje tool {msg_id} actualizado con resultado real")
                return True
        
        # Si no encontramos por objetivo_id, buscar el más reciente con AWAITING
        if rows:
            msg_id = rows[0][0]
            cursor.execute("""
                UPDATE messages SET content = ? WHERE id = ?
            """, (new_content, msg_id))
            conn.commit()
            print(f"✅ Mensaje tool {msg_id} (más reciente con AWAITING) actualizado")
            return True
        
        print(f"⚠️ No se encontró mensaje tool con AWAITING_AUTHORIZATION para objetivo {objective_id}")
        return False


# =============================================================================
# UTILIDADES
# =============================================================================

# Configuración de límites para el contexto del LLM
MAX_MESSAGES_FOR_LLM = 50  # Máximo de mensajes a enviar al LLM (mismo que loop agéntico)
MAX_TOOL_RESPONSE_LENGTH = 2000  # Máximo de caracteres para respuestas de tools

# Configuración para truncado inteligente agéntico
RECENT_MESSAGES_TO_KEEP = 35  # Mensajes recientes que se mantienen intactos (referencia)
SUMMARY_SLOT_COUNT = 0  # El resumen se inyecta en el system prompt, no usa slots extra

# =============================================================================
# SISTEMA DE MEMORIA JERÁRQUICA (Cascading Context)
# =============================================================================
# Cuando está habilitado, usa el LLM para generar resúmenes inteligentes de bloques
# de mensajes antiguos, almacenándolos en la BD para reutilización.
# Cuando está deshabilitado, usa el resumen basado en reglas (más rápido pero menos inteligente).
LLM_HIERARCHICAL_MEMORY_ENABLED = True  # Toggle principal del sistema

# Configuración de ventanas de memoria (% del contexto máximo)
MEMORY_WINDOW_ANCHOR_CRITICAL = 0.15   # 15% - System prompt + Scratchpad
MEMORY_WINDOW_RECENT = 0.35            # 35% - Últimos mensajes RAW
MEMORY_WINDOW_HISTORICAL = 0.50        # 50% - Resúmenes L2/L3 de la BD

# Threshold para activar resumen de un bloque (en caracteres)
BLOCK_SUMMARIZE_THRESHOLD = 1500  # Solo resumir bloques mayores a esto


def _generate_truncated_summary(truncated_messages: List[Dict]) -> str:
    """
    Genera un resumen compacto de los mensajes truncados.
    Este resumen se inyecta como mensaje de contexto para que el modelo
    no pierda el hilo de lo que ya hizo.
    """
    if not truncated_messages:
        return ""
    
    # Extraer información relevante de los mensajes truncados
    tool_calls_made = []
    key_findings = []
    commands_executed = []
    
    for msg in truncated_messages:
        role = msg.get('role')
        content = msg.get('content', '') or ''
        
        if role == 'assistant' and msg.get('tool_calls'):
            # Registrar qué tools se llamaron
            import json
            try:
                tcs = msg.get('tool_calls', [])
                if isinstance(tcs, str):
                    tcs = json.loads(tcs)
                for tc in tcs:
                    func_name = tc.get('function', {}).get('name', 'unknown')
                    args_str = tc.get('function', {}).get('arguments', '{}')
                    try:
                        args = json.loads(args_str)
                        if func_name == 'execute_command' and 'command' in args:
                            cmd = args['command'][:80]
                            commands_executed.append(cmd)
                        elif func_name == 'manage_mission':
                            action = args.get('action', '')
                            tool_calls_made.append(f"manage_mission({action})")
                    except:
                        tool_calls_made.append(func_name)
            except:
                pass
        
        elif role == 'tool':
            # Extraer hallazgos clave de respuestas de tools
            if content:
                # Buscar patrones importantes en la salida
                content_lower = content.lower()
                if any(kw in content_lower for kw in ['found', 'vulnerable', 'credential', 'password', 'token', 'success', 'open port']):
                    # Truncar a 100 chars
                    finding = content[:100].replace('\n', ' ')
                    if finding not in key_findings:
                        key_findings.append(finding)
    
    # Construir el resumen
    summary_parts = []
    summary_parts.append(f"[CONTEXT: {len(truncated_messages)} earlier messages truncated]")
    
    if commands_executed:
        # Limitar a los últimos 10 comandos únicos
        unique_cmds = list(dict.fromkeys(commands_executed[-10:]))
        summary_parts.append(f"Commands executed: {', '.join(unique_cmds[:5])}{'...' if len(unique_cmds) > 5 else ''}")
    
    if key_findings:
        summary_parts.append(f"Key findings: {'; '.join(key_findings[:3])}")
    
    return "\n".join(summary_parts)

# =============================================================================
# FUNCIONES CRUD PARA CONVERSATION_SUMMARIES
# =============================================================================

def add_conversation_summary(
    conversation_id: str,
    start_message_id: int,
    end_message_id: int,
    summary_text: str,
    recursive_level: int = 0,
    token_count: int = None,
    anchor_user_message_id: int = None
) -> int:
    """
    Añade un resumen de bloque de conversación a la BD.
    
    Args:
        conversation_id: ID de la conversación
        start_message_id: ID del primer mensaje del bloque (mensaje USER ancla)
        end_message_id: ID del último mensaje del bloque
        summary_text: Texto del resumen generado por LLM
        recursive_level: 0=L2 (resumen de bloque), 1+=L3 (meta-resumen)
        token_count: Estimación de tokens del resumen
        anchor_user_message_id: ID del mensaje USER que ancla este bloque
        
    Returns:
        ID del resumen insertado
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO conversation_summaries 
            (conversation_id, start_message_id, end_message_id, summary_text, 
             recursive_level, token_count, anchor_user_message_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (conversation_id, start_message_id, end_message_id, summary_text,
              recursive_level, token_count, anchor_user_message_id))
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_summaries_for_conversation(conversation_id: str, max_level: int = None) -> List[Dict]:
    """
    Obtiene todos los resúmenes de una conversación, ordenados por nivel y posición.
    
    Args:
        conversation_id: ID de la conversación
        max_level: Si se especifica, solo devuelve resúmenes hasta ese nivel
        
    Returns:
        Lista de resúmenes [{id, start_message_id, end_message_id, summary_text, ...}]
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        if max_level is not None:
            cursor.execute("""
                SELECT * FROM conversation_summaries 
                WHERE conversation_id = ? AND recursive_level <= ?
                ORDER BY recursive_level ASC, start_message_id ASC
            """, (conversation_id, max_level))
        else:
            cursor.execute("""
                SELECT * FROM conversation_summaries 
                WHERE conversation_id = ?
                ORDER BY recursive_level ASC, start_message_id ASC
            """, (conversation_id,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_best_summary_covering_range(conversation_id: str, from_msg_id: int, to_msg_id: int) -> Optional[Dict]:
    """
    Algoritmo Greedy: Encuentra el resumen MÁS GRANDE que cubra el rango especificado.
    Prioriza resúmenes de nivel más alto (L3 > L2) porque cubren más contexto.
    
    Args:
        conversation_id: ID de la conversación
        from_msg_id: ID del mensaje desde donde buscar
        to_msg_id: ID del mensaje hasta donde buscar
        
    Returns:
        El resumen de mayor cobertura o None si no hay
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        # Buscar resumen que cubra el rango, priorizando mayor cobertura
        cursor.execute("""
            SELECT *, (end_message_id - start_message_id) as coverage
            FROM conversation_summaries 
            WHERE conversation_id = ?
              AND start_message_id <= ?
              AND end_message_id >= ?
            ORDER BY coverage DESC, recursive_level DESC
            LIMIT 1
        """, (conversation_id, from_msg_id, to_msg_id))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_summaries_in_range(conversation_id: str, from_msg_id: int, to_msg_id: int) -> List[Dict]:
    """
    Obtiene todos los resúmenes L2 que intersectan con un rango de mensajes.
    Útil para reconstrucción de contexto histórico.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT * FROM conversation_summaries 
            WHERE conversation_id = ?
              AND recursive_level = 0
              AND NOT (end_message_id < ? OR start_message_id > ?)
            ORDER BY start_message_id ASC
        """, (conversation_id, from_msg_id, to_msg_id))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def delete_summaries_for_conversation(conversation_id: str):
    """Elimina todos los resúmenes de una conversación (para cleanup)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM conversation_summaries WHERE conversation_id = ?", (conversation_id,))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def invalidate_summaries_after(conversation_id: str, message_id: int):
    """
    Invalida resúmenes que incluyan mensajes posteriores a message_id.
    Útil si se borran o modifican mensajes del historial.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            DELETE FROM conversation_summaries 
            WHERE conversation_id = ? AND end_message_id >= ?
        """, (conversation_id, message_id))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


# =============================================================================
# PROMPT DEL CONSOLIDADOR LLM (Specializado Cybersecurity)
# =============================================================================

LLM_SUMMARIZER_SYSTEM_PROMPT = """You are a **Cybersecurity Engagement Chronicler**. Your task is to produce a concise, high-density summary of a conversation block from a penetration testing or security assessment session.

## CRITICAL OUTPUT REQUIREMENTS
- Maximum 300 words
- NO markdown headers, NO bullet lists - use flowing prose with semicolons
- Focus ONLY on operationally relevant information
- Write in past tense as a historical record

## MUST EXTRACT (if present):
1. **IPs/Hosts discovered**: Target addresses, network ranges, hostnames
2. **Credentials found**: Usernames, passwords, hashes, tokens, keys
3. **CVEs/Vulnerabilities**: Specific CVE IDs, vulnerability names, affected services
4. **Commands executed**: Key commands that produced results (especially successful ones)
5. **What worked vs failed**: Attack paths that succeeded, dead ends encountered
6. **Services/Ports**: Open ports, running services, versions detected
7. **Files of interest**: Config files read, loot obtained, artifacts found

## OUTPUT FORMAT
Write a single dense paragraph summarizing the engagement block. Example:
"Scanned 192.168.1.0/24 finding hosts .10, .15, .20 active; port scan on .15 revealed SSH:22 OpenSSH 7.9, HTTP:80 Apache 2.4.38; nikto found /admin exposed; attempted default creds admin:admin on /admin - success; discovered LFI via page parameter reading /etc/passwd showing users root, www-data, backup; privesc path identified through backup user cron job..."

## WHAT TO OMIT
- Greetings, pleasantries, filler
- Error messages without context
- Repeated failed attempts (summarize as "multiple failed attempts at X")
- Tool output formatting/ANSI codes"""


async def llm_summarize_block(
    messages_block: List[Dict], 
    client,  # AsyncOpenAI client
    model: str = None
) -> str:
    """
    Usa el LLM para generar un resumen inteligente de un bloque de mensajes.
    
    Args:
        messages_block: Lista de mensajes a resumir (USER + ASSISTANT + TOOL secuencia)
        client: Cliente AsyncOpenAI configurado
        model: Modelo a usar (si None, usa el modelo actual del cliente)
        
    Returns:
        Texto del resumen generado
    """
    import re
    
    # Construir el contenido a resumir
    content_parts = []
    for msg in messages_block:
        role = msg.get('role', 'unknown')
        content = msg.get('content', '') or ''
        
        # Limpiar ANSI codes
        content = re.sub(r'\x1b\[[0-9;]*m', '', content)
        
        if role == 'user':
            content_parts.append(f"[USER]: {content[:500]}")
        elif role == 'assistant':
            if msg.get('tool_calls'):
                tool_names = []
                for tc in msg.get('tool_calls', []):
                    if isinstance(tc, dict):
                        func = tc.get('function', {})
                        tool_names.append(func.get('name', 'unknown'))
                content_parts.append(f"[ASSISTANT called: {', '.join(tool_names)}]")
            elif content:
                content_parts.append(f"[ASSISTANT]: {content[:300]}")
        elif role == 'tool':
            # Truncar outputs muy largos
            tool_content = content[:1000] if len(content) > 1000 else content
            content_parts.append(f"[TOOL OUTPUT]: {tool_content}")
    
    block_text = "\n".join(content_parts)
    
    if len(block_text) < 100:
        # Bloque muy pequeño, no vale la pena resumir
        return _generate_truncated_summary(messages_block)
    
    # Llamar al LLM
    try:
        response = await client.chat.completions.create(
            model=model or "gpt-4o-mini",  # Modelo ligero para resumir
            messages=[
                {"role": "system", "content": LLM_SUMMARIZER_SYSTEM_PROMPT},
                {"role": "user", "content": f"Summarize this engagement block:\n\n{block_text}"}
            ],
            max_tokens=400,
            temperature=0.3  # Baja temperatura para resúmenes consistentes
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"⚠️ LLM summarization failed: {e}, falling back to rule-based")
        return _generate_truncated_summary(messages_block)



def smart_truncate_messages(messages: List[Dict], max_messages: int, preserve_user: bool = True) -> List[Dict]:
    """
    Trunca mensajes de forma inteligente para agentes autónomos.
    
    ESTRATEGIA:
    1. SIEMPRE preservar el system prompt
    2. SIEMPRE preservar TODOS los mensajes del usuario (son pocos en modo agéntico)
    3. Mantener los últimos RECENT_MESSAGES_TO_KEEP mensajes intactos
    4. Para mensajes intermedios: generar un resumen compacto
    5. Nunca romper pares assistant+tool_calls / tool_responses
    
    En un proceso agéntico típico:
    - Hay 1-5 mensajes del usuario como máximo
    - El resto son assistant+tool_calls y tool_responses
    - Los mensajes más recientes son los más relevantes
    """
    if len(messages) <= max_messages:
        return messages
    
    print(f"🔄 Truncando: {len(messages)} mensajes -> max {max_messages}")
    
    original_messages = messages.copy()
    
    # =========================================================================
    # PASO 1: Identificar mensajes críticos que NUNCA se eliminan
    # =========================================================================
    system_msg = None
    user_messages = []  # Índices de TODOS los mensajes de usuario
    user_msg_objects = []  # Los mensajes de usuario en sí
    
    start_idx = 0
    if original_messages and original_messages[0].get('role') == 'system':
        system_msg = original_messages[0]
        start_idx = 1
    
    # Encontrar TODOS los mensajes de usuario
    for i in range(start_idx, len(original_messages)):
        if original_messages[i].get('role') == 'user':
            user_messages.append(i)
            user_msg_objects.append(original_messages[i])
    
    if not user_messages:
        print("⚠️ CRÍTICO: No hay mensajes de usuario - devolviendo sin truncar")
        return original_messages
    
    print(f"📋 Encontrados {len(user_messages)} mensajes de usuario")
    
    # =========================================================================
    # PASO 2: Calcular cuántos mensajes podemos mantener
    # =========================================================================
    # Espacio: max_messages - system - usuarios - resumen
    reserved_for_users = len(user_msg_objects)
    reserved_for_system = 1 if system_msg else 0
    reserved_for_summary = SUMMARY_SLOT_COUNT
    
    available_for_recent = max_messages - reserved_for_system - reserved_for_users - reserved_for_summary
    
    if available_for_recent < 10:
        # Muy poco espacio - al menos mantener 10 mensajes recientes
        available_for_recent = 10
    
    # =========================================================================
    # PASO 3: Identificar BLOQUES de interacción (assistant+tools o mensaje suelto)
    # =========================================================================
    # Un bloque es:
    # - Un assistant con tool_calls + todos sus tool responses
    # - O un mensaje suelto (assistant sin tools, user, etc.)
    
    blocks = []
    non_user_indices = []  # Índices de mensajes no-user para tracking
    
    i = start_idx
    while i < len(original_messages):
        msg = original_messages[i]
        
        # Saltar mensajes de usuario (se manejan por separado)
        if msg.get('role') == 'user':
            i += 1
            continue
        
        if msg.get('role') == 'assistant' and msg.get('tool_calls'):
            # Bloque: assistant con tool_calls + sus tool responses
            block_indices = [i]
            tool_call_ids = set()
            tcs = msg.get('tool_calls', [])
            if isinstance(tcs, str):
                import json
                try:
                    tcs = json.loads(tcs)
                except:
                    tcs = []
            for tc in tcs:
                if isinstance(tc, dict):
                    tool_call_ids.add(tc.get('id'))
            
            j = i + 1
            while j < len(original_messages):
                next_msg = original_messages[j]
                if next_msg.get('role') == 'tool' and next_msg.get('tool_call_id') in tool_call_ids:
                    block_indices.append(j)
                    tool_call_ids.discard(next_msg.get('tool_call_id'))
                    j += 1
                elif next_msg.get('role') == 'user':
                    j += 1  # Saltar usuarios
                else:
                    break
            
            blocks.append(block_indices)
            non_user_indices.extend(block_indices)
            i = j
        else:
            # Mensaje suelto (assistant sin tools)
            blocks.append([i])
            non_user_indices.append(i)
            i += 1
    
    # =========================================================================
    # PASO 4: Seleccionar bloques más recientes que quepan
    # =========================================================================
    if not blocks:
        return original_messages
    
    # Calcular cuántos mensajes (no de usuario) tenemos en total
    total_non_user = len(non_user_indices)
    
    if total_non_user <= available_for_recent:
        # Todo cabe - no necesitamos truncar
        return original_messages
    
    # Seleccionar bloques desde el final hasta llenar el espacio
    selected_blocks = []
    total_selected = 0
    
    for block in reversed(blocks):
        block_size = len(block)
        if total_selected + block_size <= available_for_recent:
            selected_blocks.insert(0, block)
            total_selected += block_size
        else:
            # Este bloque no cabe completo - no lo partimos
            break
    
    # Índices que se mantienen
    recent_indices = set()
    for block in selected_blocks:
        recent_indices.update(block)
    
    # Índices que se truncan (para el resumen)
    truncate_indices = set(non_user_indices) - recent_indices
    
    print(f"📊 Zona reciente: {len(recent_indices)} msgs en {len(selected_blocks)} bloques")
    print(f"📊 Zona a truncar: {len(truncate_indices)} msgs")
    
    # =========================================================================
    # PASO 5: Generar resumen de los mensajes truncados
    # =========================================================================
    truncated_msgs = [original_messages[i] for i in sorted(truncate_indices)]
    summary_text = _generate_truncated_summary(truncated_msgs)
    
    # =========================================================================
    # PASO 6: Reconstruir el resultado
    # =========================================================================
    result = []
    
    # 1. System prompt (con resumen de truncados incluido si hay)
    if system_msg:
        # Si hay resumen, añadirlo al system prompt
        if summary_text and truncate_indices:
            enhanced_system = system_msg.copy()
            current_content = enhanced_system.get('content', '')
            enhanced_system['content'] = current_content + f"\n\n## 📜 TRUNCATED CONTEXT SUMMARY\n{summary_text}"
            result.append(enhanced_system)
            print(f"📝 Resumen inyectado en system prompt")
        else:
            result.append(system_msg)
    elif summary_text and truncate_indices:
        # No hay system prompt pero hay resumen - crear uno
        result.append({
            "role": "system",
            "content": f"## 📜 TRUNCATED CONTEXT SUMMARY\n{summary_text}"
        })
    
    # 2. Primer mensaje de usuario (OBLIGATORIO para Gemini)
    first_user_added = False
    if user_msg_objects:
        result.append(user_msg_objects[0])
        first_user_added = True
    
    # 3. Ahora añadir los mensajes de la zona reciente Y los usuarios restantes
    #    en su orden cronológico correcto
    
    # Crear lista de mensajes a incluir (zona reciente + usuarios excepto el primero)
    remaining_users = user_messages[1:] if first_user_added else user_messages
    indices_to_include = recent_indices | set(remaining_users)
    
    for i in range(start_idx, len(original_messages)):
        if i in indices_to_include:
            result.append(original_messages[i])
    
    # =========================================================================
    # PASO 6: Validación de secuencia para Gemini
    # =========================================================================
    result = ensure_valid_message_sequence(result)
    
    # Garantía final: al menos un usuario
    has_user = any(m.get('role') == 'user' for m in result)
    if not has_user and user_msg_objects:
        print("⚠️ Restaurando mensaje de usuario")
        insert_idx = 1 if system_msg else 0
        result.insert(insert_idx, user_msg_objects[0])
    
    print(f"✅ Truncado completado: {len(original_messages)} -> {len(result)} msgs")
    print(f"   - System: {1 if system_msg else 0}")
    print(f"   - Usuarios preservados: {len([m for m in result if m.get('role') == 'user'])}")
    print(f"   - Resumen incluido: {'Sí' if summary_text else 'No'}")
    
    return result


# =============================================================================
# SMART TRUNCATE CON MEMORIA JERÁRQUICA (Cascading Context)
# =============================================================================
# 
# ARQUITECTURA DE MEMORIA POR CAPAS:
# 
# L1 (Working Memory):  Mensajes RAW recientes, sin modificar
# L2 (Consolidated):    Resúmenes de bloques [USER + ASSISTANT/TOOL sequence]
# L3 (Chronicle):       Resúmenes de resúmenes (meta-consolidación)
#
# ESTRUCTURA DE REEMPLAZO (NO inyección en system):
#
# ANTES:  [SYSTEM, USER1, ASST, TOOL, ASST, TOOL, USER2, ASST, TOOL, USER3...]
# DESPUÉS:[SYSTEM, USER1, {SUMMARY_MSG}, USER2, ASST, TOOL, USER3...]
#
# El {SUMMARY_MSG} REEMPLAZA los mensajes ASST/TOOL, manteniendo USER como ancla.
# =============================================================================

async def smart_truncate_with_hierarchical_memory(
    messages: List[Dict], 
    max_messages: int,
    conversation_id: str,
    client = None,  # AsyncOpenAI client
    model: str = None,
    preserve_user: bool = True
) -> List[Dict]:
    """
    Sistema de Memoria Jerárquica con Reemplazo de Bloques.
    
    A diferencia del truncado simple, este sistema:
    1. Segmenta la conversación por mensajes USER (anclas)
    2. REEMPLAZA secuencias ASSISTANT/TOOL antiguas por mensajes de resumen
    3. Mantiene los mensajes USER originales para preservar la intención
    4. Usa caché en BD para no re-resumir bloques ya procesados
    
    Ventanas de memoria (% del max_messages):
    - ANCHOR (15%): System prompt (intocable)
    - RECENT (35%): Últimos mensajes RAW sin modificar
    - HISTORICAL (50%): Bloques resumidos que REEMPLAZAN los originales
    """
    # Si el sistema jerárquico está deshabilitado, usar versión normal
    if not LLM_HIERARCHICAL_MEMORY_ENABLED:
        return smart_truncate_messages(messages, max_messages, preserve_user)
    
    if len(messages) <= max_messages:
        return messages
    
    print(f"🧠 [CASCADING CONTEXT] Procesando {len(messages)} mensajes -> max {max_messages}")
    
    # Sin cliente LLM, fallback a versión normal
    if client is None:
        print("⚠️ No hay cliente LLM, usando truncado basado en reglas")
        return smart_truncate_messages(messages, max_messages, preserve_user)
    
    original_messages = messages.copy()
    
    # =========================================================================
    # PASO 1: Calcular ventanas de memoria dinámicas
    # =========================================================================
    anchor_slots = max(1, int(max_messages * MEMORY_WINDOW_ANCHOR_CRITICAL))  # 15%
    recent_slots = int(max_messages * MEMORY_WINDOW_RECENT)                    # 35%
    historical_slots = max_messages - anchor_slots - recent_slots              # 50%
    
    print(f"   📊 Ventanas: Anchor={anchor_slots}, Recent={recent_slots}, Historical={historical_slots}")
    
    # =========================================================================
    # PASO 2: Extraer system prompt (zona ANCHOR)
    # =========================================================================
    system_msg = None
    start_idx = 0
    if original_messages and original_messages[0].get('role') == 'system':
        system_msg = original_messages[0]
        start_idx = 1
    
    # =========================================================================
    # PASO 3: Segmentar por HITOS DE USUARIO (User-Anchored Blocks)
    # =========================================================================
    # Cada bloque = [USER] + [secuencia de ASSISTANT/TOOL hasta el siguiente USER]
    # El USER actúa como "pegamento semántico" - siempre se preserva
    
    user_indices = []
    for i in range(start_idx, len(original_messages)):
        if original_messages[i].get('role') == 'user':
            user_indices.append(i)
    
    if not user_indices:
        print("⚠️ No hay mensajes de usuario, usando truncado simple")
        return smart_truncate_messages(messages, max_messages, preserve_user)
    
    # Construir bloques: cada uno empieza en USER y termina antes del siguiente USER
    blocks = []
    for i, user_idx in enumerate(user_indices):
        # El bloque termina justo antes del siguiente USER, o al final
        if i + 1 < len(user_indices):
            block_end = user_indices[i + 1] - 1
        else:
            block_end = len(original_messages) - 1
        
        # Separar el mensaje USER del contenido ASSISTANT/TOOL
        user_msg = original_messages[user_idx]
        assistant_tool_msgs = original_messages[user_idx + 1:block_end + 1] if user_idx + 1 <= block_end else []
        
        blocks.append({
            'user_idx': user_idx,
            'user_msg': user_msg,
            'content_start': user_idx + 1,
            'content_end': block_end,
            'content_msgs': assistant_tool_msgs,
            'content_size': len(assistant_tool_msgs),
            'total_size': 1 + len(assistant_tool_msgs)  # USER + contenido
        })
    
    print(f"   📦 {len(blocks)} bloques USER-anchored identificados")
    
    # =========================================================================
    # PASO 4: Separar RECENT vs HISTORICAL (desde el final hacia atrás)
    # =========================================================================
    recent_blocks = []
    historical_blocks = []
    accumulated_size = 0
    
    # Iterar desde el bloque más reciente hacia el más antiguo
    for block in reversed(blocks):
        if accumulated_size + block['total_size'] <= recent_slots:
            recent_blocks.insert(0, block)
            accumulated_size += block['total_size']
        else:
            historical_blocks.insert(0, block)
    
    print(f"   📊 Bloques: {len(historical_blocks)} históricos, {len(recent_blocks)} recientes")
    
    if not historical_blocks:
        # Todo cabe en RECENT, no necesitamos resumir
        return smart_truncate_messages(messages, max_messages, preserve_user)
    
    # =========================================================================
    # PASO 5: Procesar bloques HISTÓRICOS (resumir o recuperar de caché)
    # =========================================================================
    # Para cada bloque histórico:
    # - Si ya existe resumen en BD -> usarlo
    # - Si no existe y es grande -> generar con LLM y cachear
    # - Si no existe y es pequeño -> usar resumen basado en reglas
    
    processed_historical = []  # Lista de (user_msg, summary_msg o None)
    
    for block in historical_blocks:
        user_msg = block['user_msg']
        content_msgs = block['content_msgs']
        
        if not content_msgs:
            # Bloque sin contenido ASSISTANT/TOOL, solo preservar USER
            processed_historical.append({
                'user_msg': user_msg,
                'summary_msg': None
            })
            continue
        
        # Buscar resumen cacheado en BD
        cached = get_best_summary_covering_range(
            conversation_id,
            block['content_start'],
            block['content_end']
        )
        
        if cached:
            print(f"   ♻️ Cache hit: bloque [{block['content_start']}-{block['content_end']}]")
            summary_text = cached['summary_text']
        else:
            # Calcular tamaño del contenido
            content_size = sum(len(str(m.get('content', ''))) for m in content_msgs)
            
            if content_size > BLOCK_SUMMARIZE_THRESHOLD:
                print(f"   🤖 LLM summarizing: bloque [{block['content_start']}-{block['content_end']}] ({content_size} chars)")
                summary_text = await llm_summarize_block(content_msgs, client, model)
                
                # Cachear en BD para futuras reconstrucciones
                add_conversation_summary(
                    conversation_id=conversation_id,
                    start_message_id=block['content_start'],
                    end_message_id=block['content_end'],
                    summary_text=summary_text,
                    recursive_level=0,
                    token_count=len(summary_text.split()),
                    anchor_user_message_id=block['user_idx']
                )
            else:
                # Bloque pequeño, resumen basado en reglas (sin LLM)
                summary_text = _generate_truncated_summary(content_msgs)
        
        # Crear mensaje de resumen que REEMPLAZA la secuencia ASSISTANT/TOOL
        summary_msg = {
            "role": "assistant",
            "content": f"[📜 CONTEXTO RESUMIDO]\n{summary_text}"
        }
        
        processed_historical.append({
            'user_msg': user_msg,
            'summary_msg': summary_msg
        })
    
    # =========================================================================
    # PASO 6: RECONSTRUIR el hilo con REEMPLAZOS (no inyección en system)
    # =========================================================================
    result = []
    
    # 1. System prompt (sin modificar)
    if system_msg:
        result.append(system_msg)
    
    # 2. Bloques HISTÓRICOS: USER original + mensaje de resumen que REEMPLAZA
    for processed in processed_historical:
        result.append(processed['user_msg'])
        if processed['summary_msg']:
            result.append(processed['summary_msg'])
    
    # 3. Bloques RECIENTES: todos los mensajes RAW sin modificar
    for block in recent_blocks:
        result.append(block['user_msg'])
        result.extend(block['content_msgs'])
    
    # =========================================================================
    # PASO 7: Validación de secuencia y límites
    # =========================================================================
    result = ensure_valid_message_sequence(result)
    
    # Verificar que no excedemos el límite (por seguridad)
    if len(result) > max_messages:
        print(f"   ⚠️ Resultado ({len(result)}) excede límite ({max_messages}), aplicando truncado adicional")
        # Truncar bloques históricos más antiguos
        excess = len(result) - max_messages
        # Remover mensajes del principio (después del system) hasta cumplir límite
        while len(result) > max_messages and len(result) > 2:
            if result[1].get('role') == 'user':
                # Buscar si el siguiente es un resumen, remover ambos
                if len(result) > 2 and result[2].get('content', '').startswith('[📜 CONTEXTO'):
                    result.pop(2)  # Remover resumen
                result.pop(1)  # Remover USER
            else:
                result.pop(1)
    
    print(f"✅ [CASCADING] Resultado: {len(original_messages)} -> {len(result)} mensajes")
    print(f"   - Bloques resumidos: {len(historical_blocks)}")
    print(f"   - Bloques RAW: {len(recent_blocks)}")
    
    return result


async def consolidate_summaries_to_chronicle(
    conversation_id: str,
    summaries: List[Dict],
    client,
    model: str = None
) -> str:
    """
    Nivel L3: Consolida múltiples resúmenes L2 en una "Crónica de Misión".
    
    Usado cuando la zona HISTORICAL tiene demasiados resúmenes y necesitamos
    meta-consolidar para seguir reduciendo el contexto.
    
    Args:
        conversation_id: ID de la conversación
        summaries: Lista de resúmenes L2 a consolidar
        client: Cliente AsyncOpenAI
        model: Modelo a usar
        
    Returns:
        Texto del resumen L3 (crónica)
    """
    if len(summaries) < 2:
        return summaries[0]['summary_text'] if summaries else ""
    
    # Construir texto combinado de todos los resúmenes
    combined_text = "\n\n".join([
        f"[Phase {i+1}]: {s['summary_text']}" 
        for i, s in enumerate(summaries)
    ])
    
    # Prompt especializado para meta-consolidación
    chronicle_prompt = """You are consolidating multiple engagement phase summaries into a single Mission Chronicle.

CRITICAL REQUIREMENTS:
- Maintain chronological order of discoveries
- Preserve ALL: IPs, credentials, CVEs, successful commands
- Note what worked vs what failed
- Maximum 400 words

SUMMARIES TO CONSOLIDATE:
""" + combined_text
    
    try:
        response = await client.chat.completions.create(
            model=model or "gpt-4o-mini",
            messages=[
                {"role": "system", "content": LLM_SUMMARIZER_SYSTEM_PROMPT},
                {"role": "user", "content": chronicle_prompt}
            ],
            max_tokens=500,
            temperature=0.3
        )
        
        chronicle = response.choices[0].message.content.strip()
        
        # Guardar en BD como L3
        if summaries:
            add_conversation_summary(
                conversation_id=conversation_id,
                start_message_id=summaries[0].get('start_message_id', 0),
                end_message_id=summaries[-1].get('end_message_id', 0),
                summary_text=chronicle,
                recursive_level=1,  # L3 = nivel 1
                token_count=len(chronicle.split())
            )
        
        return chronicle
        
    except Exception as e:
        print(f"⚠️ Chronicle consolidation failed: {e}")
        # Fallback: concatenar resúmenes
        return " | ".join([s['summary_text'][:200] for s in summaries])


def ensure_valid_message_sequence(messages: List[Dict]) -> List[Dict]:
    """
    Asegura que la secuencia de mensajes sea válida para Gemini/DeepSeek:
    1. Después del system prompt, debe venir un mensaje de usuario
    2. Un assistant con tool_calls solo puede venir después de user o tool
    3. No puede haber dos assistant seguidos (sin tool responses entre medio)
    4. Los tool responses deben venir inmediatamente después de assistant con tool_calls
    5. NO puede haber tool responses duplicados para el mismo tool_call_id
    6. NO puede haber tool responses huérfanos (sin assistant con ese tool_call_id)
    
    REGLA CLAVE DE GEMINI: "function call turn comes immediately after a user turn 
    or after a function response turn"
    """
    if not messages:
        return messages
    
    # PRIMERA PASADA: Recolectar todos los tool_call_ids válidos de los assistants
    valid_tool_call_ids = set()
    for msg in messages:
        if msg.get('role') == 'assistant' and msg.get('tool_calls'):
            for tc in msg['tool_calls']:
                tc_id = tc.get('id')
                if tc_id:
                    valid_tool_call_ids.add(tc_id)
    
    # SEGUNDA PASADA: Eliminar tool responses duplicados Y huérfanos
    seen_tool_call_ids = set()
    deduped_messages = []
    
    for msg in messages:
        if msg.get('role') == 'tool':
            tc_id = msg.get('tool_call_id')
            if tc_id:
                # Verificar si es huérfano (no existe assistant con este tool_call_id)
                if tc_id not in valid_tool_call_ids:
                    print(f"⚠️ Eliminando tool response HUÉRFANO para {tc_id} (sin assistant correspondiente)")
                    continue  # Saltar huérfano
                # Verificar si es duplicado
                if tc_id in seen_tool_call_ids:
                    print(f"⚠️ Eliminando tool response DUPLICADO para {tc_id}")
                    continue  # Saltar duplicado
                seen_tool_call_ids.add(tc_id)
        deduped_messages.append(msg)
    
    messages = deduped_messages
    
    result = []
    
    # Preservar system prompt si existe
    start_idx = 0
    if messages[0].get('role') == 'system':
        result.append(messages[0])
        start_idx = 1
    
    # Encontrar el primer mensaje de usuario después del system prompt
    first_user_idx = None
    for i in range(start_idx, len(messages)):
        if messages[i].get('role') == 'user':
            first_user_idx = i
            break
    
    if first_user_idx is None:
        # No hay mensajes de usuario, devolver solo el system prompt o vacío
        print("⚠️ No se encontró mensaje de usuario en el historial truncado")
        return result
    
    # Agregar mensajes desde el primer usuario
    i = first_user_idx
    while i < len(messages):
        msg = messages[i]
        role = msg.get('role')
        has_tool_calls = bool(msg.get('tool_calls'))
        
        # Obtener info del último mensaje en result
        last_role = result[-1].get('role') if result else None
        last_has_tool_calls = bool(result[-1].get('tool_calls')) if result else False
        
        # REGLA 1: Después de assistant con tool_calls DEBE venir tool
        if last_role == 'assistant' and last_has_tool_calls:
            if role != 'tool':
                # El assistant anterior tenía tool_calls pero no siguen tool responses
                # Esto rompe la secuencia - eliminar el assistant problemático
                print(f"⚠️ Eliminando assistant con tool_calls sin responses (siguiente es {role})")
                result.pop()
                # Recalcular last_role
                last_role = result[-1].get('role') if result else None
                last_has_tool_calls = bool(result[-1].get('tool_calls')) if result else False
        
        # REGLA 2: assistant con tool_calls solo puede venir después de user o tool
        if role == 'assistant' and has_tool_calls:
            if last_role not in (None, 'user', 'tool', 'system'):
                # Inválido: assistant con tool_calls después de assistant
                print(f"⚠️ Saltando assistant+tool_calls inválido (después de {last_role})")
                i += 1
                continue
        
        # REGLA 3: No dos assistant seguidos (a menos que el primero tenga tool_calls pendientes de tools)
        if role == 'assistant' and last_role == 'assistant' and not last_has_tool_calls:
            # Dos assistant seguidos sin tools - eliminar el anterior
            print(f"⚠️ Eliminando assistant duplicado consecutivo")
            result.pop()
        
        # REGLA 4: tool solo puede venir después de assistant con tool_calls O después de otro tool
        # (un assistant puede hacer múltiples tool_calls, cada uno genera un tool response)
        if role == 'tool':
            if last_role == 'tool':
                # Múltiples tool responses consecutivos - esto es válido si hay un assistant
                # con tool_calls antes en la secuencia. Verificar que existe.
                has_pending_assistant = False
                for j in range(len(result) - 1, -1, -1):
                    if result[j].get('role') == 'assistant' and result[j].get('tool_calls'):
                        has_pending_assistant = True
                        break
                    elif result[j].get('role') == 'assistant':
                        # Assistant sin tool_calls antes de los tools - inválido
                        break
                
                if not has_pending_assistant:
                    print(f"⚠️ Saltando tool response sin assistant con tool_calls previo")
                    i += 1
                    continue
                # Es válido - continuar
            elif last_role != 'assistant' or not last_has_tool_calls:
                # Tool huérfano - no hay assistant con tool_calls antes
                print(f"⚠️ Saltando tool response huérfano (anterior es {last_role})")
                i += 1
                continue
        
        result.append(msg)
        i += 1
    
    # SANITIZACIÓN FINAL: Asegurar que ningún mensaje tenga content=null
    # DeepSeek y otros proveedores no aceptan null, solo string vacío
    for msg in result:
        if msg.get('content') is None:
            msg['content'] = ""
    
    # Validación final: si termina con assistant con tool_calls sin tools, quitarlo
    while result and result[-1].get('role') == 'assistant' and result[-1].get('tool_calls'):
        # Verificar si hay más mensajes después que sean tools
        # En este punto ya procesamos todo, así que si termina así, es porque no hay tools
        # Pero esto puede ser válido si estamos en medio de una iteración del agente
        # Solo lo quitamos si no hay ningún tool después
        has_pending_tools = False
        for remaining_msg in messages[i:]:
            if remaining_msg.get('role') == 'tool':
                has_pending_tools = True
                break
        
        if not has_pending_tools:
            print(f"ℹ️ Historial termina con assistant+tool_calls (estado normal si hay ejecución pendiente)")
        break
    
    return result

def get_conversation_for_llm(leaf_id: int) -> List[Dict[str, str]]:
    """
    Reconstruye el historial en formato para enviar al LLM.
    Solo incluye role y content (formato OpenAI).
    
    OPTIMIZACIÓN: Limita el número de mensajes y trunca respuestas largas
    para evitar exceder límites de tokens.
    
    IMPORTANTE: Usa truncado inteligente que preserva pares tool_call/tool_response.
    """
    thread = reconstruct_thread(leaf_id)
    
    # Crear un mapa de tool_call_id -> function_name para referencias rápidas
    tool_call_names: Dict[str, str] = {}
    for msg in thread:
        if msg['tool_calls']:
            import json
            try:
                tool_calls = json.loads(msg['tool_calls'])
                for tc in tool_calls:
                    tc_id = tc.get('id')
                    func_name = tc.get('function', {}).get('name', '')
                    if tc_id and func_name:
                        tool_call_names[tc_id] = func_name
            except:
                pass
    
    messages = []
    for msg in thread:
        content = msg['content'] or ""
        
        # Truncar respuestas de tools que sean muy largas
        if msg['role'] == 'tool' and len(content) > MAX_TOOL_RESPONSE_LENGTH:
            content = content[:MAX_TOOL_RESPONSE_LENGTH] + f"\n\n[... truncado, {len(msg['content'])} chars total]"
        
        message = {"role": msg['role'], "content": content}
        
        # Si tiene tool_calls, añadirlo (con sanitización)
        if msg['tool_calls']:
            import json
            raw_tool_calls = json.loads(msg['tool_calls'])
            
            # DEEPSEEK REASONING MODE: Extraer reasoning_content si existe
            # Lo guardamos como primer elemento con _metadata
            reasoning_content = None
            if raw_tool_calls and isinstance(raw_tool_calls[0], dict) and '_metadata' in raw_tool_calls[0]:
                metadata = raw_tool_calls[0].get('_metadata', {})
                reasoning_content = metadata.get('reasoning_content')
                raw_tool_calls = raw_tool_calls[1:]  # Quitar metadata del array de tool_calls
                if reasoning_content:
                    print(f"🧠 DeepSeek reasoning extraído: {len(reasoning_content)} chars")
            
            # SANITIZACIÓN: Filtrar tool_calls corruptos (DeepSeek streaming bug)
            # Los tool_calls válidos DEBEN tener id y function.name
            valid_tool_calls = []
            for tc in raw_tool_calls:
                tc_id = tc.get('id')
                func_name = tc.get('function', {}).get('name')
                
                if tc_id and func_name:
                    # También sanitizar arguments null -> "{}"
                    if tc.get('function', {}).get('arguments') is None:
                        tc['function']['arguments'] = "{}"
                    valid_tool_calls.append(tc)
            
            if valid_tool_calls:
                message['tool_calls'] = valid_tool_calls
                # DEEPSEEK REASONING MODE: Incluir reasoning_content en el mensaje
                # Si no hay reasoning_content pero hay tool_calls, usar placeholder vacío
                # DeepSeek reasoner REQUIERE este campo en todos los assistant con tool_calls
                if reasoning_content:
                    message['reasoning_content'] = reasoning_content
                else:
                    # Placeholder para evitar error de DeepSeek reasoner
                    message['reasoning_content'] = ""
            else:
                # Si no quedaron tool_calls válidos, no incluir el campo
                print(f"⚠️ Todos los tool_calls de un mensaje eran inválidos - eliminando campo")
        
        # Si es respuesta de tool, añadir tool_call_id Y el nombre de la función
        if msg['tool_call_id']:
            message['tool_call_id'] = msg['tool_call_id']
            # Google Gemini REQUIERE el nombre de la función en tool responses
            if msg['tool_call_id'] in tool_call_names:
                message['name'] = tool_call_names[msg['tool_call_id']]
            else:
                # Fallback: si no encontramos el nombre, usar un placeholder
                # Esto puede pasar si el truncado eliminó el mensaje con el tool_call
                message['name'] = 'unknown_function'
                print(f"⚠️ Tool response sin tool_call correspondiente: {msg['tool_call_id']}")
        
        messages.append(message)
    
    # Usar truncado inteligente que preserva pares tool_call/tool_response
    if len(messages) > MAX_MESSAGES_FOR_LLM:
        original_len = len(messages)
        messages = smart_truncate_messages(messages, MAX_MESSAGES_FOR_LLM)
        print(f"⚠️ Contexto truncado inteligente: {original_len} msgs -> {len(messages)} msgs")
    
    # SANITIZACIÓN FINAL: Asegurar que ningún mensaje tenga content=null
    # DeepSeek y otros proveedores no aceptan null, solo string vacío
    # DEBE estar DESPUÉS de smart_truncate_messages porque ese copia mensajes originales
    for msg in messages:
        if msg.get('content') is None:
            msg['content'] = ""
    
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
    MAX_PENDING_JOB_RESULT_LENGTH = 2000  # Limitar el tamaño del resultado para evitar problemas de almacenamiento
    # Recortamos el resultado si es demasiado largo para evitar problemas de almacenamiento
    if len(result) > MAX_PENDING_JOB_RESULT_LENGTH:
        print(f"⚠️ Resultado del job {job_id} excede límite, truncando")
        result = result[:MAX_PENDING_JOB_RESULT_LENGTH] + f"\n\n[... truncado, {len(result)} chars total]"
    
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


# =============================================================================
# MODO AGÉNTICO - GESTIÓN DE MISIONES
# =============================================================================

def generate_mission_id() -> str:
    """Genera un ID único para misiones."""
    return f"mission_{uuid.uuid4().hex[:12]}"


def create_mission(conversation_id: str, goal: str, metadata: dict = None) -> str:
    """
    Crea una nueva misión autónoma.
    
    Args:
        conversation_id: ID de la conversación asociada
        goal: Objetivo de alto nivel de la misión
        metadata: Info adicional (target, tipo de test, etc)
    
    Returns:
        ID de la misión creada
    """
    import json
    mission_id = generate_mission_id()
    now = datetime.utcnow().isoformat()
    metadata_json = json.dumps(metadata) if metadata else None
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO missions (id, conversation_id, goal, status, created_at, metadata)
            VALUES (?, ?, ?, 'PLANNING', ?, ?)
        """, (mission_id, conversation_id, goal, now, metadata_json))
        conn.commit()
    
    print(f"🎯 Misión creada: {mission_id[:20]}... - Goal: {goal[:50]}...")
    return mission_id


def get_mission(mission_id: str) -> Optional[Dict[str, Any]]:
    """Obtiene los datos de una misión por ID."""
    import json
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM missions WHERE id = ?", (mission_id,))
        row = cursor.fetchone()
        if row:
            result = dict(row)
            # Parsear metadata JSON
            if result.get('metadata'):
                try:
                    result['metadata'] = json.loads(result['metadata'])
                except:
                    pass
            return result
        return None


def get_active_mission(conversation_id: str) -> Optional[Dict[str, Any]]:
    """
    Obtiene la misión activa (no completada) de una conversación.
    Solo puede haber una misión activa por conversación.
    """
    import json
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM missions 
            WHERE conversation_id = ? AND status IN ('PLANNING', 'IN_PROGRESS')
            ORDER BY created_at DESC
            LIMIT 1
        """, (conversation_id,))
        row = cursor.fetchone()
        if row:
            result = dict(row)
            if result.get('metadata'):
                try:
                    result['metadata'] = json.loads(result['metadata'])
                except:
                    pass
            return result
        return None


def update_mission_phase(mission_id: str, phase: str) -> bool:
    """Actualiza la fase actual de una misión."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE missions SET current_phase = ?, status = 'IN_PROGRESS'
            WHERE id = ?
        """, (phase, mission_id))
        conn.commit()
        return cursor.rowcount > 0


def update_mission_status(mission_id: str, status: str) -> bool:
    """Actualiza el estado de una misión."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE missions SET status = ? WHERE id = ?
        """, (status, mission_id))
        conn.commit()
        return cursor.rowcount > 0


def complete_mission(mission_id: str, status: str = 'COMPLETED') -> bool:
    """
    Marca una misión como completada (COMPLETED/FAILED/CANCELLED).
    """
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE missions SET status = ?, completed_at = ?
            WHERE id = ?
        """, (status, now, mission_id))
        conn.commit()
        print(f"🏁 Misión {mission_id[:12]}... completada con estado: {status}")
        return cursor.rowcount > 0


# =============================================================================
# MODO AGÉNTICO - SCRATCHPAD/MEMORIA DEL AGENTE
# =============================================================================

def get_mission_scratchpad(mission_id: str) -> str:
    """
    Obtiene el scratchpad (memoria) de una misión.
    El scratchpad es un bloc de notas privado del agente para guardar
    hallazgos importantes, credenciales, IPs, etc.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT scratchpad FROM missions WHERE id = ?", (mission_id,))
        row = cursor.fetchone()
        if row and row[0]:
            return row[0]
        return ""


def update_mission_scratchpad(mission_id: str, content: str, mode: str = 'replace') -> bool:
    """
    Actualiza el scratchpad de una misión.
    
    Args:
        mission_id: ID de la misión
        content: Contenido a escribir
        mode: 'replace' para reemplazar todo, 'append' para añadir al final
    
    Returns:
        True si se actualizó correctamente
    """
    with get_db() as conn:
        cursor = conn.cursor()
        
        if mode == 'append':
            # Obtener contenido actual
            cursor.execute("SELECT scratchpad FROM missions WHERE id = ?", (mission_id,))
            row = cursor.fetchone()
            current = row[0] if row and row[0] else ""
            
            # Añadir separador si hay contenido previo
            if current:
                content = current + "\n---\n" + content
        
        cursor.execute("""
            UPDATE missions SET scratchpad = ? WHERE id = ?
        """, (content, mission_id))
        conn.commit()
        
        print(f"📝 Scratchpad actualizado para misión {mission_id[:12]}... (modo: {mode})")
        return cursor.rowcount > 0


def clear_mission_scratchpad(mission_id: str) -> bool:
    """Limpia el scratchpad de una misión."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE missions SET scratchpad = NULL WHERE id = ?
        """, (mission_id,))
        conn.commit()
        print(f"🗑️ Scratchpad limpiado para misión {mission_id[:12]}...")
        return cursor.rowcount > 0


# =============================================================================
# MODO AGÉNTICO - GESTIÓN DE OBJETIVOS
# =============================================================================

def add_objectives(mission_id: str, tasks: List[str]) -> List[int]:
    """
    Añade una lista de objetivos a una misión.
    
    Args:
        mission_id: ID de la misión
        tasks: Lista de descripciones de tareas
    
    Returns:
        Lista de IDs de los objetivos creados
    """
    now = datetime.utcnow().isoformat()
    objective_ids = []
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Obtener el último order_index existente
        cursor.execute("""
            SELECT COALESCE(MAX(order_index), -1) FROM objectives WHERE mission_id = ?
        """, (mission_id,))
        last_index = cursor.fetchone()[0]
        
        for i, task in enumerate(tasks):
            order_index = last_index + 1 + i
            cursor.execute("""
                INSERT INTO objectives (mission_id, order_index, task, status, created_at)
                VALUES (?, ?, ?, 'PENDING', ?)
            """, (mission_id, order_index, task, now))
            objective_ids.append(cursor.lastrowid)
        
        conn.commit()
    
    print(f"📋 {len(tasks)} objetivos añadidos a misión {mission_id[:12]}...")
    return objective_ids


def get_objectives(mission_id: str) -> List[Dict[str, Any]]:
    """Obtiene todos los objetivos de una misión ordenados por order_index."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM objectives 
            WHERE mission_id = ? 
            ORDER BY order_index ASC
        """, (mission_id,))
        return [dict(row) for row in cursor.fetchall()]


def get_objective_by_id(objective_id: int) -> Optional[Dict[str, Any]]:
    """Obtiene un objetivo específico por ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM objectives WHERE id = ?", (objective_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def update_objective_status(objective_id: int, status: str, result: str = None, reflection: str = None) -> bool:
    """
    Actualiza el estado de un objetivo.
    
    Args:
        objective_id: ID del objetivo
        status: PENDING | IN_PROGRESS | COMPLETED | FAILED | SKIPPED | AWAITING_AUTHORIZATION
        result: Resumen del resultado (opcional)
        reflection: Reflexión del agente sobre por qué funcionó/falló (opcional)
    """
    now = datetime.utcnow().isoformat()
    completed_at = now if status in ('COMPLETED', 'FAILED', 'SKIPPED') else None
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE objectives 
            SET status = ?, result_summary = COALESCE(?, result_summary), 
                reflection = COALESCE(?, reflection), completed_at = ?
            WHERE id = ?
        """, (status, result, reflection, completed_at, objective_id))
        conn.commit()
        
        if cursor.rowcount > 0:
            print(f"📝 Objetivo {objective_id} actualizado: {status}")
        return cursor.rowcount > 0


def update_objective_task(objective_id: int, new_task: str) -> bool:
    """Actualiza la descripción de un objetivo."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE objectives SET task = ? WHERE id = ?
        """, (new_task, objective_id))
        conn.commit()
        return cursor.rowcount > 0


def insert_objective_after(mission_id: str, after_id: int, task: str) -> int:
    """
    Inserta un nuevo objetivo después de uno existente.
    Reordena los order_index de los objetivos siguientes.
    
    Args:
        mission_id: ID de la misión
        after_id: ID del objetivo después del cual insertar
        task: Descripción del nuevo objetivo
    
    Returns:
        ID del nuevo objetivo
    """
    now = datetime.utcnow().isoformat()
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Obtener el order_index del objetivo de referencia
        cursor.execute("SELECT order_index FROM objectives WHERE id = ?", (after_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Objetivo {after_id} no encontrado")
        
        insert_after_index = row[0]
        new_index = insert_after_index + 1
        
        # Desplazar los objetivos siguientes
        cursor.execute("""
            UPDATE objectives 
            SET order_index = order_index + 1 
            WHERE mission_id = ? AND order_index > ?
        """, (mission_id, insert_after_index))
        
        # Insertar el nuevo objetivo
        cursor.execute("""
            INSERT INTO objectives (mission_id, order_index, task, status, created_at)
            VALUES (?, ?, ?, 'PENDING', ?)
        """, (mission_id, new_index, task, now))
        
        new_id = cursor.lastrowid
        conn.commit()
        
        print(f"➕ Objetivo insertado después de {after_id}: {task[:50]}...")
        return new_id


def delete_objective(objective_id: int) -> bool:
    """
    Elimina un objetivo de una misión.
    NO reordena los índices (pueden quedar huecos).
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM objectives WHERE id = ?", (objective_id,))
        conn.commit()
        
        if cursor.rowcount > 0:
            print(f"🗑️ Objetivo {objective_id} eliminado")
        return cursor.rowcount > 0


def get_mission_progress(mission_id: str) -> Dict[str, Any]:
    """
    Calcula el progreso de una misión.
    
    Returns:
        Dict con total, completed, failed, pending, in_progress, percentage
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'IN_PROGRESS' THEN 1 ELSE 0 END) as in_progress,
                SUM(CASE WHEN status = 'SKIPPED' THEN 1 ELSE 0 END) as skipped,
                SUM(CASE WHEN status = 'AWAITING_AUTHORIZATION' THEN 1 ELSE 0 END) as awaiting
            FROM objectives WHERE mission_id = ?
        """, (mission_id,))
        
        row = cursor.fetchone()
        if not row or row[0] == 0:
            return {"total": 0, "completed": 0, "percentage": 0}
        
        total = row[0]
        completed = row[1] or 0
        
        return {
            "total": total,
            "completed": completed,
            "failed": row[2] or 0,
            "pending": row[3] or 0,
            "in_progress": row[4] or 0,
            "skipped": row[5] or 0,
            "awaiting_authorization": row[6] or 0,
            "percentage": round((completed / total) * 100, 1)
        }


def get_current_objective(mission_id: str) -> Optional[Dict[str, Any]]:
    """
    Obtiene el objetivo actualmente en progreso de una misión.
    Si no hay ninguno IN_PROGRESS, devuelve el primer PENDING.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Primero buscar IN_PROGRESS
        cursor.execute("""
            SELECT * FROM objectives 
            WHERE mission_id = ? AND status = 'IN_PROGRESS'
            ORDER BY order_index ASC
            LIMIT 1
        """, (mission_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        
        # Si no hay, buscar primer PENDING
        cursor.execute("""
            SELECT * FROM objectives 
            WHERE mission_id = ? AND status = 'PENDING'
            ORDER BY order_index ASC
            LIMIT 1
        """, (mission_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


# =============================================================================
# MODO AGÉNTICO - GESTIÓN DE RESÚMENES DE TOOLS
# =============================================================================

def save_tool_summary(message_id: int, tool_call_id: str, original: str, summary: str) -> int:
    """
    Guarda un resumen de output de tool junto con el original.
    
    Args:
        message_id: ID del mensaje que contiene el tool result
        tool_call_id: ID del tool_call específico
        original: Output original completo
        summary: Resumen generado
    
    Returns:
        ID del registro creado
    """
    now = datetime.utcnow().isoformat()
    original_length = len(original)
    compression_ratio = len(summary) / original_length if original_length > 0 else 1.0
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tool_summaries 
            (message_id, tool_call_id, original_output, original_length, summary, compression_ratio, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (message_id, tool_call_id, original, original_length, summary, compression_ratio, now))
        conn.commit()
        
        print(f"📦 Summary guardado: {original_length} chars → {len(summary)} chars ({compression_ratio:.1%})")
        return cursor.lastrowid


def get_tool_summary_entry(tool_call_id: str) -> Optional[Dict[str, Any]]:
    """
    Obtiene el registro completo de un tool summary por tool_call_id.
    Incluye el output original (para zoom in).
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM tool_summaries WHERE tool_call_id = ?
        """, (tool_call_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_tool_summary(message_id: int, tool_call_id: str) -> Optional[str]:
    """
    Obtiene solo el resumen de un tool (sin el original).
    Útil para reconstruir historial optimizado.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT summary FROM tool_summaries 
            WHERE message_id = ? AND tool_call_id = ?
        """, (message_id, tool_call_id))
        row = cursor.fetchone()
        return row[0] if row else None


# =============================================================================
# MODO AGÉNTICO - GESTIÓN DE JOBS DE MISIÓN
# =============================================================================

def add_mission_job(job_id: str, mission_id: str, objective_id: int, command: str) -> int:
    """
    Registra un job en background asociado a una misión/objetivo.
    """
    now = datetime.utcnow().isoformat()
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO mission_jobs (job_id, mission_id, objective_id, command, status, started_at)
            VALUES (?, ?, ?, ?, 'RUNNING', ?)
        """, (job_id, mission_id, objective_id, command, now))
        conn.commit()
        
        print(f"🚀 Mission job registrado: {job_id[:8]}... para objetivo {objective_id}")
        return cursor.lastrowid


def complete_mission_job(job_id: str, status: str = 'COMPLETED') -> bool:
    """
    Marca un job de misión como completado.
    """
    now = datetime.utcnow().isoformat()
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE mission_jobs SET status = ?, completed_at = ?
            WHERE job_id = ?
        """, (status, now, job_id))
        conn.commit()
        return cursor.rowcount > 0


def get_running_mission_jobs(mission_id: str = None) -> List[Dict[str, Any]]:
    """
    Obtiene jobs de misión en ejecución.
    Si mission_id es None, devuelve todos los jobs running.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        
        if mission_id:
            cursor.execute("""
                SELECT mj.*, o.task as objective_task
                FROM mission_jobs mj
                JOIN objectives o ON o.id = mj.objective_id
                WHERE mj.mission_id = ? AND mj.status = 'RUNNING'
            """, (mission_id,))
        else:
            cursor.execute("""
                SELECT mj.*, o.task as objective_task
                FROM mission_jobs mj
                JOIN objectives o ON o.id = mj.objective_id
                WHERE mj.status = 'RUNNING'
            """)
        
        return [dict(row) for row in cursor.fetchall()]


def get_mission_jobs(mission_id: str) -> List[Dict[str, Any]]:
    """
    Obtiene todos los jobs de una misión (cualquier estado).
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT mj.*, o.task as objective_task
            FROM mission_jobs mj
            JOIN objectives o ON o.id = mj.objective_id
            WHERE mj.mission_id = ?
            ORDER BY mj.started_at DESC
        """, (mission_id,))
        return [dict(row) for row in cursor.fetchall()]


# =============================================================================
# SPRINT 3: SISTEMA DE APROBACIÓN Y AUDITORÍA
# =============================================================================

def update_objective_approval(
    objective_id: int, 
    requires_approval: bool,
    approval_status: Optional[str] = None,
    pending_command: Optional[str] = None
) -> bool:
    """
    Actualiza el estado de aprobación de un objetivo.
    
    Args:
        objective_id: ID del objetivo
        requires_approval: Si requiere aprobación
        approval_status: Estado de aprobación (AWAITING_AUTHORIZATION, APPROVED, REJECTED)
        pending_command: Comando pendiente de aprobación
    
    Returns:
        True si se actualizó correctamente
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE objectives 
            SET requires_approval = ?,
                approval_status = ?,
                pending_command = ?
            WHERE id = ?
        """, (1 if requires_approval else 0, approval_status, pending_command, objective_id))
        conn.commit()
        
        if approval_status:
            print(f"🔐 Objetivo {objective_id} → approval_status={approval_status}")
        return cursor.rowcount > 0


def get_pending_approval_objectives(conversation_id: str = None) -> List[Dict[str, Any]]:
    """
    Obtiene objetivos pendientes de aprobación.
    
    Args:
        conversation_id: Filtrar por conversación (opcional)
    
    Returns:
        Lista de objetivos con estado AWAITING_AUTHORIZATION
    """
    with get_db() as conn:
        cursor = conn.cursor()
        
        if conversation_id:
            cursor.execute("""
                SELECT o.*, m.goal as mission_goal, m.conversation_id
                FROM objectives o
                JOIN missions m ON m.id = o.mission_id
                WHERE o.approval_status = 'AWAITING_AUTHORIZATION'
                  AND m.conversation_id = ?
                ORDER BY o.id DESC
            """, (conversation_id,))
        else:
            cursor.execute("""
                SELECT o.*, m.goal as mission_goal, m.conversation_id
                FROM objectives o
                JOIN missions m ON m.id = o.mission_id
                WHERE o.approval_status = 'AWAITING_AUTHORIZATION'
                ORDER BY o.id DESC
            """)
        
        return [dict(row) for row in cursor.fetchall()]


def approve_objective_command(objective_id: int, approved: bool, approved_by: str = "user") -> Dict[str, Any]:
    """
    Aprueba o rechaza un comando pendiente.
    
    Args:
        objective_id: ID del objetivo
        approved: True para aprobar, False para rechazar
        approved_by: Identificador de quién aprobó
    
    Returns:
        Dict con el comando y el nuevo estado
    """
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Obtener el comando pendiente Y el conversation_id de la misión
        cursor.execute("""
            SELECT o.pending_command, o.mission_id, o.task, m.conversation_id
            FROM objectives o
            JOIN missions m ON m.id = o.mission_id
            WHERE o.id = ? AND o.approval_status = 'AWAITING_AUTHORIZATION'
        """, (objective_id,))
        row = cursor.fetchone()
        
        if not row:
            return {"error": "No pending command found or already processed"}
        
        pending_command = row['pending_command']
        mission_id = row['mission_id']
        conversation_id = row['conversation_id']
        
        if approved:
            # Marcar como aprobado
            cursor.execute("""
                UPDATE objectives 
                SET approval_status = 'APPROVED',
                    status = 'IN_PROGRESS'
                WHERE id = ?
            """, (objective_id,))
            print(f"✅ Objetivo {objective_id} APROBADO por {approved_by}")
            
            new_status = "APPROVED"
        else:
            # Marcar como rechazado y saltar el objetivo
            cursor.execute("""
                UPDATE objectives 
                SET approval_status = 'REJECTED',
                    status = 'SKIPPED',
                    result_summary = 'Comando rechazado por el usuario',
                    completed_at = ?
                WHERE id = ?
            """, (datetime.utcnow().isoformat(), objective_id))
            print(f"❌ Objetivo {objective_id} RECHAZADO por {approved_by}")
            
            new_status = "REJECTED"
        
        conn.commit()
        
        return {
            "objective_id": objective_id,
            "command": pending_command,
            "status": new_status,
            "mission_id": mission_id,
            "conversation_id": conversation_id  # Añadido para poder reanudar
        }


# =============================================================================
# AUDITORÍA DE COMANDOS
# =============================================================================

def add_audit_log(
    conversation_id: str,
    command: str,
    risk_level: str,
    requires_approval: bool,
    reason: str,
    mission_id: Optional[str] = None,
    objective_id: Optional[int] = None,
    status: str = "PENDING"
) -> int:
    """
    Añade un registro de auditoría para un comando.
    
    Returns:
        ID del registro de auditoría
    """
    now = datetime.utcnow().isoformat()
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO command_audit 
            (conversation_id, mission_id, objective_id, command, risk_level, 
             requires_approval, reason, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (conversation_id, mission_id, objective_id, command, risk_level,
              1 if requires_approval else 0, reason, status, now))
        conn.commit()
        
        audit_id = cursor.lastrowid
        
        # Log según el riesgo
        risk_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢", "safe": "✅"}
        emoji = risk_emoji.get(risk_level, "⚪")
        print(f"{emoji} Audit #{audit_id}: {command[:50]}... ({risk_level})")
        
        return audit_id


def update_audit_log(
    audit_id: int,
    status: str,
    result_summary: Optional[str] = None,
    approved_by: Optional[str] = None
) -> bool:
    """
    Actualiza un registro de auditoría con el resultado.
    
    Args:
        audit_id: ID del registro
        status: Nuevo estado (EXECUTED, APPROVED, REJECTED, FAILED)
        result_summary: Resumen del resultado (opcional)
        approved_by: Quién aprobó (si aplica)
    
    Returns:
        True si se actualizó
    """
    now = datetime.utcnow().isoformat()
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE command_audit
            SET status = ?,
                result_summary = ?,
                approved_by = ?,
                executed_at = ?
            WHERE id = ?
        """, (status, result_summary, approved_by, now, audit_id))
        conn.commit()
        
        return cursor.rowcount > 0


def get_audit_logs(
    conversation_id: Optional[str] = None,
    mission_id: Optional[str] = None,
    status: Optional[str] = None,
    objective_id: Optional[int] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Obtiene registros de auditoría con filtros opcionales.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        
        query = "SELECT * FROM command_audit WHERE 1=1"
        params = []
        
        if conversation_id:
            query += " AND conversation_id = ?"
            params.append(conversation_id)
        if mission_id:
            query += " AND mission_id = ?"
            params.append(mission_id)
        if status:
            query += " AND status = ?"
            params.append(status)
        if objective_id:
            query += " AND objective_id = ?"
            params.append(objective_id)
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def get_audit_by_objective(objective_id: int) -> Optional[Dict[str, Any]]:
    """
    Obtiene el registro de auditoría más reciente para un objetivo.
    
    Útil para actualizar el audit cuando se aprueba/rechaza un comando.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM command_audit 
            WHERE objective_id = ? 
            ORDER BY created_at DESC 
            LIMIT 1
        """, (objective_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_audit_statistics(conversation_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Obtiene estadísticas de auditoría.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        
        where_clause = "WHERE conversation_id = ?" if conversation_id else ""
        params = [conversation_id] if conversation_id else []
        
        # Total de comandos
        cursor.execute(f"SELECT COUNT(*) as total FROM command_audit {where_clause}", params)
        total = cursor.fetchone()['total']
        
        # Por estado
        cursor.execute(f"""
            SELECT status, COUNT(*) as count 
            FROM command_audit {where_clause}
            GROUP BY status
        """, params)
        by_status = {row['status']: row['count'] for row in cursor.fetchall()}
        
        # Por riesgo
        cursor.execute(f"""
            SELECT risk_level, COUNT(*) as count 
            FROM command_audit {where_clause}
            GROUP BY risk_level
        """, params)
        by_risk = {row['risk_level']: row['count'] for row in cursor.fetchall()}
        
        # Comandos que requirieron aprobación
        cursor.execute(f"""
            SELECT COUNT(*) as count 
            FROM command_audit 
            WHERE requires_approval = 1 {' AND conversation_id = ?' if conversation_id else ''}
        """, params if conversation_id else [])
        required_approval = cursor.fetchone()['count']
        
        return {
            "total": total,
            "by_status": by_status,
            "by_risk": by_risk,
            "required_approval": required_approval,
            "approval_rate": by_status.get("APPROVED", 0) / required_approval if required_approval > 0 else 0
        }
