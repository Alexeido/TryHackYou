# 🧠 Requisitos del Backend (Controlador Universal) - Sprint 3
**Proyecto:** Agente LLM Autónomo de Ciberseguridad  
**Fase:** Integración del Cerebro (LLM)  
**Responsable:** Alejandro Barrena Millán

---

## 1. Visión General
El Backend actuará como el **cerebro y orquestador** del sistema. No es solo un pasarela de APIs; es un microservicio inteligente encargado de gestionar la identidad del agente, la memoria de la conversación, la selección de modelos en tiempo real y la interpretación de comandos para el entorno Docker.

**Arquitectura:** Microservicio independiente (Python) que expone una API REST para el Frontend y consume las APIs de los proveedores de IA y la API del Agente Docker.

---

## 2. Requisitos Funcionales Críticos

### 2.1. Gestión Universal de Proveedores (Multi-LLM)
El sistema debe actuar como un *wrapper* agnóstico, permitiendo cambiar de proveedor mediante configuración o selección dinámica sin alterar el código base.

* **Proveedores Soportados:**
    * [x] **OpenAI** (GPT-3.5, GPT-4o).
    * [x] **OpenRouter** (Agregador para Llama 3, Mistral, etc.).
    * [x] **DeepSeek** (Especializado en código/hacking).
    * [x] **Google Gemini** (API Nativa/Vertex AI).
    * [x] **Anthropic** (Claude 3.5 Sonnet/Opus).
    * [x] **Perplexity** (Modelos con acceso a internet/búsqueda).
    * [x] **Ollama** (Modelos locales/offline para entornos aislados).
* **Gestión de Credenciales:** Carga segura de API Keys (variables de entorno `.env` o entrada segura desde Frontend, no hardcoded).

### 2.2. Descubrimiento Dinámico de Modelos (Anti-Deuda Técnica)
El sistema **no debe usar listas estáticas** de modelos. Debe descubrir qué ofrece cada proveedor en el momento de la ejecución.

* **Fetching en Tiempo Real:** Implementar llamadas al endpoint `GET /models` (o equivalente) de cada proveedor configurado.
* **Normalización:** Estandarizar la respuesta de todos los proveedores en un formato JSON común para el frontend (ej: `{ "id": "...", "provider": "...", "context_window": ... }`).
* **Ranking/Tiering Lógico:** Implementar una capa lógica que ordene o etiquete los modelos según su capacidad ("Inteligencia"), para facilitar la selección al usuario (ej: separar modelos "Chat" de modelos "Instruct" o "Embedding").

### 2.3. Motor de Chat y Gestión de Memoria (Contexto)
Dado que las APIs de LLM son *stateless* (sin estado), el backend es responsable de la continuidad.

* **Historial de Sesión:** Mantener un array de objetos (`role`, `content`) que persista durante la ejecución de la auditoría.
* **System Prompt Injection:** Inyectar automáticamente al inicio de cada conversación las instrucciones maestras:
    * Definición de rol ("Eres un experto en Red Team").
    * Reglas de seguridad y ética.
    * Reglas de formato de salida (JSON para comandos).
* **Gestión de Errores de API:** Manejo robusto de *Rate Limits* (429), *Context Length Exceeded* y *Timeouts*.

### 2.4. Middleware de Interpretación de Comandos (Parser)
El "puente" entre el pensamiento (Texto) y la acción (Docker).

* **Detección de Intención:** Analizar cada respuesta del LLM para detectar que parte contiene comandos a ejecutar y no espera una respuesta del usuario sino del comando.
* **Parser Estricto:** Extraer comandos formateados (ej: Bloques de código \`\`\`bash o JSON estructurado).
* **Ejecución Remota:** Enviar el comando extraído a la API del Agente (Sprint 2) en `http://localhost:5000/execute`.
* **Bucle de Feedback:** Recibir el `stdout` o `stderr` del Docker e inyectarlo de nuevo en el chat como un mensaje de sistema ("Tool Output"), para que el LLM sepa qué pasó y decida el siguiente paso.

---

## 3. Endpoints de la API (Backend Interface)
Pendiente de definir en detalle, solo esquema rellenable.
El Backend expondrá estos endpoints para que el Frontend (Web) los consuma:
| Método | Endpoint               | Descripción                                      | Payload / Respuesta                          |
|--------|------------------------|--------------------------------------------------|----------------------------------------------|

---

## 4. Requisitos No Funcionales

* **Tecnología:** Python 3.10+ (Framework sugerido: FastAPI o Flask).
* **Estándar de Código:** PEP 8. Código modular (Separar lógica de conexión, lógica de chat y lógica de parser).
* **Logging:** Registro detallado en consola de qué está haciendo el "Cerebro" (para depuración).
* **Simplicidad:** Uso de librerías estándar compatibles con OpenAI (`openai` python package) para la mayoría de conexiones, aislando las excepciones (Google/Anthropic) en adaptadores específicos.

---

## 5. Diagrama de Flujo (Lógica del Agente)

```mermaid
graph TD
    User[Usuario Web] -->|Mensaje| API[Backend Controller]
    API -->|Prompt + Historial| LLM[Proveedor IA]
    LLM -->|Respuesta Texto + JSON| API
    API -->|¿Hay comando?| Parser{Parser}
    
    Parser -->|No| User
    Parser -->|Sí: Comando| Docker[Agente Docker API]
    
    Docker -->|Ejecución| Tools[Herramientas Kali]
    Tools -->|Output/Error| Docker
    Docker -->|Resultado JSON| API
    
    API -->|Inyectar Resultado en Contexto| LLM
    LLM -->|Análisis del Resultado| API
    API -->|Respuesta Final| User