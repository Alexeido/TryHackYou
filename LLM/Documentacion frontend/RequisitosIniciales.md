Aquí tienes el documento de arquitectura técnica definitivo para el Frontend de tu TFG. Está diseñado pensando en escalabilidad, limpieza de código y facilidad de integración con Docker.

---

# 📐 Arquitectura Técnica Frontend - TFG Ciberseguridad

Este documento define el stack tecnológico, la estructura de datos y la lógica de interfaz para el cliente web del Agente de Ciberseguridad.

## 1. Stack Tecnológico

Hemos seleccionado un stack moderno ("Golden Stack 2025") que prioriza la velocidad de desarrollo y la calidad visual profesional.

| Capa | Tecnología | Justificación |
| :--- | :--- | :--- |
| **Framework** | **Next.js 14 (App Router)** | Estándar industrial, enrutamiento por carpetas, optimización automática. |
| **UI Library** | **Shadcn/UI** | Componentes accesibles y pre-diseñados (copy-paste) que se instalan en tu código. |
| **Estilos** | **Tailwind CSS** | Estilado rápido sin archivos CSS externos. Integración nativa con Shadcn. |
| **Iconos** | **Lucide React** | Iconografía limpia y ligera, estándar en Shadcn. |
| **Estado Global** | **Zustand** | Gestión de estado (chats activos, configuración) más simple y ligera que Redux. |
| **Data Fetching** | **TanStack Query (React Query)** | Manejo de caché, *loading states* y reintentos automáticos para las peticiones al Backend. |
| **HTTP Client** | **Axios** | Cliente HTTP robusto para comunicarse con la API Python. |
| **Markdown** | **React Markdown** | Para renderizar las respuestas del LLM con formato y bloques de código. |

---

## 2. Arquitectura de Interfaz (Layout)

El diseño se basa en un **"Resizable Layout"** de 3 columnas, similar a los IDEs modernos (VS Code).

### 🖥️ Estructura Visual (Desktop)

1.  **Columna Izquierda (Sidebar - 20%)**
    * **Top:** Botón `[+ Nuevo Chat]`.
    * **Center:** Lista scrolleable de historiales (agrupados por "Hoy", "Ayer", "7 días").
    * **Bottom:** Botón `[⚙️ Configuración]` (Abre Modal).
2.  **Columna Central (Main Chat - 50-80%)**
    * **Header:** Modelo actual y estado (Online/Offline), si tocamos en el nombre se nos abre un menú similar al de configuracion donde nos aparece el buscador de modelos, donde nos deja cambiar el orden y pulsar el boton de agrupar, no agrupar y una barrita de busqueda para buscar rapido el deseado.
    * **Body:** Scroll infinito de mensajes (`User` vs `AI`). Renderizado de Markdown.
    * **Footer:** Input de texto + Botón enviar + Aviso de "Use Client".
3.  **Columna Derecha (Terminal / Logs - 0-30%)**
    * **Comportamiento:** Inicialmente `width: 0` (Oculto).
    * **Trigger:** Se despliega automáticamente si el LLM envía un `tool_call`.
    * **Contenido:** Logs crudos de ejecución, JSONs de respuesta de herramientas y outputs de comandos.
    * **Controles:** Botón `[x]` para cerrar/colapsar manualmente.

---

## 3. Gestión de Datos y Estado

Separamos estrictamente qué datos viven en el navegador del usuario y cuáles en el servidor.

### 🔐 A. LocalStorage (Navegador)
Datos sensibles o preferencias de UI que **no** deben guardarse en base de datos por privacidad o persistencia de sesión local.

* `api_keys`: Objeto JSON con las claves `{ openai: "sk-...", google: "AIza..." }`.
* `ui_preferences`: `{ theme: "dark", sidebar_collapsed: false }`.
* `custom_instructions`: String con el System Prompt personalizado del usuario.



### 🗄️ Esquema de Base de Datos (SQLite)

Necesitamos dos tablas. Fíjate en los campos `created_at` y `updated_at`.

#### 1\. Tabla `conversations` (La lista de la izquierda)

Guarda la "carpeta" del chat.

| Columna | Tipo | Descripción |
| :--- | :--- | :--- |
| `id` | `UUID` o `INT` (PK) | Identificador único del chat. |
| `title` | `TEXT` | "Chat sobre Ciberseguridad" (Se puede generar auto). |
| `created_at` | `DATETIME` | Cuándo se creó el chat (para ordenar históricos). |
| **`updated_at`** | **`DATETIME`** | **CRUCIAL:** Cuándo fue el último mensaje. Sirve para poner este chat arriba del todo en la lista izquierda cuando llega un mensaje nuevo. |

#### 2\. Tabla `messages` (El contenido central)

Guarda los bocadillos del chat.

| Columna | Tipo | Descripción |
| :--- | :--- | :--- |
| `id` | `INT` (PK, Auto-inc) | Identificador único del mensaje. |
| `conversation_id` | `UUID` (FK) | **Clave foránea:** A qué chat pertenece. |
| `role` | `TEXT` | `user`, `assistant`, `system` o `tool`. |
| `content` | `TEXT` | El texto del mensaje. |
| `tool_calls` | `JSON` | (Opcional) Si el modelo pidió usar herramientas. |
| `tool_call_id` | `TEXT` | (Opcional) ID para vincular la respuesta de una tool con su petición. |
| **`created_at`** | **`DATETIME`** | **LO QUE FALTABA:** La fecha y hora exacta (con milisegundos) de creación. |














### 🔄 C. Flujo de Datos (Data Flow)

1.  **Envío:** Usuario escribe -> Frontend coge API Key de `localStorage` -> Envía POST `/chat` al Backend.
2.  **Recepción:** Procesamos -> Guardamos en SQLite -> Respondemos al Frontend.
3.  **Sincronización:** `TanStack Query` detecta el cambio y actualiza la lista de la izquierda y el chat central.

---

## 4. Componentes Clave (Shadcn/UI)

Para montar esto rápido, usaremos estos componentes específicos de la librería:

* **`Resizable`:** Para las 3 columnas ajustables.
* **`ScrollArea`:** Para las listas de chat y el terminal (evita barras de scroll feas del navegador).
* **`Dialog`:** Para la ventana modal de Configuración.
* **`Tabs`:** Dentro de Configuración, para separar "General", "Instrucciones", "API Keys".
* **`Switch`:** Para activar/desactivar Modo Oscuro.
* **`Card`:** Para envolver los mensajes del chat.
* **`Badge`:** Para mostrar el estado del modelo (ej: "GPT-4" o "Gemini").

---

## 5. Estrategia de Configuración (El Modal)

El botón de configuración abrirá un **Dialog** central con pestañas:

1.  **Apariencia:**
    * Toggle `Modo Oscuro` / `Modo Claro`.
2.  **Cerebro (Instrucciones):**
    * Textarea grande para editar el `SYSTEM_PROMPT` que se envía al inicio de cada chat.
    * Esto permite cambiar la "personalidad" del agente sin tocar código.
3.  **Conexiones (API Keys):**
    * Inputs tipo `password` para cada proveedor (OpenAI, Google, DeepSeek).
    * Botón "Guardar en Navegador" (Persiste en LocalStorage).

---

## 6. Dockerización (El Plan Final)

El objetivo es tener un `docker-compose.yml` que levante todo el ecosistema.

### Dockerfile del Frontend
Usaremos una construcción "Multi-stage" para que la imagen final sea ligera (usando `standalone` output de Next.js).

1.  **Stage Builder:** Instala dependencias y compila (`npm run build`).
2.  **Stage Runner:** Imagen Alpine mínima con Node.js, copia solo la carpeta `.next/standalone` y `public`.
3.  **Puerto:** Expone el `3000`.

### Integración
El Frontend no sabrá si el backend está en `localhost` o en otro contenedor. Usaremos una variable de entorno `NEXT_PUBLIC_API_URL` que apuntará a `http://backend_container:8000`.

---

## ✅ Resumen de Acción (Roadmap)

1.  **Inicialización:** `npx create-next-app` + `npx shadcn init`.
2.  **Layout:** Implementar `ResizablePanelGroup` para las 3 columnas.
3.  **Store:** Configurar `Zustand` para manejar el estado de las columnas y las Keys.
4.  **API Client:** Configurar `Axios` para inyectar automáticamente las Keys del LocalStorage en los headers.
5.  **Componente Chat:** Crear el bucle de mensajes y renderizado Markdown.
6.  **Componente Terminal:** Crear el visor de logs condicional.
7.  **Modal Config:** Crear el formulario de Keys.