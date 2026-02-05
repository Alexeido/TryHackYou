#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
addSecurity.py - Genera reportes de seguridad y autonomía para todas las conversaciones.

Escanea todos los .md de la carpeta actual, extrae el ID de conversación de la primera línea,
y genera dos CSVs: uno de seguridad y otro de autonomía, en sus carpetas respectivas.

Estructura esperada en la primera línea:
    Conversacion conv_14fbc4636df2 | model: gpt-oss:20b
                ^--- Posición 15, 17 caracteres de largo
"""

import os
import subprocess
import sys
from pathlib import Path

# Configurar output a UTF-8
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass
if sys.stderr.encoding != 'utf-8':
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

# Rutas de destino
SECURITY_FOLDER = Path("security_reports")
AUTONOMY_FOLDER = Path("autonomy_reports")

# Ruta del script conversation_analyzer.py
CONVERSATION_ANALYZER = Path(__file__).parent.parent.parent / "conversation_analyzer.py"

# Crear carpetas si no existen
SECURITY_FOLDER.mkdir(exist_ok=True)
AUTONOMY_FOLDER.mkdir(exist_ok=True)

print(f"[DIR] Reportes de seguridad: {SECURITY_FOLDER.absolute()}")
print(f"[DIR] Reportes de autonomía: {AUTONOMY_FOLDER.absolute()}")
print(f"[CONFIG] Script: {CONVERSATION_ANALYZER}\n")


def list_md_files():
    """Lista todos los archivos .md en la carpeta actual."""
    md_files = []
    for file in os.listdir('.'):
        if file.endswith('.md'):
            md_files.append(file)
    return sorted(md_files)


def extract_conversation_id(md_file):
    """
    Extrae el ID de conversación de la primera línea del archivo .md.
    
    Formato esperado:
        Conversacion conv_14fbc4636df2 | model: gpt-oss:20b
    
    Returns:
        Tupla (conversation_id, model) o (None, None) si falla
    """
    try:
        # Abrir con UTF-8 para manejar caracteres especiales
        with open(md_file, 'r', encoding='utf-8') as f:
            first_line = f.readline()
        
        # Extraer ID (posición 15, 17 caracteres)
        if len(first_line) < 32:
            print(f"⚠️ Primera línea demasiado corta en {md_file}: {first_line}")
            return None, None
        
        conversation_id = first_line[15:32].strip()
        
        # Extraer modelo (después de "model: ")
        model = "unknown"
        if "model:" in first_line:
            model_part = first_line.split("model:")[1].strip()
            model = model_part.split()[0] if model_part else "unknown"
        
        # Validar que sea un ID válido (empieza con "conv_")
        if not conversation_id.startswith("conv_"):
            print(f"⚠️ ID no válido en {md_file}: {conversation_id}")
            return None, None
        
        return conversation_id, model
    
    except UnicodeDecodeError as e:
        print(f"❌ Error de encoding al leer {md_file}: {e}")
        return None, None
    except Exception as e:
        print(f"❌ Error al procesar {md_file}: {e}")
        return None, None


def generate_security_report(conversation_id: str, md_file: str):
    """
    Genera el reporte de seguridad (CSV) para una conversación.
    
    Args:
        conversation_id: ID de la conversación
        md_file: Nombre del archivo .md (para nombrar el CSV)
    """
    try:
        # Nombre del archivo de salida
        base_name = md_file.replace('.md', '')
        output_file = SECURITY_FOLDER / f"{base_name}_security.csv"
        
        # Ejecutar conversation_analyzer.py en modo CLI
        cmd = [
            sys.executable,
            str(CONVERSATION_ANALYZER),
            conversation_id,
            str(output_file)
        ]
        
        print(f"  [SECURITY] Generando: {output_file.name}")
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        
        if result.returncode != 0:
            print(f"     [ERROR] {result.stderr[:200]}")
            return False
        
        return True
    
    except Exception as e:
        print(f"  [ERROR] Error al generar reporte de seguridad: {e}")
        return False


def generate_autonomy_report(conversation_id: str, md_file: str):
    """
    Genera el reporte de autonomía (CSV) para una conversación.
    
    Args:
        conversation_id: ID de la conversación
        md_file: Nombre del archivo .md (para nombrar el CSV)
    """
    try:
        # Nombre del archivo de salida
        base_name = md_file.replace('.md', '')
        output_file = AUTONOMY_FOLDER / f"{base_name}_autonomy.csv"
        
        # Ejecutar conversation_analyzer.py en modo CLI
        cmd = [
            sys.executable,
            str(CONVERSATION_ANALYZER),
            "--autonomy",
            conversation_id,
            str(output_file)
        ]
        
        print(f"  [AUTONOMY] Generando: {output_file.name}")
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        
        if result.returncode != 0:
            print(f"     [ERROR] {result.stderr[:200]}")
            return False
        
        return True
    
    except Exception as e:
        print(f"  [ERROR] Error al generar reporte de autonomía: {e}")
        return False


def main():
    """Función principal."""
    md_files = list_md_files()
    
    if not md_files:
        print("⚠️ No se encontraron archivos .md en la carpeta actual")
        return
    
    print(f"[FILE] Se encontraron {len(md_files)} archivos .md\n")
    
    success_count = 0
    fail_count = 0
    
    for md_file in md_files:
        print(f"[PROCESS] Procesando: {md_file}")
        
        # Extraer ID de conversación
        conversation_id, model = extract_conversation_id(md_file)
        
        if not conversation_id:
            print(f"   [WARN] No se pudo extraer ID, saltando...\n")
            fail_count += 1
            continue
        
        print(f"   ID: {conversation_id} | Modelo: {model}")
        
        # Generar ambos reportes
        security_ok = generate_security_report(conversation_id, md_file)
        autonomy_ok = generate_autonomy_report(conversation_id, md_file)
        
        if security_ok and autonomy_ok:
            print(f"   [OK] Completado\n")
            success_count += 1
        else:
            print(f"   [FAIL] Falló\n")
            fail_count += 1
    
    # Resumen final
    print("=" * 60)
    print(f"[OK] Completados: {success_count}/{len(md_files)}")
    print(f"[FAIL] Fallidos: {fail_count}/{len(md_files)}")
    print(f"[DIR] Reportes guardados en:")
    print(f"   - {SECURITY_FOLDER.absolute()}")
    print(f"   - {AUTONOMY_FOLDER.absolute()}")


if __name__ == "__main__":
    main()