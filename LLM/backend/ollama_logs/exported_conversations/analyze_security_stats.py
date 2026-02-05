#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze_security_stats.py - Genera estadísticas globales y detecta falsos positivos.

Analiza todos los CSVs de seguridad generados y produce:
1. CSV con estadísticas agregadas por modelo y entorno
2. Reporte de falsos positivos (comandos mal clasificados)
"""

import csv
import sys
import re
from pathlib import Path
from collections import defaultdict, Counter
from typing import List, Dict, Tuple, Tuple

# Configurar output a UTF-8
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

# Importar patrones de clasificación del módulo de seguridad
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from security import DANGEROUS_PATTERNS, SAFE_PATTERNS, RiskLevel

SECURITY_FOLDER = Path("security_reports")
AUTONOMY_FOLDER = Path("autonomy_reports")
OUTPUT_STATS = Path("estadisticas_globales.csv")
OUTPUT_FALSE_POSITIVES = Path("falsos_positivos.csv")


def parse_autonomy_csv(csv_path: Path) -> Dict:
    """Extrae métricas de autonomía de un CSV."""
    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
        
        data = {
            'model': None,
            'autonomy_percentage': 0.0,
            'approvals': 0,
            'avg_wait_time': 0.0
        }
        
        # Buscar la línea con los datos (después de "=== DATOS PARA TABLA 6.8 ===")
        for i, line in enumerate(lines):
            if 'DATOS PARA TABLA 6.8' in line:
                # La línea de datos está 2 líneas después
                if i + 2 < len(lines):
                    data_line = lines[i + 2].strip()
                    parts = data_line.split(';')
                    
                    if len(parts) >= 4:
                        data['model'] = parts[0].strip()
                        
                        # Autonomía (remover %)
                        autonomy_str = parts[1].strip().replace('%', '')
                        data['autonomy_percentage'] = float(autonomy_str)
                        
                        # Aprobaciones
                        data['approvals'] = int(parts[2].strip())
                        
                        # Tiempo de espera (remover " s")
                        wait_str = parts[3].strip().replace(' s', '')
                        data['avg_wait_time'] = float(wait_str)
                    
                    break
        
        return data
    
    except Exception as e:
        print(f"[ERROR] Error parseando autonomía {csv_path}: {e}")
        return None


def parse_csv(csv_path: Path) -> Dict:
    """Extrae información de un CSV de seguridad."""
    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
        
        data = {
            'conversation_id': None,
            'conversation_title': None,
            'model': None,
            'risk_counts': {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'safe': 0},
            'total_commands': 0,
            'user_interventions': 0,
            'total_messages': 0,
            'commands': []  # Lista de (comando, nivel_asignado, razon)
        }
        
        # Parsear líneas
        for i, line in enumerate(lines):
            parts = line.strip().split(';')
            
            if len(parts) >= 2:
                key = parts[0].strip()
                value = parts[1].strip() if len(parts) > 1 else ''
                
                # Extraer campos clave
                if key == 'ID':
                    data['conversation_id'] = value
                elif key == 'Conversación':
                    data['conversation_title'] = value[:100]
                elif key == 'TOTAL CRITICAL':
                    data['risk_counts']['critical'] = int(value)
                elif key == 'TOTAL HIGH':
                    data['risk_counts']['high'] = int(value)
                elif key == 'TOTAL MEDIUM':
                    data['risk_counts']['medium'] = int(value)
                elif key == 'TOTAL LOW':
                    data['risk_counts']['low'] = int(value)
                elif key == 'TOTAL SAFE':
                    data['risk_counts']['safe'] = int(value)
                elif key == 'TOTAL COMANDOS':
                    data['total_commands'] = int(value)
                elif key == 'Total mensajes usuario':
                    data['user_interventions'] = int(value)
                elif key == 'Total mensajes en thread':
                    data['total_messages'] = int(value)
        
        # Extraer comandos detallados (sección final)
        in_commands_section = False
        for i, line in enumerate(lines):
            if 'DETALLE DE COMANDOS POR RIESGO' in line:
                in_commands_section = True
                continue
            
            if in_commands_section and i > 0:
                parts = line.strip().split(';')
                if len(parts) >= 4 and parts[0] != 'Comando':
                    comando = parts[0].strip()
                    nivel_numero = parts[1].strip()
                    nivel_texto = parts[2].strip()
                    razon = parts[3].strip()
                    
                    # Validar que no sea header
                    if nivel_numero.isdigit():
                        data['commands'].append({
                            'command': comando,
                            'risk_number': int(nivel_numero),
                            'risk_level': nivel_texto.lower(),
                            'reason': razon
                        })
        
        # Extraer modelo del nombre del archivo
        filename = csv_path.stem
        if 'DeepCogito' in filename or 'deepcogito' in filename.lower():
            data['model'] = 'DeepCogito-Qwen-32B'
        elif 'gpt-oss' in filename:
            data['model'] = 'gpt-oss-20b'
        elif 'nemotron' in filename:
            data['model'] = 'nemotron-3-nano-30b'
        elif 'DEEPSEEK' in filename:
            data['model'] = 'DeepSeek-V3.2'
        elif 'G3PRO' in filename or 'gemini' in filename.lower():
            data['model'] = 'Gemini-3-Pro'
        else:
            data['model'] = 'Unknown'
        
        # Extraer entorno
        if 'DVWA' in filename:
            data['environment'] = 'DVWA'
        elif 'Juice' in filename or 'JSHOP' in filename:
            data['environment'] = 'Juice Shop'
        elif 'Metasploit' in filename or 'METASPLOIT' in filename:
            data['environment'] = 'Metasploitable2'
        else:
            data['environment'] = 'Unknown'
        
        return data
    
    except Exception as e:
        print(f"[ERROR] Error parseando {csv_path}: {e}")
        return None


def reclassify_command(command: str) -> Tuple[str, str]:
    """Re-clasifica un comando usando los patrones originales de security.py.
    
    Returns:
        Tupla de (nivel_riesgo, explicacion_patron)
    """
    # Verificar whitelist
    for safe_pattern in SAFE_PATTERNS:
        if re.search(safe_pattern, command, re.IGNORECASE):
            return ("safe", f"Coincide con patrón de whitelist: {safe_pattern}")
    
    # Buscar patrones peligrosos
    max_risk = RiskLevel.LOW
    matched_descriptions = []
    
    for pattern, risk_level, description in DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            matched_descriptions.append(f"{description} (patrón: {pattern})")
            
            if risk_level.value == RiskLevel.CRITICAL.value:
                max_risk = RiskLevel.CRITICAL
            elif risk_level.value == RiskLevel.HIGH.value and max_risk != RiskLevel.CRITICAL:
                max_risk = RiskLevel.HIGH
            elif risk_level.value == RiskLevel.MEDIUM.value and max_risk not in [RiskLevel.CRITICAL, RiskLevel.HIGH]:
                max_risk = RiskLevel.MEDIUM
    
    # Generar explicación
    if matched_descriptions:
        explanation = " + ".join(matched_descriptions)
    else:
        explanation = "Sin patrones de riesgo detectados (LOW por defecto)"
    
    return (max_risk.value, explanation)


def find_false_positives(all_data: List[Dict]) -> List[Dict]:
    """Identifica comandos mal clasificados."""
    false_positives = []
    
    for data in all_data:
        for cmd in data['commands']:
            expected_level, explanation = reclassify_command(cmd['command'])
            actual_level = cmd['risk_level']
            
            # Considerar falso positivo si difiere
            if expected_level != actual_level:
                false_positives.append({
                    'model': data['model'],
                    'environment': data['environment'],
                    'command': cmd['command'][:150],  # Aumentar límite
                    'expected_level': expected_level,
                    'actual_level': actual_level,
                    'reason_given': cmd['reason'],
                    'expected_reason': explanation  # Nueva columna
                })
    
    return false_positives


def generate_statistics_csv(all_data: List[Dict], autonomy_data: Dict[str, Dict], output_path: Path):
    """Genera CSV con estadísticas globales incluyendo métricas de autonomía."""
    # Agrupar por modelo y entorno
    stats_by_model_env = defaultdict(lambda: {
        'total_commands': 0,
        'critical': 0,
        'high': 0,
        'medium': 0,
        'low': 0,
        'safe': 0,
        'conversations': 0,
        'total_interventions': 0,
        'total_messages': 0,
        'autonomy_percentage': 0.0,
        'avg_wait_time': 0.0,
        'approvals': 0,
        'autonomy_count': 0  # Para calcular promedio correcto
    })
    
    # Agrupar solo por modelo (sin entorno)
    stats_by_model = defaultdict(lambda: {
        'total_commands': 0,
        'critical': 0,
        'high': 0,
        'medium': 0,
        'low': 0,
        'safe': 0,
        'conversations': 0,
        'total_interventions': 0,
        'total_messages': 0,
        'autonomy_percentage': 0.0,
        'avg_wait_time': 0.0,
        'approvals': 0,
        'autonomy_count': 0
    })
    
    for data in all_data:
        key = (data['model'], data['environment'])
        stats = stats_by_model_env[key]
        
        stats['total_commands'] += data['total_commands']
        stats['critical'] += data['risk_counts']['critical']
        stats['high'] += data['risk_counts']['high']
        stats['medium'] += data['risk_counts']['medium']
        stats['low'] += data['risk_counts']['low']
        stats['safe'] += data['risk_counts']['safe']
        stats['conversations'] += 1
        stats['total_interventions'] += data['user_interventions']
        stats['total_messages'] += data['total_messages']
        
        # Buscar datos de autonomía correspondientes
        conv_id = data.get('conversation_id', '')
        if conv_id in autonomy_data:
            auto = autonomy_data[conv_id]
            stats['autonomy_percentage'] += auto['autonomy_percentage']
            stats['avg_wait_time'] += auto['avg_wait_time']
            stats['approvals'] += auto['approvals']
            stats['autonomy_count'] += 1
        
        # Agregar también a stats por modelo solamente
        model_key = data['model']
        model_stats = stats_by_model[model_key]
        model_stats['total_commands'] += data['total_commands']
        model_stats['critical'] += data['risk_counts']['critical']
        model_stats['high'] += data['risk_counts']['high']
        model_stats['medium'] += data['risk_counts']['medium']
        model_stats['low'] += data['risk_counts']['low']
        model_stats['safe'] += data['risk_counts']['safe']
        model_stats['conversations'] += 1
        model_stats['total_interventions'] += data['user_interventions']
        model_stats['total_messages'] += data['total_messages']
        
        if conv_id in autonomy_data:
            auto = autonomy_data[conv_id]
            model_stats['autonomy_percentage'] += auto['autonomy_percentage']
            model_stats['avg_wait_time'] += auto['avg_wait_time']
            model_stats['approvals'] += auto['approvals']
            model_stats['autonomy_count'] += 1
    
    # Escribir CSV
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f, delimiter=';')
        
        # Cabecera
        writer.writerow(['ESTADÍSTICAS GLOBALES DE COMANDOS POR MODELO Y ENTORNO'])
        writer.writerow([])
        
        # Headers
        writer.writerow([
            'Modelo',
            'Entorno',
            'Conversaciones',
            'Total Comandos',
            'CRITICAL',
            'HIGH',
            'MEDIUM',
            'LOW',
            'SAFE',
            '% Autonomía',
            'T. Espera Medio (s)',
            'Aprobaciones (con MEDIUM)',
            'Aprobaciones (sin MEDIUM)',
            'Intervenciones Usuario',
            'Total Mensajes',
            'Promedio Comandos/Conv'
        ])
        
        # Datos
        for (model, env), stats in sorted(stats_by_model_env.items()):
            avg_commands = stats['total_commands'] / stats['conversations'] if stats['conversations'] > 0 else 0
            avg_autonomy = stats['autonomy_percentage'] / stats['autonomy_count'] if stats['autonomy_count'] > 0 else 0
            avg_wait = stats['avg_wait_time'] / stats['autonomy_count'] if stats['autonomy_count'] > 0 else 0
            
            # Aprobaciones con MEDIUM = CRITICAL + HIGH + MEDIUM
            approvals_with_medium = stats['critical'] + stats['high'] + stats['medium']
            
            # Aprobaciones sin MEDIUM = CRITICAL + HIGH
            approvals_without_medium = stats['critical'] + stats['high']
            
            writer.writerow([
                model,
                env,
                stats['conversations'],
                stats['total_commands'],
                stats['critical'],
                stats['high'],
                stats['medium'],
                stats['low'],
                stats['safe'],
                f"{avg_autonomy:.2f}%" if avg_autonomy > 0 else "N/A",
                f"{avg_wait:.2f}" if avg_wait > 0 else "N/A",
                approvals_with_medium,
                approvals_without_medium,
                stats['total_interventions'],
                stats['total_messages'],
                f"{avg_commands:.1f}"
            ])
        
        # Totales globales
        writer.writerow([])
        writer.writerow(['=== TOTALES GLOBALES ==='])
        
        total_commands = sum(s['total_commands'] for s in stats_by_model_env.values())
        total_critical = sum(s['critical'] for s in stats_by_model_env.values())
        total_high = sum(s['high'] for s in stats_by_model_env.values())
        total_medium = sum(s['medium'] for s in stats_by_model_env.values())
        total_low = sum(s['low'] for s in stats_by_model_env.values())
        total_safe = sum(s['safe'] for s in stats_by_model_env.values())
        total_convs = sum(s['conversations'] for s in stats_by_model_env.values())
        
        total_approvals_with = total_critical + total_high + total_medium
        total_approvals_without = total_critical + total_high
        
        writer.writerow(['Total Conversaciones', total_convs])
        writer.writerow(['Total Comandos Analizados', total_commands])
        writer.writerow(['Total CRITICAL', total_critical])
        writer.writerow(['Total HIGH', total_high])
        writer.writerow(['Total MEDIUM', total_medium])
        writer.writerow(['Total LOW', total_low])
        writer.writerow(['Total SAFE', total_safe])
        writer.writerow(['Total Aprobaciones (con MEDIUM)', total_approvals_with])
        writer.writerow(['Total Aprobaciones (sin MEDIUM)', total_approvals_without])
        
        # Distribución porcentual
        writer.writerow([])
        writer.writerow(['=== DISTRIBUCIÓN PORCENTUAL ==='])
        if total_commands > 0:
            writer.writerow(['% CRITICAL', f"{(total_critical/total_commands)*100:.2f}%"])
            writer.writerow(['% HIGH', f"{(total_high/total_commands)*100:.2f}%"])
            writer.writerow(['% MEDIUM', f"{(total_medium/total_commands)*100:.2f}%"])
            writer.writerow(['% LOW', f"{(total_low/total_commands)*100:.2f}%"])
            writer.writerow(['% SAFE', f"{(total_safe/total_commands)*100:.2f}%"])
            writer.writerow(['% Comandos que requieren aprobación (con MEDIUM)', f"{(total_approvals_with/total_commands)*100:.2f}%"])
            writer.writerow(['% Comandos que requieren aprobación (sin MEDIUM)', f"{(total_approvals_without/total_commands)*100:.2f}%"])
        
        # NUEVA SECCIÓN: Estadísticas por modelo (agrupando todos los entornos)
        writer.writerow([])
        writer.writerow(['=== ESTADÍSTICAS POR MODELO (TODOS LOS ENTORNOS) ==='])
        writer.writerow([])
        writer.writerow([
            'Modelo',
            'Conversaciones',
            'Total Comandos',
            'CRITICAL',
            'HIGH',
            'MEDIUM',
            'LOW',
            'SAFE',
            '% Autonomía Media',
            'T. Espera Medio (s)',
            'Aprobaciones (con MEDIUM)',
            'Aprobaciones (sin MEDIUM)',
            'Total Mensajes',
            'Promedio Comandos/Conv'
        ])
        
        for model, stats in sorted(stats_by_model.items()):
            avg_commands = stats['total_commands'] / stats['conversations'] if stats['conversations'] > 0 else 0
            avg_autonomy = stats['autonomy_percentage'] / stats['autonomy_count'] if stats['autonomy_count'] > 0 else 0
            avg_wait = stats['avg_wait_time'] / stats['autonomy_count'] if stats['autonomy_count'] > 0 else 0
            
            approvals_with_medium = stats['critical'] + stats['high'] + stats['medium']
            approvals_without_medium = stats['critical'] + stats['high']
            
            writer.writerow([
                model,
                stats['conversations'],
                stats['total_commands'],
                stats['critical'],
                stats['high'],
                stats['medium'],
                stats['low'],
                stats['safe'],
                f"{avg_autonomy:.2f}%" if avg_autonomy > 0 else "N/A",
                f"{avg_wait:.2f}" if avg_wait > 0 else "N/A",
                approvals_with_medium,
                approvals_without_medium,
                stats['total_messages'],
                f"{avg_commands:.1f}"
            ])
    
    print(f"[OK] Estadísticas globales generadas: {output_path}")


def generate_false_positives_csv(false_positives: List[Dict], output_path: Path):
    """Genera CSV con análisis de falsos positivos."""
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f, delimiter=';')
        
        writer.writerow(['ANÁLISIS DE FALSOS POSITIVOS - CLASIFICACIONES INCORRECTAS'])
        writer.writerow([])
        writer.writerow([
            'Modelo',
            'Entorno',
            'Comando',
            'Nivel Esperado',
            'Nivel Asignado',
            'Por qué debería ser ESPERADO',
            'Razón que dio el sistema'
        ])
        
        for fp in false_positives:
            writer.writerow([
                fp['model'],
                fp['environment'],
                fp['command'],
                fp['expected_level'].upper(),
                fp['actual_level'].upper(),
                fp['expected_reason'],  # Nueva columna explicativa
                fp['reason_given']
            ])
        
        # Resumen
        writer.writerow([])
        writer.writerow(['=== RESUMEN ==='])
        writer.writerow(['Total Falsos Positivos', len(false_positives)])
        
        # Por modelo
        by_model = Counter(fp['model'] for fp in false_positives)
        writer.writerow([])
        writer.writerow(['Por Modelo'])
        for model, count in by_model.most_common():
            writer.writerow([model, count])
        
        # Por tipo de error
        writer.writerow([])
        writer.writerow(['Por Tipo de Error'])
        error_types = Counter(f"{fp['expected_level']} -> {fp['actual_level']}" for fp in false_positives)
        for error_type, count in error_types.most_common():
            writer.writerow([error_type, count])
    
    print(f"[OK] Análisis de falsos positivos generado: {output_path}")


def main():
    """Función principal."""
    if not SECURITY_FOLDER.exists():
        print(f"[ERROR] No se encontró la carpeta {SECURITY_FOLDER}")
        return
    
    # Listar CSVs
    csv_files = list(SECURITY_FOLDER.glob("*.csv"))
    
    if not csv_files:
        print(f"[WARN] No se encontraron CSVs en {SECURITY_FOLDER}")
        return
    
    print(f"[INFO] Analizando {len(csv_files)} archivos CSV...\n")
    
    # Parsear todos los CSVs de seguridad
    all_data = []
    for csv_file in csv_files:
        print(f"[PROCESS] {csv_file.name}")
        data = parse_csv(csv_file)
        if data:
            all_data.append(data)
    
    print(f"\n[OK] {len(all_data)} archivos procesados correctamente\n")
    
    # Parsear CSVs de autonomía
    autonomy_data = {}
    if AUTONOMY_FOLDER.exists():
        print(f"[INFO] Cargando datos de autonomía desde {AUTONOMY_FOLDER}...\n")
        autonomy_files = list(AUTONOMY_FOLDER.glob("*.csv"))
        
        for auto_file in autonomy_files:
            print(f"[AUTONOMY] {auto_file.name}")
            auto_data = parse_autonomy_csv(auto_file)
            if auto_data:
                # Estrategia de matching: por nombre de archivo sin extensión
                # Los archivos deberían tener nombres similares
                auto_basename = auto_file.stem.replace('_autonomy', '').lower()
                
                # Buscar coincidencia en all_data
                matched = False
                for data in all_data:
                    security_basename = Path(csv_files[all_data.index(data)]).stem.replace('_security', '').lower()
                    
                    # Match directo por nombre de archivo
                    if auto_basename == security_basename:
                        autonomy_data[data['conversation_id']] = auto_data
                        matched = True
                        print(f"  -> Matched con {Path(csv_files[all_data.index(data)]).name}")
                        break
                
                if not matched:
                    print(f"  -> [WARN] No se encontró coincidencia para {auto_file.name}")
        
        print(f"\n[OK] {len(autonomy_data)} archivos de autonomía vinculados\n")
    else:
        print(f"[WARN] No se encontró carpeta {AUTONOMY_FOLDER}, las métricas de autonomía estarán en 0\n")
    
    # Generar estadísticas globales
    generate_statistics_csv(all_data, autonomy_data, OUTPUT_STATS)
    
    # Detectar falsos positivos
    print("\n[ANALYSIS] Detectando falsos positivos...")
    false_positives = find_false_positives(all_data)
    print(f"[FOUND] {len(false_positives)} clasificaciones incorrectas detectadas\n")
    
    generate_false_positives_csv(false_positives, OUTPUT_FALSE_POSITIVES)
    
    # Resumen final
    print("\n" + "="*60)
    print("[SUMMARY] Análisis completado")
    print(f"  - Conversaciones analizadas: {len(all_data)}")
    print(f"  - Total comandos: {sum(d['total_commands'] for d in all_data)}")
    print(f"  - Falsos positivos: {len(false_positives)}")
    print(f"\n[OUTPUT]")
    print(f"  - Estadísticas: {OUTPUT_STATS.absolute()}")
    print(f"  - Falsos positivos: {OUTPUT_FALSE_POSITIVES.absolute()}")


if __name__ == "__main__":
    main()
