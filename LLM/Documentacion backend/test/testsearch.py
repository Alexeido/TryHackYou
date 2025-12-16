import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import requests
import threading
import json

# --- CONFIGURACIÓN ---
API_URL = "http://127.0.0.1:8000/models/discover"

# TUS CLAVES POR DEFECTO
DEFAULT_KEYS = {
    "openai_key": "***REMOVED***",
    "gemini_key": "***REMOVED***",
    "anthropic_key": "string",
    "deepseek_key": "***REMOVED***",
    "openrouter_key": "***REMOVED***"
}

class ModelTesterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🧪 Testeador de Cerebro LLM (TFG)")
        self.root.geometry("900x700")
        
        # Estilos
        style = ttk.Style()
        style.theme_use('clam')
        
        # --- FRAME DE PAYLOAD PREVIEW (DERECHA) ---
        payload_frame = ttk.LabelFrame(root, text="📤 Payload Preview (Copy to Postman/Swagger)", padding=10)
        payload_frame.pack(fill="both", expand=True, padx=10, pady=5, side="right")
        
        self.payload_text = scrolledtext.ScrolledText(payload_frame, font=("Consolas", 9), height=20, state="disabled")
        self.payload_text.pack(fill="both", expand=True)
        
        # --- FRAME DE KEYS Y OPCIONES (IZQUIERDA) ---
        left_frame = ttk.Frame(root)
        left_frame.pack(fill="both", expand=True, padx=10, pady=5, side="left")
        
        # --- FRAME DE KEYS (ARRIBA IZQUIERDA) ---
        input_frame = ttk.LabelFrame(left_frame, text="🔐 API Keys", padding=10)
        input_frame.pack(fill="x", pady=5)
        
        self.entries = {}
        row = 0
        for provider, key in DEFAULT_KEYS.items():
            ttk.Label(input_frame, text=provider.replace("_key", "").upper() + ":").grid(row=row, column=0, sticky="w", padx=5)
            entry = ttk.Entry(input_frame, width=60)
            entry.insert(0, key) # Pre-rellenar
            entry.grid(row=row, column=1, padx=5, pady=2)
            self.entries[provider] = entry
            row += 1

        # --- FRAME DE OPCIONES (ABAJO IZQUIERDA) ---
        opts_frame = ttk.LabelFrame(left_frame, text="⚙️ Filtros y Orden", padding=10)
        opts_frame.pack(fill="x", pady=5)
        
        # Sorting
        ttk.Label(opts_frame, text="Ordenar por:").pack(side="left", padx=5)
        self.sort_var = tk.StringVar(value="default")
        self.combo_sort = ttk.Combobox(opts_frame, textvariable=self.sort_var, values=["default", "ranking", "context"], state="readonly")
        self.combo_sort.pack(side="left", padx=5)
        
        # Checkboxes
        self.var_group = tk.BooleanVar(value=False)
        self.var_snap = tk.BooleanVar(value=False)
        self.var_free = tk.BooleanVar(value=False)
        
        ttk.Checkbutton(opts_frame, text="Agrupar por Proveedor", variable=self.var_group).pack(side="left", padx=10)
        ttk.Checkbutton(opts_frame, text="Mostrar Snapshots (Antiguos)", variable=self.var_snap).pack(side="left", padx=10)
        ttk.Checkbutton(opts_frame, text="Solo Gratis (OpenRouter)", variable=self.var_free).pack(side="left", padx=10)

        # Botón
        self.btn_search = ttk.Button(opts_frame, text="🔍 DESCUBRIR MODELOS", command=self.start_search)
        self.btn_search.pack(side="right", padx=10)

        # --- FRAME DE RESULTADOS (ABAJO) ---
        res_frame = ttk.LabelFrame(root, text="📄 Resultados", padding=10)
        res_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.text_area = scrolledtext.ScrolledText(res_frame, font=("Consolas", 10), state="disabled")
        self.text_area.pack(fill="both", expand=True)
        
        # Tags de colores
        self.text_area.tag_config("title", foreground="blue", font=("Consolas", 11, "bold"))
        self.text_area.tag_config("score", foreground="green", font=("Consolas", 10, "bold"))
        self.text_area.tag_config("provider", foreground="magenta")
        self.text_area.tag_config("error", foreground="red")

        # Configurar actualización en tiempo real del payload
        self.setup_payload_traces()
        self.update_payload_preview()  # Inicial

    def setup_payload_traces(self):
        """Configura traces para actualizar el payload en tiempo real."""
        # Traces para entries
        for provider in DEFAULT_KEYS.keys():
            self.entries[provider].bind("<KeyRelease>", lambda e: self.update_payload_preview())
        
        # Traces para variables
        self.sort_var.trace_add("write", lambda *args: self.update_payload_preview())
        self.var_group.trace_add("write", lambda *args: self.update_payload_preview())
        self.var_snap.trace_add("write", lambda *args: self.update_payload_preview())
        self.var_free.trace_add("write", lambda *args: self.update_payload_preview())

    def update_payload_preview(self):
        """Actualiza el preview del payload JSON."""
        payload = {
            "openai_key": self.entries["openai_key"].get(),
            "gemini_key": self.entries["gemini_key"].get(),
            "anthropic_key": self.entries["anthropic_key"].get(),
            "deepseek_key": self.entries["deepseek_key"].get(),
            "openrouter_key": self.entries["openrouter_key"].get(),
            "sorting": self.sort_var.get(),
            "group": self.var_group.get(),
            "snapshots": self.var_snap.get(),
            "openrouter_free": self.var_free.get()
        }
        
        # Formatear como JSON bonito
        json_str = json.dumps(payload, indent=2, ensure_ascii=False)
        
        self.payload_text.config(state="normal")
        self.payload_text.delete(1.0, tk.END)
        self.payload_text.insert(tk.END, json_str)
        self.payload_text.config(state="disabled")

    def start_search(self):
        # Desactivar botón
        self.btn_search.config(state="disabled")
        self.status_var.set("⏳ Consultando APIs... Por favor espere.")
        
        # Limpiar texto
        self.text_area.config(state="normal")
        self.text_area.delete(1.0, tk.END)
        self.text_area.config(state="disabled")
        
        # Recoger datos
        payload = {
            "openai_key": self.entries["openai_key"].get(),
            "gemini_key": self.entries["gemini_key"].get(),
            "anthropic_key": self.entries["anthropic_key"].get(),
            "deepseek_key": self.entries["deepseek_key"].get(),
            "openrouter_key": self.entries["openrouter_key"].get(),
            "sorting": self.sort_var.get(),
            "group": self.var_group.get(),
            "snapshots": self.var_snap.get(),
            "openrouter_free": self.var_free.get()
        }
        
        # Ejecutar en hilo secundario para no congelar la GUI
        threading.Thread(target=self.fetch_data, args=(payload,), daemon=True).start()

    def fetch_data(self, payload):
        try:
            response = requests.post(API_URL, json=payload)
            data = response.json()
            
            # Volver al hilo principal para actualizar GUI
            self.root.after(0, self.display_results, data)
            
        except Exception as e:
            self.root.after(0, self.display_error, str(e))

    def display_results(self, data):
        self.text_area.config(state="normal")
        
        total = data.get("total", 0)
        models = data.get("models", [])
        
        header = f"✅ Búsqueda completada. Total encontrados: {total}\n"
        header += "-" * 80 + "\n\n"
        self.text_area.insert(tk.END, header)
        
        if total == 0:
            self.text_area.insert(tk.END, "⚠️ No se encontraron modelos. Revisa las API Keys o los filtros.\n", "error")

        for m in models:
            # Icono según score
            score = m.get('elo_score', 0)
            icon = "⭐" if score > 1200 else "🔹" if score > 1100 else "🔸"
            
            # Línea 1: Título
            line_title = f"{icon} [{score}] {m['name']}\n"
            self.text_area.insert(tk.END, line_title, "title")
            
            # Línea 2: Detalles
            provider = m['provider'].upper()
            ctx = f"{m['context_window']:,}" if m['context_window'] else "?"
            
            # Precios
            p_in = m.get('pricing_input', 0)
            p_out = m.get('pricing_output', 0)
            price_str = f"In: ${p_in:.2f} / Out: ${p_out:.2f}" if (p_in or p_out) else "Precios desconocidos"
            
            details = f"    🏢 Provider: {provider} | 🧠 Context: {ctx} tokens | 💰 {price_str}\n"
            self.text_area.insert(tk.END, details)
            
            # Línea 3: ID Técnico
            self.text_area.insert(tk.END, f"    🆔 ID: {m['id']}\n\n")

        self.text_area.config(state="disabled")
        self.status_var.set("Listo.")
        self.btn_search.config(state="normal")

    def display_error(self, error_msg):
        self.text_area.config(state="normal")
        self.text_area.insert(tk.END, f"\n❌ ERROR DE CONEXIÓN:\n{error_msg}\n", "error")
        self.text_area.insert(tk.END, "\n Asegúrate de que el backend está corriendo: 'uvicorn main:app --reload'")
        self.text_area.config(state="disabled")
        self.status_var.set("Error.")
        self.btn_search.config(state="normal")
        messagebox.showerror("Error", f"Fallo al conectar con la API:\n{error_msg}")

if __name__ == "__main__":
    root = tk.Tk()
    app = ModelTesterApp(root)
    root.mainloop()