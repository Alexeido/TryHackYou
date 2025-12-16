import os
import json
import sys
import datetime
from openai import OpenAI
from colorama import init, Fore, Style

# Inicializar colores
init(autoreset=True)

# 1. CONFIGURACIÓN
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print(Fore.RED + "❌ Error: Define la variable de entorno GEMINI_API_KEY")
    sys.exit(1)

client = OpenAI(
    api_key=api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

def guardar_sesion_txt(history, modelo):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"sesion_{timestamp}.txt"
    
    print(Fore.YELLOW + f"\n💾 Guardando sesión en {filename}...")

    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"REGISTRO DE SESION TFG\n")
        f.write(f"Fecha: {datetime.datetime.now()}\n")
        f.write(f"Modelo: {modelo}\n")
        f.write("=" * 80 + "\n\n")

        for msg in history:
            if isinstance(msg, dict):
                role = msg.get('role')
                content = msg.get('content')
                tool_calls = msg.get('tool_calls')
                tool_call_id = msg.get('tool_call_id')
                name = msg.get('name')
            else:
                role = getattr(msg, 'role', 'unknown')
                content = getattr(msg, 'content', None)
                tool_calls = getattr(msg, 'tool_calls', None)
                tool_call_id = getattr(msg, 'tool_call_id', None)
                name = None

            if role == "system":
                f.write(f"SYSTEM: {content}\n\n")
            
            elif role == "user":
                f.write(f"USER:\n{content}\n\n")
            
            elif role == "assistant":
                f.write(f"AI ({modelo}):\n")
                if content:
                    f.write(f"{content}\n\n")
                
                if tool_calls:
                    f.write("TOOL REQUEST:\n")
                    for tc in tool_calls:
                        if hasattr(tc, 'function'):
                            fn_name = str(tc.function.name)
                            fn_args = str(tc.function.arguments)
                            fn_id = str(tc.id)
                        else:
                            fn_name = str(tc['function']['name'])
                            fn_args = str(tc['function']['arguments'])
                            fn_id = str(tc['id'])

                        f.write(f"Function: {fn_name}\n")
                        f.write(f"ID: {fn_id}\n")
                        f.write(f"Args: {fn_args}\n\n")

            elif role == "tool":
                f.write(f"TOOL OUTPUT:\n")
                f.write(f"ID: {tool_call_id}\n")
                f.write(f"Name: {name}\n")
                f.write(f"{content}\n\n")
            
            f.write("-" * 80 + "\n\n")

    print(Fore.GREEN + "✅ Sesión guardada en TXT correctamente.")
  
# --- FUNCION PARA GUARDAR LOG RAW (CORREGIDA) ---
def guardar_sesion_raw(history, modelo):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"sesion_raw_{timestamp}.json"
    
    print(Fore.YELLOW + f"\n💾 Guardando sesión RAW en {filename}...")

    serializable_history = []
    
    for msg in history:
        if isinstance(msg, dict):
            # Si ya es un dict (mensajes del usuario o tools manuales), lo guardamos tal cual
            serializable_history.append(msg)
        else:
            # Si es un objeto de OpenAI, usamos model_dump() si existe (v1+)
            # o __dict__ como fallback, asegurando que sea serializable
            try:
                if hasattr(msg, 'model_dump'):
                    msg_dict = msg.model_dump()
                else:
                    msg_dict = msg.__dict__.copy()
                
                # Limpieza extra: Convertir tool_calls si son objetos dentro del dict
                if msg_dict.get('tool_calls'):
                    tool_calls_clean = []
                    for tc in msg_dict['tool_calls']:
                        if hasattr(tc, 'model_dump'):
                            tool_calls_clean.append(tc.model_dump())
                        elif hasattr(tc, '__dict__'):
                            # Caso manual si falla model_dump
                            tc_data = {
                                "id": getattr(tc, 'id', None),
                                "type": getattr(tc, 'type', 'function'),
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            }
                            tool_calls_clean.append(tc_data)
                        else:
                            tool_calls_clean.append(tc)
                    msg_dict['tool_calls'] = tool_calls_clean
                
                serializable_history.append(msg_dict)
            except Exception as e:
                print(Fore.RED + f"⚠️ Error serializando mensaje: {e}")
                serializable_history.append({"role": "error", "content": str(msg)})

    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump({
                "fecha": str(datetime.datetime.now()),
                "modelo": modelo,
                "historial": serializable_history
            }, f, indent=4, ensure_ascii=False)
        print(Fore.GREEN + "✅ Sesión guardada en RAW correctamente.")
    except Exception as e:
        print(Fore.RED + f"❌ Error final escribiendo JSON: {e}")
        
# --- FUNCIÓN PARA GUARDAR LOG EN MARKDOWN ---
def guardar_sesion_md(history, modelo):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"sesion_{timestamp}.md"
    
    print(Fore.YELLOW + f"\n💾 Guardando sesión en {filename}...")

    with open(filename, "w", encoding="utf-8") as f:
        # Cabecera del archivo
        f.write(f"# 📝 Registro de Sesión TFG\n")
        f.write(f"- **Fecha:** {datetime.datetime.now()}\n")
        f.write(f"- **Modelo:** `{modelo}`\n")
        f.write("---\n\n")

        for msg in history:
            # Detectar si es Objeto (API) o Diccionario (Manual)
            if isinstance(msg, dict):
                role = msg.get('role')
                content = msg.get('content')
                tool_calls = msg.get('tool_calls')
                tool_call_id = msg.get('tool_call_id')
                name = msg.get('name')
            else:
                # Es un objeto de OpenAI
                role = getattr(msg, 'role', 'unknown')
                content = getattr(msg, 'content', None)
                tool_calls = getattr(msg, 'tool_calls', None)
                tool_call_id = getattr(msg, 'tool_call_id', None)
                # En objetos OpenAI, el nombre suele ir dentro de tool_calls o no estar en top level
                name = None 

            # ESCRIBIR EN EL MARKDOWN SEGÚN EL ROL
            if role == "system":
                f.write(f"> **⚙️ SYSTEM:** {content}\n\n")
            
            elif role == "user":
                f.write(f"## 👤 USER\n{content}\n\n")
            
            elif role == "assistant":
                f.write(f"## 🤖 AI ({modelo})\n")
                if content:
                    f.write(f"{content}\n\n")
                
                if tool_calls:
                    f.write("### 🛠️ Tool Request (Intención de Comando)\n")
                    for tc in tool_calls:
                        # Manejo de si tc es objeto o dict
                        if hasattr(tc, 'function'):
                            fn_name = str(tc.function.name)
                            fn_args = str(tc.function.arguments)
                            fn_id = str(tc.id)
                        else:
                            fn_name = str(tc['function']['name'])
                            fn_args = str(tc['function']['arguments'])
                            fn_id = str(tc['id'])

                        f.write("```json\n")
                        f.write(f"Function: {fn_name}\n")
                        f.write(f"ID:       {fn_id}\n")
                        f.write(f"Args:     {fn_args}\n")
                        f.write("```\n\n")

            elif role == "tool":
                f.write(f"### 📦 TOOL OUTPUT (Respuesta del Sistema)\n")
                f.write(f"- **ID:** `{tool_call_id}`\n")
                f.write(f"- **Name:** `{name}`\n")
                f.write("```json\n")
                f.write(f"{content}\n")
                f.write("```\n\n")
            
            f.write("---\n")

    print(Fore.GREEN + "✅ Sesión guardada correctamente.")

# 2. LISTAR Y SELECCIONAR
def seleccionar_modelo():
    print(Fore.CYAN + "📡 Listando modelos...")
    try:
        models = client.models.list()
        available = [m.id for m in models if "gemini" in m.id]
        available.sort()
        
        if not available: return "gemini-1.5-flash"

        print(Fore.YELLOW + "\n--- MODELOS ---")
        for i, m in enumerate(available):
            print(f"{i+1}. {m}")
        
        idx = int(input(Fore.YELLOW + "\nElige número: ")) - 1
        return available[idx] if 0 <= idx < len(available) else available[0]

    except:
        return "gemini-1.5-flash"

# 3. SCHEMA
tools_schema = [{
    "type": "function",
    "function": {
        "name": "ejecutar_comando_secreto",
        "description": "Herramienta de prueba.",
        "parameters": {
            "type": "object",
            "properties": {
                "comando": {"type": "string"},
                "razon": {"type": "string"}
            },
            "required": ["comando"]
        }
    }
}]

# 4. LOOP PRINCIPAL
def chat_loop():
    modelo = seleccionar_modelo()
    print(Fore.YELLOW + f"\n🤖 Usando: {modelo} | Escribe 'salir' para guardar y cerrar.\n")

    history = [{"role": "system", "content": "Eres un experto en ciberseguridad. Usa 'ejecutar_comando_secreto' si es necesario."}]
    pending_tool = None 

    while True:
        if pending_tool:
            prompt = input(Fore.MAGENTA + f"[TOOL PENDIENTE] > " + Style.RESET_ALL)
        else:
            prompt = input(Fore.GREEN + "Tú > " + Style.RESET_ALL)

        # SALIDA Y GUARDADO
        if prompt.lower() in ['salir', 'exit']:
            guardar_sesion_md(history, modelo)
            guardar_sesion_txt(history, modelo)
            guardar_sesion_raw(history, modelo)
            break

        # RESPUESTA DE TOOL MANUAL
        if pending_tool:
            if prompt.startswith("/testResponse"):
                json_falso = prompt.replace("/testResponse", "", 1).strip()
                history.append({
                    "role": "tool",
                    "tool_call_id": pending_tool.id,
                    "name": pending_tool.function.name,
                    "content": json_falso
                })
                pending_tool = None
            else:
                print(Fore.RED + "⚠️ Usa: /testResponse {...}")
                continue

        # MENSAJE NORMAL
        else:
            history.append({"role": "user", "content": prompt})

        # LLAMADA API
        try:
            print(Fore.CYAN + "...", end="\r")
            response = client.chat.completions.create(
                model=modelo,
                messages=history,
                tools=tools_schema,
                tool_choice="auto"
            )
            msg = response.choices[0].message
            print("   ", end="\r")

            # Guardar mensaje del asistente en historial
            history.append(msg)

            if msg.content:
                print(Fore.CYAN + f"AI > {msg.content}")

            if msg.tool_calls:
                tc = msg.tool_calls[0]
                pending_tool = tc
                print(Fore.MAGENTA + f"🛠️  PIDE TOOL: {tc.function.arguments}")
                print(Fore.WHITE + "👉 Escribe: /testResponse {\"res\": \"ok\"}")

        except Exception as e:
            print(Fore.RED + f"Error: {e}")

if __name__ == "__main__":
    chat_loop()