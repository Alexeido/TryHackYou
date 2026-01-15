"""
security.py - Sistema de seguridad para el modo agéntico.

Sprint 3: Human-in-the-Loop + Control de comandos peligrosos.

Este módulo proporciona:
1. Detección de comandos potencialmente peligrosos
2. Categorización de riesgo
3. Sistema de auditoría
"""

import re
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from enum import Enum


class RiskLevel(Enum):
    """Niveles de riesgo para comandos."""
    SAFE = "safe"           # Comandos de reconocimiento pasivo
    LOW = "low"             # Escaneos ligeros
    MEDIUM = "medium"       # Enumeración activa
    HIGH = "high"           # Exploits, brute-force
    CRITICAL = "critical"   # Shells reversos, post-explotación


# =============================================================================
# PATRONES DE COMANDOS PELIGROSOS
# =============================================================================

# Patrones con sus niveles de riesgo y descripción
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

# Comandos seguros que NUNCA requieren aprobación (whitelist)
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
    r"^curl\s+.*-I",      # Solo headers
    r"^curl\s+.*--head",
    r"^wget\s+.*-q",
    r"^nmap\s+.*-sn",     # Ping scan only
    r"^nmap\s+.*-Pn\s+-F", # Fast scan
]


# =============================================================================
# FUNCIONES DE ANÁLISIS
# =============================================================================

def analyze_command(command: str) -> Dict:
    """
    Analiza un comando y determina su nivel de riesgo.
    
    Args:
        command: Comando a analizar
        
    Returns:
        Dict con:
        - risk_level: Nivel de riesgo (RiskLevel)
        - requires_approval: Si necesita aprobación humana
        - matched_patterns: Lista de patrones que coincidieron
        - reason: Explicación del riesgo
    """
    command = command.strip()
    
    # Primero verificar si está en la whitelist
    for safe_pattern in SAFE_PATTERNS:
        if re.search(safe_pattern, command, re.IGNORECASE):
            return {
                "risk_level": RiskLevel.SAFE.value,
                "requires_approval": False,
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
            
            # Mantener el riesgo más alto encontrado
            if risk_level.value == RiskLevel.CRITICAL.value:
                max_risk = RiskLevel.CRITICAL
            elif risk_level.value == RiskLevel.HIGH.value and max_risk != RiskLevel.CRITICAL:
                max_risk = RiskLevel.HIGH
            elif risk_level.value == RiskLevel.MEDIUM.value and max_risk not in [RiskLevel.CRITICAL, RiskLevel.HIGH]:
                max_risk = RiskLevel.MEDIUM
    
    # Determinar si requiere aprobación
    requires_approval = max_risk in [RiskLevel.CRITICAL, RiskLevel.HIGH]
    
    if not matched:
        return {
            "risk_level": RiskLevel.LOW.value,
            "requires_approval": False,
            "matched_patterns": [],
            "reason": "No se detectaron patrones de riesgo"
        }
    
    return {
        "risk_level": max_risk.value,
        "requires_approval": requires_approval,
        "matched_patterns": matched,
        "reason": ", ".join(reasons)
    }


def is_dangerous_command(command: str) -> bool:
    """
    Verificación rápida si un comando requiere aprobación.
    
    Args:
        command: Comando a verificar
        
    Returns:
        True si requiere aprobación humana
    """
    analysis = analyze_command(command)
    return analysis["requires_approval"]


def get_risk_level(command: str) -> str:
    """
    Obtiene el nivel de riesgo de un comando.
    
    Args:
        command: Comando a analizar
        
    Returns:
        String con el nivel de riesgo
    """
    analysis = analyze_command(command)
    return analysis["risk_level"]


# =============================================================================
# SISTEMA DE AUDITORÍA
# =============================================================================

class CommandAuditLog:
    """
    Sistema de auditoría para registrar todos los comandos ejecutados.
    """
    
    def __init__(self, db_module):
        """
        Inicializa el sistema de auditoría.
        
        Args:
            db_module: Módulo de base de datos (database.py)
        """
        self.db = db_module
    
    def log_command_attempt(
        self,
        conversation_id: str,
        command: str,
        mission_id: Optional[str] = None,
        objective_id: Optional[int] = None
    ) -> int:
        """
        Registra un intento de ejecución de comando.
        
        Returns:
            ID del registro de auditoría
        """
        analysis = analyze_command(command)
        
        return self.db.add_audit_log(
            conversation_id=conversation_id,
            command=command,
            risk_level=analysis["risk_level"],
            requires_approval=analysis["requires_approval"],
            reason=analysis["reason"],
            mission_id=mission_id,
            objective_id=objective_id,
            status="PENDING" if analysis["requires_approval"] else "ALLOWED"
        )
    
    def log_command_result(
        self,
        audit_id: int,
        status: str,  # EXECUTED, APPROVED, REJECTED, FAILED
        result_summary: Optional[str] = None,
        approved_by: Optional[str] = None
    ):
        """
        Actualiza el registro de auditoría con el resultado.
        """
        self.db.update_audit_log(
            audit_id=audit_id,
            status=status,
            result_summary=result_summary,
            approved_by=approved_by
        )


# =============================================================================
# UTILIDADES
# =============================================================================

def get_approval_message(command: str, analysis: Dict) -> str:
    """
    Genera un mensaje explicativo para solicitar aprobación.
    
    Args:
        command: Comando que requiere aprobación
        analysis: Resultado de analyze_command()
        
    Returns:
        Mensaje formateado para el usuario
    """
    risk_emoji = {
        "critical": "🔴",
        "high": "🟠",
        "medium": "🟡",
        "low": "🟢",
        "safe": "✅"
    }
    
    emoji = risk_emoji.get(analysis["risk_level"], "⚪")
    
    message = f"""
{emoji} **COMANDO REQUIERE APROBACIÓN**

**Comando:** `{command}`

**Nivel de riesgo:** {analysis["risk_level"].upper()}

**Razón:** {analysis["reason"]}

**Patrones detectados:**
"""
    
    for pattern in analysis["matched_patterns"]:
        message += f"- {pattern['description']} (riesgo: {pattern['risk']})\n"
    
    message += """
Por favor, revisa el comando antes de aprobar su ejecución.
"""
    
    return message.strip()


def format_audit_report(logs: List[Dict]) -> str:
    """
    Genera un reporte de auditoría formateado.
    
    Args:
        logs: Lista de registros de auditoría
        
    Returns:
        Reporte en formato Markdown
    """
    if not logs:
        return "No hay registros de auditoría."
    
    report = "# 📋 Reporte de Auditoría de Comandos\n\n"
    report += f"**Total de comandos:** {len(logs)}\n\n"
    
    # Estadísticas
    stats = {"EXECUTED": 0, "APPROVED": 0, "REJECTED": 0, "FAILED": 0, "PENDING": 0}
    risk_stats = {"critical": 0, "high": 0, "medium": 0, "low": 0, "safe": 0}
    
    for log in logs:
        stats[log.get("status", "PENDING")] = stats.get(log.get("status", "PENDING"), 0) + 1
        risk_stats[log.get("risk_level", "low")] = risk_stats.get(log.get("risk_level", "low"), 0) + 1
    
    report += "## Estadísticas\n\n"
    report += f"- ✅ Ejecutados: {stats['EXECUTED']}\n"
    report += f"- ✓ Aprobados: {stats['APPROVED']}\n"
    report += f"- ✗ Rechazados: {stats['REJECTED']}\n"
    report += f"- ⏳ Pendientes: {stats['PENDING']}\n"
    report += f"- ❌ Fallidos: {stats['FAILED']}\n\n"
    
    report += "## Por Nivel de Riesgo\n\n"
    report += f"- 🔴 Critical: {risk_stats['critical']}\n"
    report += f"- 🟠 High: {risk_stats['high']}\n"
    report += f"- 🟡 Medium: {risk_stats['medium']}\n"
    report += f"- 🟢 Low: {risk_stats['low']}\n"
    report += f"- ✅ Safe: {risk_stats['safe']}\n\n"
    
    report += "## Detalle de Comandos\n\n"
    
    for log in logs:
        timestamp = log.get("created_at", "N/A")
        command = log.get("command", "N/A")
        status = log.get("status", "PENDING")
        risk = log.get("risk_level", "low")
        
        status_emoji = {"EXECUTED": "✅", "APPROVED": "✓", "REJECTED": "✗", "PENDING": "⏳", "FAILED": "❌"}
        
        report += f"### {status_emoji.get(status, '?')} {timestamp}\n"
        report += f"- **Comando:** `{command[:100]}{'...' if len(command) > 100 else ''}`\n"
        report += f"- **Riesgo:** {risk}\n"
        report += f"- **Estado:** {status}\n"
        if log.get("reason"):
            report += f"- **Razón:** {log['reason']}\n"
        report += "\n"
    
    return report
