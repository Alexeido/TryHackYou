# Programa que en una interfaz gui NO DE TERMINAL!!! muestra la lista de conversaciones nos deja elegir una y exportarla legible para humanos, en markdown

# Mirará en localhost:4000 

# GET /conversations

# GET /conversations/{conversation_id}/thread 

import requests
import json
import os
import re
import sys
import csv
from datetime import datetime
from collections import defaultdict


def clean_text(text):
    """Elimina caracteres de control ANSI y otros caracteres especiales problemáticos"""
    if not text:
        return text
    
    # Eliminar secuencias de escape ANSI (códigos de color, etc.)
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    text = ansi_escape.sub('', text)
    
    # Eliminar otros caracteres de control excepto saltos de línea y tabulaciones
    text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F-\x9F]', '', text)
    
    return text

def export_conversation(conversation_id, output_dir, title=None, metadata=None):
    # Endpoint para obtener el hilo de la conversación
    url = f"http://localhost:4000/conversations/{conversation_id}/thread"
    
    try:
        print(f"  Obteniendo datos de la conversación...")
        response = requests.get(url, timeout=30)  # Timeout de 30 segundos
        response.raise_for_status()  # Verificar que la solicitud fue exitosa
        thread_data = response.json()
        print(f"  Datos recibidos. Procesando...")
        
        # Crear el directorio de salida si no existe
        os.makedirs(output_dir, exist_ok=True)
        
        # Detectar objetivo si está en el primer mensaje del usuario
        target = None
        if 'messages' in thread_data and len(thread_data['messages']) > 1:
            first_user_msg = thread_data['messages'][1].get('content', '')
            if '10.10.0.4' in first_user_msg:
                target = 'Metasploitable2'
            elif '10.10.0.5' in first_user_msg:
                target = 'Juice Shop'
            elif '10.10.0.3' in first_user_msg:
                target = 'DVWA'
        
        # Determinar nombre del archivo
        if metadata:
            # Si viene del CSV, usar formato: model-objetivo-hora.md
            model_name = metadata.get('model', 'desconocido').replace(':', '-').replace(' ', '_').replace('/', '-')
            if "deepcogito" in model_name:
                model_name = "DeepCogito-Qwen-32B-Q8_K"
            target_name = target if target else 'desconocido'
            timestamp = metadata.get('last_timestamp', '').replace('/', '-').replace(' ', '_').replace(':', '-')
            output_path = os.path.join(output_dir, f"{model_name}-{target_name}-{timestamp}.md")
        elif title != '':
            # Si tiene título, usar formato anterior
            short_id = conversation_id[5:]
            output_path = os.path.join(output_dir, f"{title if title else ''}_{short_id}.md")
        else:
            # Por defecto, usar el conversation_id
            output_path = os.path.join(output_dir, f"{conversation_id}.md")
        
        # Guardar la conversación en un archivo md
        with open(output_path, 'w', encoding='utf-8') as f:
            # Sacamos del modelo del tercer mensaje del hilo, que es donde ya ha respondido el modelo, para ponerlo en el título del md
            model = "desconocido"
            if 'messages' in thread_data and len(thread_data['messages']) > 2:
                model = thread_data['messages'][2].get('model_used', 'desconocido')
            f.write(f"# Conversación {conversation_id} | model: {model}\n\n")
            
            # Si hay metadata del CSV, añadirla al principio
            if metadata:
                f.write("## Estadísticas de la Conversación\n\n")
                if target:
                    f.write(f"- **Objetivo**: {target}\n")
                f.write(f"- **Último mensaje**: {metadata['last_timestamp']}\n")
                f.write(f"- **Duración total**: {metadata['duration']}\n")
                f.write(f"- **Tokens totales**: {metadata['cumulative_total']:,} tokens\n")
                f.write(f"  - Prompt: {metadata['cumulative_prompt']:,} tokens\n")
                f.write(f"  - Completion: {metadata['cumulative_completion']:,} tokens\n")
                f.write(f"- **Promedio por petición**:\n")
                f.write(f"  - Prompt: {metadata['avg_prompt']:.1f} tokens\n")
                f.write(f"  - Completion: {metadata['avg_completion']:.1f} tokens\n")
                f.write(f"  - Total: {metadata['avg_total']:.1f} tokens\n")
                f.write(f"- **Número de peticiones**: {metadata['num_requests']}\n\n")
                f.write("---\n\n")

            for message in thread_data.get('messages', []):
                role = message.get('role', 'unknown')
                content = message.get('content', '')
                tool_calls = message.get('tool_calls', '')
                
                # Limpiar contenido de caracteres especiales
                content = clean_text(content)
                tool_calls = clean_text(tool_calls)
                
                # Encabezado del rol
                f.write(f"## {role.capitalize()}\n\n")
                
                # Contenido del mensaje - añadir ## a todos los # para mejor jerarquía
                if content:
                    # Reemplazar # por ### en el contenido (añadir 2 niveles)
                    processed_content = content.replace('\n#', '\n###')
                    if processed_content.startswith('#'):
                        processed_content = '##' + processed_content
                    f.write(f"{processed_content}\n\n")
                
                # Si hay tool calls, procesarlas
                if tool_calls:
                    try:
                        # Intentar parsear como JSON
                        tool_calls_data = json.loads(tool_calls)
                        
                        # Si es una lista, procesarla
                        if isinstance(tool_calls_data, list):
                            for tool_call in tool_calls_data:
                                if isinstance(tool_call, dict):
                                    tool_name = tool_call.get('function', {}).get('name', 'tool')
                                    tool_args = tool_call.get('function', {}).get('arguments', '')
                                    
                                    # Parsear los argumentos y remover thought_signature
                                    try:
                                        args_data = json.loads(tool_args) if isinstance(tool_args, str) else tool_args
                                        if isinstance(args_data, dict):
                                            # Remover thought_signature y extra_content si existen
                                            args_data.pop('thought_signature', None)
                                            if 'extra_content' in args_data:
                                                extra = args_data.get('extra_content', {})
                                                if isinstance(extra, dict) and 'google' in extra:
                                                    extra.get('google', {}).pop('thought_signature', None)
                                            tool_args = json.dumps(args_data, indent=2, ensure_ascii=False)
                                    except:
                                        pass
                                    
                                    f.write(f"```{tool_name}\n{tool_args}\n```\n\n")
                        else:
                            # Si no es una lista, mostrar como texto
                            f.write(f"```tool\n{tool_calls}\n```\n\n")
                    except json.JSONDecodeError:
                        # Si no es JSON válido, mostrar como texto plano
                        f.write(f"```tool\n{tool_calls}\n```\n\n")
        
        print(f"Conversación {conversation_id} exportada exitosamente a {output_path}")
        return True
    except requests.exceptions.Timeout:
        print(f"ERROR: Timeout al obtener la conversación {conversation_id}")
        return False
    except requests.exceptions.RequestException as e:
        print(f"ERROR al obtener la conversación {conversation_id}: {e}")
        return False
    except Exception as e:
        print(f"ERROR inesperado al procesar {conversation_id}: {e}")
        return False

def list_conversations():
    url = "http://localhost:4000/conversations"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        # La API devuelve un objeto con 'conversations' y 'total'
        if isinstance(data, dict) and 'conversations' in data:
            conversations = data['conversations']
        else:
            conversations = data if isinstance(data, list) else []
        
        # Filtrar conversaciones válidas (con ID)
        valid_conversations = [c for c in conversations if c.get('id')]
        return valid_conversations
    except requests.exceptions.RequestException as e:
        print(f"Error al listar conversaciones: {e}")
        return []
    
import dearpygui.dearpygui as dpg

def PyGui_export_conversations():
    dpg.create_context()
    
    conversations = list_conversations()
    
    def refresh_conversations():
        """Actualiza la lista de conversaciones"""
        dpg.delete_item("conversation_group", children_only=True)
        conversations = list_conversations()
        
        if not conversations:
            dpg.add_text("No hay conversaciones disponibles", parent="conversation_group", color=(255, 100, 100))
            return
        
        for conv in conversations:
            conv_id = conv.get('id')
            if not conv_id:
                continue
            conv_title = conv.get('title', f"Conversación {conv_id}")
            dpg.add_button(
                parent="conversation_group",
                label=f"Exportar: {conv_title}",
                width=450,
                callback=export_and_notify,
                user_data=(conv_id, conv_title)
            )

    def export_and_notify(sender, app_data, user_data):
        """Exporta la conversación y muestra notificación"""
        conv_id, conv_title = user_data
        try:
            export_conversation(conv_id, "exported_conversations", title=conv_title)
            dpg.set_value("status_text", f"✓ Conversación {conv_title} exportada correctamente")
        except Exception as e:
            dpg.set_value("status_text", f"✗ Error al exportar: {str(e)}")
    
    with dpg.window(label="Exportar Conversaciones", tag="window_export", width=500, height=400, no_close=False):
        dpg.add_text("Selecciona una conversación para exportar:", color=(200, 200, 200))
        dpg.add_separator()
        
        # Grupo para las conversaciones
        with dpg.group(id="conversation_group"):
            if conversations:
                for conv in conversations:
                    conv_id = conv.get('id')
                    if not conv_id:
                        continue
                    conv_title = conv.get('title', f"Conversación {conv_id}")
                    dpg.add_button(
                        label=f"Exportar: {conv_title}",
                        width=450,
                        callback=export_and_notify,
                        user_data=(conv_id, conv_title)
                    )
                if not any(c.get('id') for c in conversations):
                    dpg.add_text("No hay conversaciones con ID válido", color=(255, 100, 100))
            else:
                dpg.add_text("No hay conversaciones disponibles", color=(255, 100, 100))
        
        dpg.add_separator()
        
        # Botón para refrescar
        dpg.add_button(
            label="Refrescar lista",
            width=200,
            callback=refresh_conversations
        )
        
        # Texto de estado
        dpg.add_text("", tag="status_text", color=(100, 200, 100))
    
    dpg.create_viewport(title="Exportador de Conversaciones", width=550, height=450)
    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.set_primary_window("window_export", True)
    
    while dpg.is_dearpygui_running():
        dpg.render_dearpygui_frame()
    
    dpg.destroy_context()

def process_csv_and_export(csv_path):
    """Procesa un CSV de tokens y exporta todas las conversaciones con estadísticas"""
    
    # Leer el CSV y agrupar por conversation_id
    conv_data = defaultdict(list)
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            conv_id = row['conversation_id']
            conv_data[conv_id].append(row)
    
    print(f"Encontradas {len(conv_data)} conversaciones únicas en el CSV")
    
    # Contadores para estadísticas
    exported_count = 0
    failed_count = 0
    
    # Procesar cada conversación
    for idx, (conv_id, rows) in enumerate(conv_data.items(), 1):
        print(f"\n[{idx}/{len(conv_data)}] Exportando {conv_id}...")
        
        # Ordenar por timestamp para asegurar orden correcto
        rows.sort(key=lambda x: x['timestamp'])
        
        first_row = rows[0]
        last_row = rows[-1]
        
        # Parsear timestamps
        first_time = datetime.fromisoformat(first_row['timestamp'])
        last_time = datetime.fromisoformat(last_row['timestamp'])
        
        # Calcular duración
        duration_seconds = (last_time - first_time).total_seconds()
        hours = int(duration_seconds // 3600)
        minutes = int((duration_seconds % 3600) // 60)
        seconds = int(duration_seconds % 60)
        
        if hours > 0:
            duration_str = f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            duration_str = f"{minutes}m {seconds}s"
        else:
            duration_str = f"{seconds}s"
        
        # Obtener valores acumulativos del último mensaje
        cumulative_prompt = int(last_row['cumulative_prompt'])
        cumulative_completion = int(last_row['cumulative_completion'])
        cumulative_total = int(last_row['cumulative_total'])
        
        # Calcular promedios
        num_requests = len(rows)
        avg_prompt = cumulative_prompt / num_requests
        avg_completion = cumulative_completion / num_requests
        avg_total = cumulative_total / num_requests
        
        # Formatear timestamp del último mensaje
        last_timestamp_str = last_time.strftime("%d/%m/%Y %H:%M")
        
        # Crear metadata
        metadata = {
            'last_timestamp': last_timestamp_str,
            'duration': duration_str,
            'cumulative_prompt': cumulative_prompt,
            'cumulative_completion': cumulative_completion,
            'cumulative_total': cumulative_total,
            'avg_prompt': avg_prompt,
            'avg_completion': avg_completion,
            'avg_total': avg_total,
            'num_requests': num_requests,
            'model': last_row['model']
        }
        
        success = export_conversation(conv_id, "exported_conversations", title='', metadata=metadata)
        if success:
            exported_count += 1
        else:
            failed_count += 1
    
    print(f"\n{'='*50}")
    print(f"✓ Exportación completada")
    print(f"  - Exitosas: {exported_count}/{len(conv_data)}")
    if failed_count > 0:
        print(f"  - Fallidas: {failed_count}/{len(conv_data)}")
    print(f"{'='*50}")

if __name__ == "__main__":
    # Si se proporciona un argumento
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        
        # Verificar si es un archivo CSV
        if arg.endswith('.csv'):
            print(f"Procesando CSV: {arg}")
            process_csv_and_export(arg)
        else:
            # Es un ID de conversación
            conversation_id = arg
            
            # Obtener información de la conversación para el título
            try:
                url = f"http://localhost:4000/conversations/{conversation_id}"
                response = requests.get(url)
                if response.status_code == 200:
                    conv_data = response.json()
                    title = conv_data.get('title', 'conversacion')
                else:
                    title = 'conversacion'
            except:
                title = 'conversacion'
            
            print(f"Exportando conversación {conversation_id}...")
            export_conversation(conversation_id, "exported_conversations", title=title)
    else:
        # Sin argumentos, abrir la GUI
        PyGui_export_conversations()