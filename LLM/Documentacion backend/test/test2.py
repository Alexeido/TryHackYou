import os
import json
import datetime
import requests
from dotenv import load_dotenv # Importante: Carga las variables del .env si existe
from colorama import init, Fore, Style

# Cargar variables de entorno desde el archivo .env (si lo tienes local)
load_dotenv()

# Inicializar colores
init(autoreset=True)

# 1. CONFIGURACIÓN DEL BACKEND
BACKEND_URL = "http://127.0.0.1:8000"

# CARGA DINÁMICA DE KEYS
# Si no encuentra la variable en el .env, la deja vacía ("").
# El backend ignorará las que estén vacías.
KEYS = {
    "gemini_key": "AIzaSyAG1O_oFwxKluVxaqW1q8Xmqbf38rZfuco",
    "openai_key": os.getenv("OPENAI_API_KEY", ""),
    "deepseek_key": os.getenv("DEEPSEEK_API_KEY", ""),
    "openrouter_key": "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",
    "anthropic_key": os.getenv("ANTHROPIC_API_KEY", "")
}

# --- FUNCIONES DE LOGGING (Simplificadas) ---

def guardar_sesion_md(history, modelo, provider):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"log_{provider}_{timestamp}.md"
    print(Fore.YELLOW + f"\n💾 Guardando MD en {filename}...")

    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# 📝 Sesión TFG - {provider.upper()}\n- **Modelo:** `{modelo}`\n---\n\n")
        for msg in history:
            role = msg.get('role')
            content = msg.get('content')
            tool_calls = msg.get('tool_calls')

            if role == "system":
                f.write(f"> **⚙️ SYSTEM:** {content}\n\n")
            elif role == "user":
                f.write(f"## 👤 USER\n{content}\n\n")
            elif role == "assistant":
                f.write(f"## 🤖 AI ({modelo})\n{content or ''}\n\n")
                if tool_calls:
                    f.write("### 🛠️ Tool Call\n```json\n")
                    f.write(json.dumps(tool_calls, indent=2))
                    f.write("\n```\n\n")
            elif role == "tool":
                f.write(f"### 📦 Output ({msg.get('name')})\n```json\n{content}\n```\n\n")
            f.write("---\n")
    print(Fore.GREEN + "✅ Guardado.")

# 2. SELECCIÓN DE MODELO
def seleccionar_modelo():
    print(Fore.CYAN + "📡 Conectando al Backend para listar modelos disponibles...")
    
    # Imprimir qué keys tenemos cargadas (Debug visual)
    active_providers = [k.replace('_key', '').upper() for k, v in KEYS.items() if v and len(v) > 5]
    print(Fore.WHITE + f"   (Keys detectadas: {', '.join(active_providers)})")

    try:
        # Enviamos TODAS las keys. Las que estén vacías, el backend las ignorará.
        payload = {
            "openai_key": KEYS["openai_key"],
            "gemini_key": KEYS["gemini_key"],
            "deepseek_key": KEYS["deepseek_key"],
            "openrouter_key": "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",
            "anthropic_key": KEYS["anthropic_key"],  
            "openrouter_free": True,
            "sorting": "ranking" # Ordenar por nota ELO
        }
        
        resp = requests.post(f"{BACKEND_URL}/models/discover", json=payload)
        
        if resp.status_code != 200:
            print(Fore.RED + f"❌ Error Backend: {resp.status_code}")
            return None, None

        data = resp.json()
        models = data.get("models", [])
        
        if not models:
            print(Fore.RED + "⚠️ El backend devolvió 0 modelos. Revisa tu .env y reinicia.")
            return None, None

        print(Fore.YELLOW + f"\n--- 🤖 MODELOS DISPONIBLES ({data['total']}) ---")
        for i, m in enumerate(models):
            # Formato bonito: ⭐ [GOOGLE] gemini-1.5-pro (Score: 1261)
            score = m.get('elo_score', 0)
            icon = "⭐" if score > 1200 else "🔹"
            print(f"{i+1}. {icon} [{m['provider'].upper()}] {m['name']} (ELO: {score})")
        
        # Selección usuario
        idx = int(input(Fore.YELLOW + "\nElige número: ")) - 1
        if 0 <= idx < len(models):
            selected = models[idx]
            return selected['provider'], selected['id']
        
        # Default fallback
        return models[0]['provider'], models[0]['id']

    except Exception as e:
        print(Fore.RED + f"⚠️ Error fatal conectando: {e}")
        return None, None

# 3. SCHEMA DE HERRAMIENTAS (Ejemplo)
tools_schema = [{
    "type": "function",
    "function": {
        "name": "ejecutar_comando_secreto",
        "description": "Herramienta de prueba.",
        "parameters": {
            "type": "object",
            "properties": {
                "comando": {"type": "string"},
            },
            "required": ["comando"]
        }
    }
}]

# 4. LOOP PRINCIPAL
def chat_loop():
    provider, modelo_id = seleccionar_modelo()
    
    if not provider:
        print(Fore.RED + "❌ No se pudo seleccionar modelo. Abortando.")
        return
    if provider == "google":
        key_name = "gemini_key"
    else:
        key_name = f"{provider}_key"
    
    current_key = KEYS.get(key_name)
    
    if not current_key:
        print(Fore.RED + f"❌ Error: No se encontró la API Key para '{provider}' (buscando '{key_name}').")
        return
    
    print(Fore.YELLOW + f"\n💬 CHAT INICIADO: {provider.upper()} -> {modelo_id}")
    print(Fore.WHITE + "Escribe 'salir' para terminar.\n")

    history = [{"role": "system", "content": "Eres un asistente útil."}]

    while True:
        prompt = input(Fore.GREEN + "Tú > " + Style.RESET_ALL)

        if prompt.lower() in ['salir', 'exit']:
            guardar_sesion_md(history, modelo_id, provider)
            break

        history.append({"role": "user", "content": prompt})

        try:
            print(Fore.CYAN + "⏳ ...", end="\r")
            
            # Payload para /chat
            payload = {
                "provider": provider,
                "api_key": current_key,
                "model_id": modelo_id,
                "messages": history,
                "tools": tools_schema
            }

            resp = requests.post(f"{BACKEND_URL}/chat", json=payload)
            print("      ", end="\r") # Limpiar espera

            if resp.status_code == 200:
                data = resp.json()
                
                # Reconstruimos mensaje
                assistant_msg = {
                    "role": data["role"],
                    "content": data["content"],
                    "tool_calls": data["tool_calls"]
                }
                history.append(assistant_msg)

                # Mostrar respuesta
                if assistant_msg["content"]:
                    print(Fore.CYAN + f"AI > {assistant_msg['content']}")
                
                # Mostrar intención de uso de herramienta
                if assistant_msg["tool_calls"]:
                    tc = assistant_msg["tool_calls"][0]
                    print(Fore.MAGENTA + f"🛠️  TOOL: {tc['function']['name']} args={tc['function']['arguments']}")
                    
                    # Simular respuesta de tool automática para que no se rompa el chat
                    history.append({
                        "role": "tool",
                        "tool_call_id": tc['id'],
                        "name": tc['function']['name'],
                        "content": '{"status": "simulado", "output": "comando ejecutado correctamente"}'
                    })
                    print(Fore.WHITE + "   (Tool simulada automáticamente)")

            else:
                print(Fore.RED + f"❌ Error API: {resp.text}")

        except Exception as e:
            print(Fore.RED + f"❌ Error local: {e}")

if __name__ == "__main__":
    chat_loop()