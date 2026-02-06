import requests
import json
import dearpygui.dearpygui as dpg
import google.generativeai as genai
import tiktoken

# Configuración del servidor local
BASE_URL = "http://localhost:4000"

def get_conversations():
    try:
        response = requests.get(f"{BASE_URL}/conversations", timeout=5)
        response.raise_for_status()
        return response.json().get('conversations', [])
    except: return []

def calculate_tokens(sender, app_data, user_data):
    conv_id, conv_title = user_data
    api_key = dpg.get_value("api_key_input")
    
    if not api_key:
        dpg.set_value("status_bar", "⚠️ Error: Introduce tu Gemini API Key primero.")
        return

    try:
        # 1. Obtener el hilo
        response = requests.get(f"{BASE_URL}/conversations/{conv_id}/thread", timeout=10)
        thread_data = response.json()
        messages = thread_data.get('messages', [])

        # --- CONTEO CON TIKTOKEN (cl100k_base) ---
        enc = tiktoken.get_encoding("cl100k_base")
        tk_input, tk_output = 0, 0
        
        # --- PREPARAR PARA API GOOGLE ---
        google_contents = []

        for msg in messages:
            role = str(msg.get('role', '')).lower()
            # Mapeo de roles para Google: 'user' o 'model'
            g_role = "user" if role in ["user", "system"] else "model"
            content = msg.get('content', '') or ""
            
            # Sumar a tiktoken
            tokens_local = len(enc.encode(content))
            if g_role == "user": tk_input += tokens_local
            else: tk_output += tokens_local
            
            # Añadir a lista de Google
            google_contents.append({"role": g_role, "parts": [content]})

        # --- CONTEO CON API GOOGLE ---
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Llamada oficial
        google_res = model.count_tokens(contents=google_contents)
        api_total = google_res.total_tokens

        # --- MOSTRAR COMPARATIVA ---
        dpg.set_value("res_title", f"Charla: {conv_title}")
        
        # Valores Tiktoken
        dpg.set_value("tk_in", f"Entrada: {tk_input}")
        dpg.set_value("tk_out", f"Salida: {tk_output}")
        dpg.set_value("tk_total", f"Total: {tk_input + tk_output}")
        
        # Valores API Google
        dpg.set_value("api_total_val", f"Total Real (API): {api_total}")
        
        # Diferencia
        diff = ((tk_input + tk_output) - api_total)
        perc = (diff / api_total * 100) if api_total > 0 else 0
        dpg.set_value("diff_val", f"Diferencia: {diff} tokens ({perc:.2f}%)")
        dpg.set_value("diff_val", color=(255, 100, 100) if abs(perc) > 5 else (100, 255, 100))

        dpg.configure_item("results_modal", show=True)
        dpg.set_value("status_bar", "✓ Conteo completado")

    except Exception as e:
        dpg.set_value("status_bar", f"Error: {str(e)}")

def refresh_list():
    dpg.delete_item("conv_list_group", children_only=True)
    convs = get_conversations()
    for conv in convs:
        cid, title = conv.get('id'), conv.get('title', "Sin título")
        dpg.add_button(label=f"📊 Comparar: {title}", width=-1, parent="conv_list_group",
                       callback=calculate_tokens, user_data=(cid, title))

# --- UI ---
dpg.create_context()
with dpg.window(label="TokenCounter PRO: API vs Tiktoken", tag="main"):
    with dpg.group(horizontal=True):
        dpg.add_text("API Key:")
        dpg.add_input_text(tag="api_key_input", password=True, width=300)
    
    dpg.add_button(label="🔄 Refrescar Conversaciones", callback=refresh_list)
    dpg.add_separator()
    dpg.add_group(tag="conv_list_group")
    dpg.add_text("Listo", tag="status_bar", color=(150, 150, 150))

# Ventana de Resultados
with dpg.window(label="Comparativa de Tokenización", modal=True, show=False, tag="results_modal", width=400):
    dpg.add_text("", tag="res_title", color=(100, 200, 255))
    dpg.add_separator()
    
    with dpg.group(horizontal=True):
        with dpg.child_window(width=180, height=120, label="Tiktoken (OpenAI)"):
            dpg.add_text("Tiktoken (Local)", color=(200, 200, 0))
            dpg.add_text("", tag="tk_in")
            dpg.add_text("", tag="tk_out")
            dpg.add_text("", tag="tk_total")
            
        with dpg.child_window(width=180, height=120, label="Google API"):
            dpg.add_text("Google API (Real)", color=(0, 200, 200))
            dpg.add_spacer(height=15)
            dpg.add_text("", tag="api_total_val")
            
    dpg.add_separator()
    dpg.add_text("", tag="diff_val")
    dpg.add_button(label="Cerrar", callback=lambda: dpg.configure_item("results_modal", show=False))

dpg.create_viewport(title='TokenCounter Pro', width=500, height=600)
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.set_primary_window("main", True)
dpg.start_dearpygui()
dpg.destroy_context()


"""
pip install dearpygui requests google-generativeai tiktoken
"""