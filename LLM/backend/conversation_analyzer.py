#!/usr/bin/env python3
"""
conversation_analyzer.py - Analizador de conversaciones para documentación de seguridad.

Uso:
    - Sin argumentos: Abre interfaz Tkinter con lista de conversaciones
    - Con argumento: python conversation_analyzer.py <conversation_id> 
                     Genera CSV directamente sin interfaz

Genera un CSV con:
    1. Estadísticas de riesgo (TOTAL CRITICAL, HIGH, etc.)
    2. Estadísticas de uso de comandos
    3. Todos los comandos clasificados por nivel de riesgo
    4. Suma de intervenciones de usuario
"""

import sqlite3
import csv
import sys
import re
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter
from enum import Enum

# Ruta de la base de datos (misma que usa el server)
DB_PATH = Path(__file__).parent / "chat_history.db"


# =============================================================================
# SISTEMA DE ANÁLISIS DE RIESGO (Copiado de security.py para independencia)
# =============================================================================

class RiskLevel(Enum):
    """Niveles de riesgo para comandos."""
    SAFE = "safe"           # Comandos de reconocimiento pasivo
    LOW = "low"             # Escaneos ligeros
    MEDIUM = "medium"       # Enumeración activa
    HIGH = "high"           # Exploits, brute-force
    CRITICAL = "critical"   # Shells reversos, post-explotación


# Mapeo de niveles a valores numéricos para ordenación
RISK_TO_NUMBER = {
    "critical": 5,
    "high": 4,
    "medium": 3,
    "low": 2,
    "safe": 1
}

# Patrones de comandos peligrosos
DANGEROUS_PATTERNS: List[Tuple[str, RiskLevel, str]] = [
    # === CRITICAL: Requieren aprobación SIEMPRE ===
    (r"msfconsole", RiskLevel.CRITICAL, "Metasploit Framework"),
    (r"msfvenom", RiskLevel.CRITICAL, "Generador de payloads Metasploit"),
    (r"exploit/", RiskLevel.CRITICAL, "Módulo de exploit"),
    (r"nc\s+.*-e", RiskLevel.CRITICAL, "Netcat reverse shell"),
    (r"nc\s+.*-c", RiskLevel.CRITICAL, "Netcat command execution"),
    (r"bash\s+-i\s+>&", RiskLevel.CRITICAL, "Bash reverse shell"),
    (r"/dev/tcp/", RiskLevel.CRITICAL, "Bash TCP redirect (shell)"),
    (r"python.*socket.*connect", RiskLevel.CRITICAL, "Python reverse shell"),
    (r"rm\s+-rf\s+/", RiskLevel.CRITICAL, "Eliminación recursiva de sistema"),
    (r"mkfs\.", RiskLevel.CRITICAL, "Formateo de disco"),
    (r"dd\s+if=.*of=/dev/", RiskLevel.CRITICAL, "Escritura directa a dispositivo"),
    
    # === HIGH: Requieren aprobación por defecto ===
    (r"hydra", RiskLevel.HIGH, "Brute-force de credenciales"),
    (r"medusa", RiskLevel.HIGH, "Brute-force paralelo"),
    (r"john\s+", RiskLevel.HIGH, "Password cracking"),
    (r"hashcat", RiskLevel.HIGH, "Password cracking GPU"),
    (r"sqlmap.*--dump", RiskLevel.HIGH, "Dumping de base de datos"),
    (r"sqlmap.*--os-shell", RiskLevel.HIGH, "Shell via SQL injection"),
    (r"sqlmap.*--os-pwn", RiskLevel.HIGH, "Meterpreter via SQLi"),
    (r"--script.*exploit", RiskLevel.HIGH, "Nmap exploit scripts"),
    (r"--script.*vuln", RiskLevel.HIGH, "Nmap vulnerability scripts"),
    (r"--script.*brute", RiskLevel.HIGH, "Nmap brute-force scripts"),
    (r"wpscan.*--passwords", RiskLevel.HIGH, "WordPress brute-force"),
    (r"responder", RiskLevel.HIGH, "LLMNR/NBT-NS poisoning"),
    (r"bettercap", RiskLevel.HIGH, "Network attacks"),
    (r"ettercap", RiskLevel.HIGH, "ARP spoofing"),
    (r"arpspoof", RiskLevel.HIGH, "ARP spoofing"),
    (r"tcpdump\s+-w", RiskLevel.HIGH, "Captura de tráfico a archivo"),
    (r"impacket", RiskLevel.HIGH, "Herramientas de red SMB/Kerberos"),
    (r"crackmapexec", RiskLevel.HIGH, "Post-explotación AD"),
    (r"evil-winrm", RiskLevel.HIGH, "WinRM shell"),
    (r"psexec", RiskLevel.HIGH, "Remote execution"),
    (r"mimikatz", RiskLevel.HIGH, "Credential extraction"),
    (r"secretsdump", RiskLevel.HIGH, "SAM/LSA secrets dump"),
    
    # === MEDIUM: Advertencia pero se puede ejecutar ===
    (r"nmap\s+.*-sU", RiskLevel.MEDIUM, "UDP scan (lento/ruidoso)"),
    (r"nmap\s+.*-A", RiskLevel.MEDIUM, "Aggressive scan"),
    (r"nmap\s+.*-T[45]", RiskLevel.MEDIUM, "Fast/Insane timing"),
    (r"nikto", RiskLevel.MEDIUM, "Web vulnerability scanner"),
    (r"gobuster", RiskLevel.MEDIUM, "Directory brute-force"),
    (r"dirb\s+", RiskLevel.MEDIUM, "Directory brute-force"),
    (r"wfuzz", RiskLevel.MEDIUM, "Web fuzzer"),
    (r"ffuf\s+", RiskLevel.MEDIUM, "Fast web fuzzer"),
    (r"feroxbuster", RiskLevel.MEDIUM, "Directory brute-force"),
    (r"sqlmap\s+", RiskLevel.MEDIUM, "SQL injection testing"),
    (r"nuclei\s+", RiskLevel.MEDIUM, "Vulnerability scanner"),
    (r"searchsploit", RiskLevel.MEDIUM, "Exploit database search"),
]

# Comandos seguros (whitelist)
SAFE_PATTERNS: List[str] = [
    r"^whoami$",
    r"^id$",
    r"^pwd$",
    r"^ls\s+",
    r"^cat\s+",
    r"^head\s+",
    r"^tail\s+",
    r"^grep\s+",
    r"^find\s+",
    r"^echo\s+",
    r"^ping\s+",
    r"^host\s+",
    r"^dig\s+",
    r"^nslookup\s+",
    r"^curl\s+.*-I",
    r"^curl\s+.*--head",
    r"^wget\s+.*-q",
    r"^nmap\s+.*-sn",
    r"^nmap\s+.*-Pn\s+-F",
]


def analyze_command(command: str) -> Dict:
    """Analiza un comando y determina su nivel de riesgo."""
    command = command.strip()
    
    # Verificar whitelist
    for safe_pattern in SAFE_PATTERNS:
        if re.search(safe_pattern, command, re.IGNORECASE):
            return {
                "risk_level": RiskLevel.SAFE.value,
                "risk_number": RISK_TO_NUMBER["safe"],
                "matched_patterns": [],
                "reason": "Comando seguro (whitelist)"
            }
    
    # Buscar patrones peligrosos
    matched = []
    max_risk = RiskLevel.LOW
    reasons = []
    
    for pattern, risk_level, description in DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            matched.append({
                "pattern": pattern,
                "risk": risk_level.value,
                "description": description
            })
            reasons.append(description)
            
            if risk_level.value == RiskLevel.CRITICAL.value:
                max_risk = RiskLevel.CRITICAL
            elif risk_level.value == RiskLevel.HIGH.value and max_risk != RiskLevel.CRITICAL:
                max_risk = RiskLevel.HIGH
            elif risk_level.value == RiskLevel.MEDIUM.value and max_risk not in [RiskLevel.CRITICAL, RiskLevel.HIGH]:
                max_risk = RiskLevel.MEDIUM
    
    if not matched:
        return {
            "risk_level": RiskLevel.LOW.value,
            "risk_number": RISK_TO_NUMBER["low"],
            "matched_patterns": [],
            "reason": "Sin patrones de riesgo detectados"
        }
    
    return {
        "risk_level": max_risk.value,
        "risk_number": RISK_TO_NUMBER[max_risk.value],
        "matched_patterns": matched,
        "reason": ", ".join(reasons)
    }


# =============================================================================
# FUNCIONES DE BASE DE DATOS
# =============================================================================

def get_db_connection():
    """Obtiene conexión a la base de datos."""
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Base de datos no encontrada: {DB_PATH}")
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def list_conversations() -> List[Dict]:
    """Lista todas las conversaciones con info del último modelo usado."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Obtener conversaciones con el último mensaje assistant y su modelo
    cursor.execute("""
        SELECT 
            c.id,
            c.title,
            c.created_at,
            c.updated_at,
            (
                SELECT m.model_used 
                FROM messages m 
                WHERE m.conversation_id = c.id 
                  AND m.role = 'assistant' 
                  AND m.model_used IS NOT NULL
                ORDER BY m.created_at DESC 
                LIMIT 1
            ) as last_model,
            (SELECT COUNT(*) FROM messages WHERE conversation_id = c.id) as message_count
        FROM conversations c
        ORDER BY c.updated_at DESC
    """)
    
    conversations = []
    for row in cursor.fetchall():
        conversations.append({
            "id": row["id"],
            "title": row["title"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "last_model": row["last_model"] or "Sin modelo",
            "message_count": row["message_count"]
        })
    
    conn.close()
    return conversations


def get_conversation(conv_id: str) -> Optional[Dict]:
    """Obtiene metadatos de una conversación."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, title, system_prompt, active_leaf_id, created_at, updated_at
        FROM conversations WHERE id = ?
    """, (conv_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    return dict(row) if row else None


def reconstruct_thread(leaf_id: int) -> List[Dict]:
    """Reconstruye la rama desde un mensaje hoja hasta la raíz."""
    thread = []
    current_id = leaf_id
    
    conn = get_db_connection()
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
        thread.insert(0, msg)
        current_id = msg['parent_id']
    
    conn.close()
    return thread


def get_thread_for_conversation(conv_id: str) -> List[Dict]:
    """Obtiene el thread activo de una conversación."""
    conv = get_conversation(conv_id)
    if not conv or not conv.get("active_leaf_id"):
        # Si no hay active_leaf_id, buscar el último mensaje
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM messages 
            WHERE conversation_id = ? 
            ORDER BY created_at DESC 
            LIMIT 1
        """, (conv_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return reconstruct_thread(row["id"])
        return []
    
    return reconstruct_thread(conv["active_leaf_id"])


# =============================================================================
# EXTRACCIÓN Y ANÁLISIS DE COMANDOS
# =============================================================================

def extract_commands_from_thread(thread: List[Dict]) -> List[Dict]:
    """
    Extrae todos los comandos ejecutados del thread.
    Los comandos están en tool_calls de mensajes assistant 
    y en content de mensajes tool.
    """
    commands = []
    
    for msg in thread:
        role = msg.get("role", "")
        
        # Extraer de tool_calls (assistant pidiendo ejecutar)
        if role == "assistant" and msg.get("tool_calls"):
            try:
                tool_calls = msg["tool_calls"]
                if isinstance(tool_calls, str):
                    tool_calls = json.loads(tool_calls)
                
                for tc in tool_calls:
                    func = tc.get("function", {})
                    func_name = func.get("name", "")
                    
                    # Solo analizar comandos de terminal
                    if func_name in ["execute_command", "run_command", "bash", "terminal", "shell"]:
                        args = func.get("arguments", {})
                        if isinstance(args, str):
                            args = json.loads(args)
                        
                        cmd = args.get("command", args.get("cmd", ""))
                        if cmd:
                            analysis = analyze_command(cmd)
                            commands.append({
                                "command": cmd,
                                "tool_name": func_name,
                                "risk_level": analysis["risk_level"],
                                "risk_number": analysis["risk_number"],
                                "reason": analysis["reason"],
                                "message_id": msg.get("id"),
                                "timestamp": msg.get("created_at")
                            })
            except (json.JSONDecodeError, TypeError, KeyError):
                pass
        
        # También buscar comandos en el contenido de mensajes tool
        # que podrían tener el comando ejecutado
        if role == "tool" and msg.get("content"):
            content = msg["content"]
            # Buscar patrones de comandos en la salida
            # Típicamente el contenido empieza con el comando o tiene formato específico
            lines = content.split('\n')
            if lines and lines[0].startswith('$'):
                cmd = lines[0][1:].strip()
                if cmd:
                    analysis = analyze_command(cmd)
                    commands.append({
                        "command": cmd,
                        "tool_name": "terminal_output",
                        "risk_level": analysis["risk_level"],
                        "risk_number": analysis["risk_number"],
                        "reason": analysis["reason"],
                        "message_id": msg.get("id"),
                        "timestamp": msg.get("created_at")
                    })
    
    return commands


def count_user_interventions(thread: List[Dict]) -> int:
    """Cuenta las intervenciones de usuario en el thread."""
    return sum(1 for msg in thread if msg.get("role") == "user")


# =============================================================================
# GENERACIÓN DE CSV
# =============================================================================

def generate_csv(conv_id: str, output_path: str = None) -> str:
    """
    Genera el CSV de análisis de seguridad para una conversación.
    
    Returns:
        Ruta del archivo CSV generado
    """
    # Obtener conversación
    conv = get_conversation(conv_id)
    if not conv:
        raise ValueError(f"Conversación no encontrada: {conv_id}")
    
    # Obtener thread
    thread = get_thread_for_conversation(conv_id)
    if not thread:
        raise ValueError(f"No hay mensajes en la conversación: {conv_id}")
    
    # Extraer comandos
    commands = extract_commands_from_thread(thread)
    
    # Contar intervenciones de usuario
    user_interventions = count_user_interventions(thread)
    
    # Estadísticas de riesgo
    risk_counts = Counter(cmd["risk_level"] for cmd in commands)
    
    # Estadísticas de uso de comandos (comando base, sin argumentos)
    command_usage = Counter()
    for cmd in commands:
        # Extraer comando base (primera palabra)
        base_cmd = cmd["command"].split()[0] if cmd["command"] else "unknown"
        command_usage[base_cmd] += 1
    
    # Ordenar comandos por nivel de riesgo (mayor a menor)
    commands_sorted = sorted(commands, key=lambda x: x["risk_number"], reverse=True)
    
    # Generar nombre de archivo
    if not output_path:
        safe_title = re.sub(r'[^\w\s-]', '', conv["title"])[:50]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"security_analysis_{safe_title}_{timestamp}.csv"
    
    # Escribir CSV (utf-8-sig para compatibilidad con Excel)
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f, delimiter=';')
        
        # === SECCIÓN 1: CABECERA ===
        writer.writerow(["ANÁLISIS DE SEGURIDAD - CLASIFICACIÓN DE COMANDOS POR RIESGO"])
        writer.writerow(["Conversación", conv["title"]])
        writer.writerow(["ID", conv_id])
        writer.writerow(["Fecha análisis", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
        writer.writerow([])
        
        # === SECCIÓN 2: ESTADÍSTICAS DE RIESGO ===
        writer.writerow(["=== ESTADÍSTICAS DE RIESGO ==="])
        writer.writerow(["TOTAL CRITICAL", risk_counts.get("critical", 0)])
        writer.writerow(["TOTAL HIGH", risk_counts.get("high", 0)])
        writer.writerow(["TOTAL MEDIUM", risk_counts.get("medium", 0)])
        writer.writerow(["TOTAL LOW", risk_counts.get("low", 0)])
        writer.writerow(["TOTAL SAFE", risk_counts.get("safe", 0)])
        writer.writerow(["TOTAL COMANDOS", len(commands)])
        writer.writerow([])
        
        # === SECCIÓN 3: ESTADÍSTICAS DE USO DE COMANDOS ===
        writer.writerow(["=== ESTADÍSTICAS DE USO DE COMANDOS ==="])
        writer.writerow(["Comando", "Veces usado"])
        for cmd_name, count in command_usage.most_common():
            writer.writerow([cmd_name, count])
        writer.writerow([])
        
        # === SECCIÓN 4: INTERVENCIONES DE USUARIO ===
        writer.writerow(["=== INTERVENCIONES DE USUARIO ==="])
        writer.writerow(["Total mensajes usuario", user_interventions])
        writer.writerow(["Total mensajes en thread", len(thread)])
        writer.writerow([])
        
        # === SECCIÓN 5: DETALLE DE COMANDOS ===
        writer.writerow(["=== DETALLE DE COMANDOS POR RIESGO ==="])
        writer.writerow(["Comando", "Nivel Riesgo (Número)", "Nivel Riesgo", "Razón"])
        
        for cmd in commands_sorted:
            # Escapar el comando para CSV
            cmd_text = cmd["command"].replace('\n', ' ').replace('\r', '')
            writer.writerow([
                cmd_text,
                cmd["risk_number"],
                cmd["risk_level"].upper(),
                cmd["reason"]
            ])
    
    print(f"✅ CSV generado: {output_path}")
    return output_path


# =============================================================================
# MÉTRICAS DE AUTONOMÍA
# =============================================================================

def calculate_autonomy_metrics(conv_id: str) -> Dict:
    """
    Calcula métricas de autonomía para una conversación.
    
    Returns:
        Dict con:
        - user_messages: Total mensajes del usuario
        - assistant_messages: Total mensajes del asistente
        - tool_messages: Total mensajes de tools
        - autonomy_percentage: % de mensajes del asistente sobre el total (excluyendo system)
        - avg_wait_time_seconds: Tiempo medio de espera entre mensaje user y respuesta assistant
        - wait_times: Lista de tiempos de espera individuales
        - approvals_requested: Número de aprobaciones solicitadas (si aplica)
        - model_used: Modelo(s) usado(s) en la conversación
    """
    conv = get_conversation(conv_id)
    if not conv:
        raise ValueError(f"Conversación no encontrada: {conv_id}")
    
    thread = get_thread_for_conversation(conv_id)
    if not thread:
        raise ValueError(f"No hay mensajes en la conversación: {conv_id}")
    
    # Contadores de mensajes
    user_count = 0
    assistant_count = 0
    tool_count = 0
    system_count = 0
    
    # Tiempos de espera
    wait_times = []
    last_user_time = None
    
    # Modelos usados
    models_used = set()
    
    # Aprobaciones (buscamos patrones en los mensajes)
    approvals_count = 0
    
    for msg in thread:
        role = msg.get("role", "")
        created_at = msg.get("created_at", "")
        content = msg.get("content", "") or ""
        model = msg.get("model_used")
        
        if role == "system":
            system_count += 1
        elif role == "user":
            user_count += 1
            # Guardar timestamp para calcular tiempo de espera
            if created_at:
                try:
                    last_user_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                except:
                    try:
                        last_user_time = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S.%f")
                    except:
                        try:
                            last_user_time = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S")
                        except:
                            last_user_time = None
        elif role == "assistant":
            assistant_count += 1
            if model:
                models_used.add(model)
            
            # Calcular tiempo de espera desde último mensaje de usuario
            if last_user_time and created_at:
                try:
                    assistant_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                except:
                    try:
                        assistant_time = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S.%f")
                    except:
                        try:
                            assistant_time = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S")
                        except:
                            assistant_time = None
                
                if assistant_time:
                    delta = (assistant_time - last_user_time).total_seconds()
                    if delta > 0:  # Solo contar tiempos positivos
                        wait_times.append(delta)
                    last_user_time = None  # Reset para evitar doble conteo
            
            # Detectar si hubo solicitud de aprobación
            if "AWAITING_AUTHORIZATION" in content or "REQUIERE APROBACIÓN" in content:
                approvals_count += 1
                
        elif role == "tool":
            tool_count += 1
            # También buscar aprobaciones en tool responses
            if "approval" in content.lower() or "aprobación" in content.lower():
                pass  # Ya contado arriba
    
    # Calcular porcentaje de autonomía
    # Autonomía = mensajes del asistente / (mensajes asistente + mensajes usuario)
    # Excluimos system y tool porque son generados automáticamente
    total_interaction = user_count + assistant_count
    if total_interaction > 0:
        # Fórmula: cuánto trabaja el asistente por cada intervención del usuario
        autonomy_pct = (assistant_count / total_interaction) * 100
    else:
        autonomy_pct = 0
    
    # Tiempo medio de espera
    avg_wait_time = sum(wait_times) / len(wait_times) if wait_times else 0
    
    return {
        "conversation_id": conv_id,
        "conversation_title": conv["title"],
        "user_messages": user_count,
        "assistant_messages": assistant_count,
        "tool_messages": tool_count,
        "system_messages": system_count,
        "total_messages": len(thread),
        "autonomy_percentage": round(autonomy_pct, 2),
        "avg_wait_time_seconds": round(avg_wait_time, 2),
        "wait_times": wait_times,
        "min_wait_time": round(min(wait_times), 2) if wait_times else 0,
        "max_wait_time": round(max(wait_times), 2) if wait_times else 0,
        "approvals_requested": approvals_count,
        "models_used": list(models_used),
        "primary_model": list(models_used)[0] if models_used else "Desconocido"
    }


def generate_autonomy_csv(conv_id: str, output_path: str = None) -> str:
    """
    Genera un CSV con métricas de autonomía para una conversación.
    
    Returns:
        Ruta del archivo CSV generado
    """
    metrics = calculate_autonomy_metrics(conv_id)
    conv = get_conversation(conv_id)
    
    # Generar nombre de archivo
    if not output_path:
        safe_title = re.sub(r'[^\w\s-]', '', conv["title"])[:50]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"autonomy_metrics_{safe_title}_{timestamp}.csv"
    
    # Escribir CSV
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f, delimiter=';')
        
        # === CABECERA ===
        writer.writerow(["MÉTRICAS DE AUTONOMÍA OPERATIVA"])
        writer.writerow(["Conversación", metrics["conversation_title"]])
        writer.writerow(["ID", conv_id])
        writer.writerow(["Fecha análisis", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
        writer.writerow([])
        
        # === MODELO ===
        writer.writerow(["=== MODELO ==="])
        writer.writerow(["Modelo principal", metrics["primary_model"]])
        writer.writerow(["Modelos usados", ", ".join(metrics["models_used"])])
        writer.writerow([])
        
        # === CONTEO DE MENSAJES ===
        writer.writerow(["=== CONTEO DE MENSAJES ==="])
        writer.writerow(["Mensajes del usuario", metrics["user_messages"]])
        writer.writerow(["Mensajes del asistente", metrics["assistant_messages"]])
        writer.writerow(["Mensajes de tools", metrics["tool_messages"]])
        writer.writerow(["Total mensajes", metrics["total_messages"]])
        writer.writerow([])
        
        # === AUTONOMÍA ===
        writer.writerow(["=== AUTONOMÍA ==="])
        writer.writerow(["Autonomía (%)", f"{metrics['autonomy_percentage']}%"])
        writer.writerow(["Ratio asistente/usuario", 
                        f"{metrics['assistant_messages']/metrics['user_messages']:.2f}" if metrics['user_messages'] > 0 else "N/A"])
        writer.writerow(["Aprobaciones solicitadas", metrics["approvals_requested"]])
        writer.writerow([])
        
        # === TIEMPOS DE ESPERA ===
        writer.writerow(["=== TIEMPOS DE ESPERA ==="])
        writer.writerow(["Tiempo medio de espera (s)", f"{metrics['avg_wait_time_seconds']} s"])
        writer.writerow(["Tiempo mínimo (s)", f"{metrics['min_wait_time']} s"])
        writer.writerow(["Tiempo máximo (s)", f"{metrics['max_wait_time']} s"])
        writer.writerow(["Número de mediciones", len(metrics["wait_times"])])
        writer.writerow([])
        
        # === DATOS PARA TABLA 6.8 ===
        writer.writerow(["=== DATOS PARA TABLA 6.8 (Métricas de Autonomía Operativa) ==="])
        writer.writerow(["Modelo", "Autonomía (%)", "Aprobaciones", "T. Espera Medio (s)"])
        writer.writerow([
            metrics["primary_model"],
            f"{metrics['autonomy_percentage']}%",
            metrics["approvals_requested"],
            f"{metrics['avg_wait_time_seconds']} s"
        ])
        writer.writerow([])
        
        # === DETALLE DE TIEMPOS DE ESPERA ===
        if metrics["wait_times"]:
            writer.writerow(["=== DETALLE DE TIEMPOS DE ESPERA ==="])
            writer.writerow(["#", "Tiempo (s)"])
            for i, wait_time in enumerate(metrics["wait_times"], 1):
                writer.writerow([i, f"{wait_time:.2f}"])
    
    print(f"✅ CSV de autonomía generado: {output_path}")
    return output_path


# =============================================================================
# INTERFAZ TKINTER
# =============================================================================

def run_gui():
    """Ejecuta la interfaz gráfica Tkinter."""
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
    
    class ConversationAnalyzerGUI:
        def __init__(self, root):
            self.root = root
            self.root.title("Analizador de Conversaciones - Clasificación de Riesgo")
            self.root.geometry("900x600")
            
            # Frame principal
            main_frame = ttk.Frame(root, padding="10")
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Título
            title_label = ttk.Label(
                main_frame, 
                text="📊 Analizador de Seguridad de Conversaciones",
                font=('Helvetica', 14, 'bold')
            )
            title_label.pack(pady=(0, 10))
            
            # Info
            info_label = ttk.Label(
                main_frame,
                text="Selecciona una conversación para generar el CSV de análisis de comandos por riesgo",
                font=('Helvetica', 10)
            )
            info_label.pack(pady=(0, 10))
            
            # Frame para la lista
            list_frame = ttk.Frame(main_frame)
            list_frame.pack(fill=tk.BOTH, expand=True)
            
            # Treeview para conversaciones
            columns = ("title", "model", "messages", "updated")
            self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=20)
            
            # Configurar columnas
            self.tree.heading("title", text="Título")
            self.tree.heading("model", text="Último Modelo")
            self.tree.heading("messages", text="Mensajes")
            self.tree.heading("updated", text="Última actualización")
            
            self.tree.column("title", width=350)
            self.tree.column("model", width=200)
            self.tree.column("messages", width=80, anchor=tk.CENTER)
            self.tree.column("updated", width=180)
            
            # Scrollbar
            scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
            self.tree.configure(yscrollcommand=scrollbar.set)
            
            self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # Bind doble click
            self.tree.bind("<Double-1>", self.on_conversation_select)
            
            # Frame de botones
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X, pady=(10, 0))
            
            # Botón de refrescar
            refresh_btn = ttk.Button(
                button_frame, 
                text="🔄 Refrescar Lista",
                command=self.load_conversations
            )
            refresh_btn.pack(side=tk.LEFT, padx=5)
            
            # Botón de generar
            generate_btn = ttk.Button(
                button_frame,
                text="📄 CSV Seguridad",
                command=self.generate_selected
            )
            generate_btn.pack(side=tk.LEFT, padx=5)
            
            # Botón de métricas de autonomía
            autonomy_btn = ttk.Button(
                button_frame,
                text="📊 CSV Autonomía",
                command=self.generate_autonomy_selected
            )
            autonomy_btn.pack(side=tk.LEFT, padx=5)
            
            # Botón de salir
            exit_btn = ttk.Button(
                button_frame,
                text="❌ Salir",
                command=root.quit
            )
            exit_btn.pack(side=tk.RIGHT, padx=5)
            
            # Almacenar IDs de conversaciones
            self.conversation_ids = {}
            
            # Cargar conversaciones
            self.load_conversations()
        
        def load_conversations(self):
            """Carga las conversaciones en el treeview."""
            # Limpiar lista
            for item in self.tree.get_children():
                self.tree.delete(item)
            self.conversation_ids.clear()
            
            try:
                conversations = list_conversations()
                
                for conv in conversations:
                    item_id = self.tree.insert("", tk.END, values=(
                        conv["title"],
                        conv["last_model"],
                        conv["message_count"],
                        conv["updated_at"]
                    ))
                    self.conversation_ids[item_id] = conv["id"]
                
                if not conversations:
                    messagebox.showinfo(
                        "Sin conversaciones",
                        "No hay conversaciones en la base de datos."
                    )
            
            except FileNotFoundError as e:
                messagebox.showerror("Error", str(e))
            except Exception as e:
                messagebox.showerror("Error", f"Error al cargar conversaciones: {e}")
        
        def on_conversation_select(self, event):
            """Maneja el doble click en una conversación."""
            self.generate_selected()
        
        def generate_selected(self):
            """Genera CSV para la conversación seleccionada."""
            selection = self.tree.selection()
            if not selection:
                messagebox.showwarning(
                    "Sin selección",
                    "Por favor, selecciona una conversación."
                )
                return
            
            item_id = selection[0]
            conv_id = self.conversation_ids.get(item_id)
            
            if not conv_id:
                messagebox.showerror("Error", "ID de conversación no encontrado.")
                return
            
            # Preguntar dónde guardar
            output_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title="Guardar análisis de seguridad"
            )
            
            if not output_path:
                return
            
            try:
                generate_csv(conv_id, output_path)
                messagebox.showinfo(
                    "Éxito",
                    f"CSV generado correctamente:\n{output_path}"
                )
            except Exception as e:
                messagebox.showerror(
                    "Error",
                    f"Error al generar CSV: {e}"
                )
        
        def generate_autonomy_selected(self):
            """Genera CSV de métricas de autonomía para la conversación seleccionada."""
            selection = self.tree.selection()
            if not selection:
                messagebox.showwarning(
                    "Sin selección",
                    "Por favor, selecciona una conversación."
                )
                return
            
            item_id = selection[0]
            conv_id = self.conversation_ids.get(item_id)
            
            if not conv_id:
                messagebox.showerror("Error", "ID de conversación no encontrado.")
                return
            
            # Preguntar dónde guardar
            output_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title="Guardar métricas de autonomía"
            )
            
            if not output_path:
                return
            
            try:
                generate_autonomy_csv(conv_id, output_path)
                
                # Mostrar resumen rápido
                metrics = calculate_autonomy_metrics(conv_id)
                summary = (
                    f"CSV generado correctamente:\n{output_path}\n\n"
                    f"📊 Resumen:\n"
                    f"• Modelo: {metrics['primary_model']}\n"
                    f"• Autonomía: {metrics['autonomy_percentage']}%\n"
                    f"• Mensajes usuario: {metrics['user_messages']}\n"
                    f"• Mensajes asistente: {metrics['assistant_messages']}\n"
                    f"• T. Espera medio: {metrics['avg_wait_time_seconds']} s\n"
                    f"• Aprobaciones: {metrics['approvals_requested']}"
                )
                messagebox.showinfo("Éxito", summary)
            except Exception as e:
                messagebox.showerror(
                    "Error",
                    f"Error al generar CSV de autonomía: {e}"
                )
    
    # Crear ventana
    root = tk.Tk()
    app = ConversationAnalyzerGUI(root)
    root.mainloop()


# =============================================================================
# MAIN
# =============================================================================

def main():
    """
    Punto de entrada principal.
    
    Uso:
        python conversation_analyzer.py                     # Abre GUI
        python conversation_analyzer.py <conv_id>           # CSV seguridad
        python conversation_analyzer.py <conv_id> <file>    # CSV seguridad con nombre
        python conversation_analyzer.py --autonomy <conv_id>           # CSV autonomía
        python conversation_analyzer.py --autonomy <conv_id> <file>    # CSV autonomía con nombre
    """
    if len(sys.argv) > 1:
        # Modo CLI
        if sys.argv[1] == "--autonomy" or sys.argv[1] == "-a":
            # Modo autonomía
            if len(sys.argv) < 3:
                print("❌ Error: Falta el ID de conversación")
                print("Uso: python conversation_analyzer.py --autonomy <conv_id> [output_file.csv]")
                sys.exit(1)
            
            conv_id = sys.argv[2]
            output_path = sys.argv[3] if len(sys.argv) > 3 else None
            
            try:
                csv_path = generate_autonomy_csv(conv_id, output_path)
                
                # Mostrar resumen
                metrics = calculate_autonomy_metrics(conv_id)
                print(f"\n📊 MÉTRICAS DE AUTONOMÍA")
                print(f"   Modelo: {metrics['primary_model']}")
                print(f"   Autonomía: {metrics['autonomy_percentage']}%")
                print(f"   Mensajes usuario: {metrics['user_messages']}")
                print(f"   Mensajes asistente: {metrics['assistant_messages']}")
                print(f"   T. Espera medio: {metrics['avg_wait_time_seconds']} s")
                print(f"   Aprobaciones: {metrics['approvals_requested']}")
                
            except Exception as e:
                print(f"❌ Error: {e}")
                sys.exit(1)
        else:
            # Modo seguridad (por defecto)
            conv_id = sys.argv[1]
            output_path = sys.argv[2] if len(sys.argv) > 2 else None
            
            try:
                csv_path = generate_csv(conv_id, output_path)
                print(f"CSV generado: {csv_path}")
            except Exception as e:
                print(f"❌ Error: {e}")
                sys.exit(1)
    else:
        # Modo GUI: mostrar interfaz
        run_gui()


if __name__ == "__main__":
    main()
