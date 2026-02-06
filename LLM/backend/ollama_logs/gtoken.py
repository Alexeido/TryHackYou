import requests
import dearpygui.dearpygui as dpg
import tiktoken
import os

# Intentar importar el nuevo SDK de Google GenAI
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    print("⚠️ Error: La librería 'google-genai' no está instalada.")
    print("Por favor ejecuta: pip install google-genai")

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================
BASE_URL = "http://localhost:4000"
DEFAULT_MODEL_ID = "gemini-2.0-flash" 

# ==============================================================================
# LÓGICA DE NEGOCIO
# ==============================================================================

def get_conversations():
    """Obtiene la lista de conversaciones del backend local."""
    try:
        response = requests.get(f"{BASE_URL}/conversations", timeout=5)
        response.raise_for_status()
        data = response.json()
        return data.get('conversations', [])
    except Exception as e:
        print(f"Error conectando al backend: {e}")
        return []


import json # Asegúrate de tener este import arriba

def calculate_tokens(sender, app_data, user_data):
    conv_id, conv_title = user_data
    api_key = dpg.get_value("api_key_input")
    model_id = dpg.get_value("model_id_input")
    
    if not api_key or not model_id or not genai:
        dpg.set_value("status_bar", "⚠️ Error de configuración.")
        return

    dpg.set_value("status_bar", f"⏳ Optimizando Contexto + Pensamientos: {conv_title}...")
    
    try:
        url = f"{BASE_URL}/conversations/{conv_id}/thread"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        thread_data = response.json()
        
        messages = thread_data.get('messages', [])
        system_raw = thread_data.get('system_instruction') or ""
        
        if not messages:
            dpg.set_value("status_bar", "⚠️ Conversación vacía.")
            return

        client = genai.Client(api_key=api_key)
        sys_info = types.Content(parts=[types.Part(text=system_raw)]) if system_raw else None
        
        cumulative_google = 0
        enc = tiktoken.get_encoding("cl100k_base")

        for i in range(len(messages)):
            # Solo calculamos el coste en los turnos donde el modelo responde
            if messages[i].get('role') not in ['assistant', 'model']:
                continue

            # 1. VENTANA DESLIZANTE (Últimos 50 mensajes)
            start_idx = max(0, i - 49)
            current_window = messages[start_idx : i + 1]
            google_contents = []
            
            for j, msg in enumerate(current_window):
                real_idx = start_idx + j
                is_current_msg = (real_idx == i)
                
                role_raw = msg.get('role', 'user')
                content = msg.get('content') or ""
                
                # --- OPTIMIZACIÓN 1: PODA DE TOOLS (> 2000 chars) ---
                is_tool = (role_raw == 'tool' or msg.get('tool_call_id') is not None)
                if not is_current_msg and is_tool and len(content) > 2000:
                    content = content[:2000] + "... [CONTENIDO RECORTADO]"

                parts = [types.Part(text=content)]
                
                # --- OPTIMIZACIÓN 2: GESTIÓN DE PENSAMIENTOS (thought_signature) ---
                # Extraemos el pensamiento si existe
                extra_raw = msg.get('extra_content')
                thought = None
                if extra_raw:
                    try:
                        extra_data = json.loads(extra_raw) if isinstance(extra_raw, str) else extra_raw
                        thought = extra_data.get('google', {}).get('thought_signature')
                    except: pass

                # Si es un mensaje antiguo, eliminamos el pensamiento para ahorrar tokens
                # Si es el actual, lo dejamos para contar cuánto costó generarlo
                if not is_current_msg:
                    thought = None 

                # --- TOOL CALLS ---
                if 'tool_calls' in msg and msg['tool_calls']:
                    try:
                        raw_calls = msg['tool_calls']
                        calls = json.loads(raw_calls) if isinstance(raw_calls, str) else raw_calls
                        for tc in calls:
                            f_info = tc.get('function', {})
                            args = f_info.get('arguments', {})
                            if isinstance(args, str): args = json.loads(args)
                            parts.append(types.Part(function_call=types.FunctionCall(
                                name=f_info.get('name'), 
                                args=args
                            )))
                    except: pass

                gemini_role = "model" if role_raw in ['assistant', 'model'] else "user"
                
                # Creamos el contenido. Nota: thought_signature se suele enviar en campos específicos
                # del SDK si se quiere persistir, pero aquí simulamos su peso.
                google_contents.append(types.Content(role=gemini_role, parts=parts))

            # 3. CONTEO REAL CON GOOGLE
            res = client.models.count_tokens(
                model=model_id,
                contents=google_contents,
                config=types.CountTokensConfig(system_instruction=sys_info) if sys_info else None
            )
            cumulative_google += res.total_tokens

        # --- RESULTADOS FINALES ---
        dpg.set_value("res_title_text", f"ANÁLISIS AGRESIVO: {conv_title}")
        dpg.set_value("res_google", f"{cumulative_google:,}")
        
        # Referencia Bruta (Sistema + todo el contenido sin recortes ni ventanas)
        brute_text = system_raw + "".join([(m.get('content') or "") for m in messages])
        tk_bruto = len(enc.encode(brute_text))
        dpg.set_value("res_tiktoken", f"{tk_bruto:,}")
        
        ahorro = (tk_bruto * len(messages)/2) - cumulative_google # Estimación de ahorro acumulado
        dpg.set_value("res_diff", f"Gasto total estimado: {cumulative_google:,} tokens")
        dpg.configure_item("res_diff", color=(0, 255, 255))
        
        dpg.configure_item("modal_results", show=True)
        dpg.set_value("status_bar", "✅ Auditoría de tokens completada.")

    except Exception as e:
        import traceback
        traceback.print_exc()
        dpg.set_value("status_bar", f"❌ Error: {str(e)}")
def refresh_list():
    dpg.set_value("status_bar", "🔄 Actualizando...")
    dpg.delete_item("messages_container", children_only=True)
    
    convs = get_conversations()
    if not convs:
        dpg.add_text("Sin conexión o sin datos.", parent="messages_container", color=(255, 100, 100))
        dpg.set_value("status_bar", "⚠️ Error de conexión")
        return

    for c in convs:
        c_id = c.get('id')
        title = c.get('title', 'Sin título')
        with dpg.group(parent="messages_container", horizontal=True):
            dpg.add_button(label="📊 Analizar", callback=calculate_tokens, user_data=(c_id, title))
            dpg.add_text(f"{title}", color=(200, 220, 255))
    
    dpg.set_value("status_bar", f"Lista lista ({len(convs)} convs)")

# ==============================================================================
# INTERFAZ GRÁFICA
# ==============================================================================

dpg.create_context()
dpg.create_viewport(title='Gemini Token Counter', width=550, height=650)

with dpg.window(tag="primary_window"):

    dpg.add_text("GEMINI TOKEN ANALYZER", color=(0, 255, 255))
    dpg.add_separator()

    with dpg.group():
        dpg.add_text("Configuración API")
        dpg.add_input_text(label="API Key", tag="api_key_input", password=True, width=-120)
        
        with dpg.group(horizontal=True):
            dpg.add_input_text(label="Modelo", tag="model_id_input", default_value=DEFAULT_MODEL_ID, width=250)
            dpg.add_text("(ID del modelo)", color=(150, 150, 150))
    
    dpg.add_separator()
    dpg.add_button(label="🔄 Recargar Conversaciones", callback=refresh_list, height=30)
    dpg.add_text("Listo", tag="status_bar", color=(255, 255, 0))
    dpg.add_separator()

    dpg.add_child_window(tag="messages_container", border=True, height=-1)

# MODAL
with dpg.window(label="Resultados", modal=True, show=False, tag="modal_results", width=400, height=280):
    dpg.add_text("Análisis de Consumo", color=(0, 255, 255))
    dpg.add_text("", tag="res_title_text", wrap=380)
    dpg.add_separator()

    with dpg.table(header_row=True, borders_innerH=True, borders_outerH=True, borders_innerV=True, borders_outerV=True):
        dpg.add_table_column(label="Método")
        dpg.add_table_column(label="Tokens")
        with dpg.table_row():
            dpg.add_text("Tiktoken")
            dpg.add_text("0", tag="res_tiktoken")
        with dpg.table_row():
            dpg.add_text("Google API")
            dpg.add_text("0", tag="res_google")
            
    dpg.add_spacer(height=10)
    dpg.add_text("Diferencia:")
    dpg.add_text("0", tag="res_diff")
    
    dpg.add_spacer(height=20)
    dpg.add_button(label="Cerrar", width=100, callback=lambda: dpg.configure_item("modal_results", show=False))

dpg.setup_dearpygui()
dpg.show_viewport()
dpg.set_primary_window("primary_window", True)
dpg.start_dearpygui()
dpg.destroy_context()