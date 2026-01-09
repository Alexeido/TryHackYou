# Cuaderno de Bitácora

# Indice
- [Cuaderno de Bitácora](#cuaderno-de-bitácora)
- [Indice](#indice)
- [Sprint 2 - Sandbox Terminal](#sprint-2---sandbox-terminal)
    - [Objetivos del Sprint](#objetivos-del-sprint)
    - [Resumen de la semana del 24 Noviembre](#resumen-de-la-semana-del-24-noviembre)
        - [Logros](#logros)
        - [Pruebas realizadas](#pruebas-realizadas)
    - [L 01/12/2025](#l-01122025)
    - [M 02/12/2025](#m-02122025)
- [Sprint 3 - Integración LLM](#sprint-3---integración-llm)
    - [X 03/12/2025](#x-03122025)
    - [J 04/12/2025](#j-04122025)
    - [Días 05 - 11/12/2025](#días-05---11122025)
    - [V 12/12/2025](#v-12122025)
    - [L 15/12/2025](#l-15122025)
    - [M 16/12/2025](#m-16122025)

# Sprint 2 - Sandbox Terminal

## Objetivos del Sprint
Los objetivos principales para este sprint son:

1. **Desarrollar una API funcional** que permita la interacción con un entorno de sandbox terminal
2. **Implementar un sandbox terminal** mediante contenedores Docker, que actúe como entorno aislado de ejecución
3. **Crear una máquina víctima de pruebas** para validar las capacidades del sistema
4. **Establecer la interconexión** entre el sandbox terminal y la máquina víctima, permitiendo que ambos componentes se comuniquen de forma efectiva

El enfoque de este sprint es construir los cimientos técnicos del proyecto, estableciendo la infraestructura base sobre la que se desarrollarán las funcionalidades más avanzadas en sprints posteriores.

---

## Resumen de la semana del 24 Noviembre (No hice bitácora diaria)
Esta semana se consiguió con creces implementar y validar un contenedor Docker que incluye la API para interactuar con un sandbox de Linux. El entregable principal está operativo y permite comunicación básica con el entorno aislado.

### Logros
- Imagen Docker construida y publicada localmente.
- API desarrollada e integrada en el contenedor.
- Comunicación funcional con el sandbox de Linux (ejecución de comandos y respuesta).

### Pruebas realizadas
- Despliegue del contenedor en local.
- Ejecución de comandos triviales en el sandbox mediante la API.
- Verificación de respuestas y manejo de errores básicos.



Aquí tienes la versión resumida y directa para tu bitácora:

## L **01/12/2025**

Se ha completado la orquestación del laboratorio de pruebas, evolucionando de un contenedor aislado a una infraestructura de red completa.

* **Infraestructura (Docker Compose):** Despliegue de red aislada (`10.5.0.0/24`) integrando el Agente con tres entornos vulnerables: **DVWA** (Web clásica), **Metasploitable 2** (Infraestructura) y **OWASP Juice Shop** (Web moderna).
* **Mejoras en el Agente:** Implementación de persistencia de directorios en la API (soporte para `cd`) y actualización del `Dockerfile` con herramientas para APIs (`httpie`, `LinkFinder`, `nuclei`).
* **Validación:** Ejecución exitosa de un ataque **SQL Injection** contra DVWA, logrando automatizar el login y la evasión de tokens CSRF mediante scripts.

**Estado:** Sprint 2 cerrado. Infraestructura validada y lista para la integración del LLM (Sprint 3).

## M **02/12/2025**

Jornada dedicada a la consolidación y preparación del entorno de desarrollo:

* **Corrección de bugs:** Revisión y corrección de errores identificados durante las pruebas del día anterior en la integración del laboratorio con Docker Compose.
* **Pruebas de validación:** Verificación exhaustiva del correcto funcionamiento de la comunicación entre el agente y los distintos contenedores vulnerables.
* **Instalación de LaTeX local:** Configuración del compilador LaTeX en el entorno local para facilitar la generación y edición de la documentación técnica del proyecto sin dependencias externas.

**Estado:** Entorno estabilizado y preparado para la siguiente fase del proyecto.

# Sprint 3 - Integración LLM

## X **03/12/2025**

Hoy se avanzó en la preparación para el siguiente sprint:

* **Reunión con Computaex:** Tuve una reunion con Daniel Flores para consultar la disponibilidad de GPUs y recursos para el desarrollo del proyecto.
* **Análisis de requisitos para el siguiente sprint:** Se definieron las interfaces API necesarias, la estructura de datos y los flujos de comunicación entre el agente y el modelo LLM.
* **Creación de tareas y estimaciones:** Se desglosaron las tareas en issues con prioridades y estimaciones de esfuerzo.

**Estado:** Tareas definidas, credenciales de maquinas en Computaex recibidas, correo mandado para ajustar recursos.


## J **04/12/2025**

Hoy se completaron varias tareas importantes relacionadas con la planificación y documentación del proyecto:

* **Selección de LLMs locales:** Se finalizó la lista de modelos compatibles con 32GB y 64GB de VRAM, incluyendo notas detalladas sobre su rendimiento esperado.
* **Relleno de anexos del TFG:** Se completaron los anexos requeridos, asegurando que toda la documentación esté alineada con los objetivos del proyecto.
* **Descarga de la plantilla de Latex de la memoria:** Se descargó y configuró la plantilla de LaTeX para la memoria del TFG, facilitando la redacción y formateo del documento final.
* **Creacion de ramas acorde a las tareas:** Se organizaron las ramas del repositorio Git para reflejar las tareas planificadas, facilitando el seguimiento del progreso y la colaboración futura.

**Estado:** Todo completado con éxito.



## **Días 05 - 11/12/2025**

Jornadas dedicadas íntegramente al **proyecto de la asignatura PBD**. No hubo avances en el TFG para priorizar la entrega/gestión de dicha asignatura.

**Estado:** Sin avances en TFG por PBD.


## V **12/12/2025**

Jornada dedicada al análisis profundo de la arquitectura de comunicación con LLMs:

* **Estudio del lenguaje interno de LLMs:** Se analizó cómo los modelos procesan y generan respuestas, incluyendo el formato de mensajes (roles: system, user, assistant) y el contexto conversacional.
* **Investigación de Tool Calling:** Se estudió el mecanismo de llamadas a herramientas (function calling), incluyendo la estructura de esquemas JSON, parámetros y flujo de respuestas.
* **Tests de APIs:** Se realizaron pruebas exhaustivas con distintas APIs (OpenAI, Google Gemini, OpenRouter, DeepSeek) para entender sus diferencias en implementación, formato de respuestas y manejo de herramientas.
* **Diseño de interfaz universal:** Se definió una capa de abstracción que permitirá usar múltiples proveedores de LLM de forma transparente.

**Estado:** Base teórica sólida establecida para el desarrollo del backend.

## L **15/12/2025**

Día de desarrollo intensivo del backend y herramientas de prueba:

* **Desarrollo de la API Backend:** Se implementó el servidor FastAPI con endpoints para:
  - `/models/discover`: Descubrimiento dinámico de modelos de múltiples proveedores en paralelo.
  - `/chat`: Endpoint universal de chat compatible con tool calling.
* **Sistema de ranking automático:** Se integró un sistema de puntuación ELO basado en el LMArena Leaderboard, con fallback local y fuzzy matching inteligente.
* **Documentación Swagger:** Se generó documentación automática interactiva en `/docs` para facilitar las pruebas.
* **Frontend de pruebas (Tkinter):** Se creó una interfaz gráfica para:
  - Listar y filtrar modelos disponibles según proveedor, puntuación y características.
  - Ordenar modelos por ranking, contexto o proveedor.
  - Filtrar por opciones específicas (solo gratuitos, snapshots, etc.).
* **Integración multi-proveedor:** Soporte funcional para OpenAI, Google Gemini, DeepSeek, OpenRouter y Anthropic.

**Estado:** API completamente funcional con documentación y herramientas de testing operativas.

Aquí tienes la actualización de tu cuaderno de bitácora, adaptada con el lenguaje técnico adecuado y reflejando fielmente los avances que has descrito.



## M **16/12/2025**

Jornada de definición tecnológica y arquitectura del cliente web:

* **Definición del Tech Stack "Golden Stack 2025":** Se ha seleccionado un conjunto de tecnologías de vanguardia para garantizar un rendimiento profesional y una estética de "herramienta de ciberseguridad":
* **Framework:** Next.js 14 (App Router) para optimización y enrutamiento avanzado.
* **UI Library:** Shadcn/UI basado en Radix UI para componentes altamente accesibles.
* **Estilos:** Tailwind CSS para un diseño ágil y consistente.
* **Iconos:** Lucide React para una iconografía técnica ligera.
* **Estado Global:** Zustand para una gestión de estado ligera y persistente.
* **Data Fetching:** TanStack Query para la sincronización asíncrona con el backend.
* **Markdown:** React Markdown para el renderizado de código y respuestas técnicas.


* **Inicialización del Proyecto:** Configuración de la estructura de directorios, alias de importación y temas (dark mode por defecto).

**Estado:** Stack tecnológico cerrado y entorno de desarrollo configurado.



## X **17/12/2025**

Integración del ecosistema y diseño de persistencia avanzada:

* **Integración Frontend-Backend:** Conexión exitosa del cliente web con los endpoints de descubrimiento de modelos. Se implementaron filtros complejos y sistemas de ordenación (ELO, latencia, proveedores) aprovechando la lógica de ranking del backend.
* **Diseño de Base de Datos Cronológica:** Estudio de necesidades para la persistencia de chats. Se ha definido una estructura de datos en **árbol (N-ary Tree)** que permita:
* Almacenar conversaciones de forma relacional.
* Implementar "branching" (ramas) para permitir al usuario editar mensajes y explorar diferentes caminos de respuesta sin perder el historial original.


* **Implementación de Streaming:** Se ha añadido soporte en el backend para la generación de respuestas mediante **Server-Sent Events (SSE)**, permitiendo una experiencia de usuario fluida (token a token).
* **Hito Visual:** Interfaz de chat completamente funcional con renderizado de código y selección dinámica de modelos.

**Estado:** Frontend operativo como chat de IA; arquitectura de persistencia diseñada.



## J **18/12/2025**

Aislamiento de procesos y gestión de estado del sistema (Sandbox Isolation):

* **Aislamiento de Directorios por Conversación:** Para evitar colisiones de archivos y contaminación de contexto, se ha modificado el backend del sandbox (Kali Linux). Ahora, cada conversación posee su propia carpeta aislada en el sistema de archivos del contenedor.
* **Sistema de Control de Versiones para el Estado (Git Integration):** Se ha implementado una solución innovadora utilizando **Git** dentro de cada carpeta de chat:
* Se realiza un *commit/checkout* automático por cada mensaje enviado/recibido.
* Si el usuario vuelve a una rama anterior del chat, el sandbox ejecuta un `git checkout` al estado exacto de ese mensaje, eliminando archivos residuales o cambios en el sistema que no existían en ese punto.


* **Persistencia de Recursos Globales:** Creación de una carpeta de persistencia compartida para almacenar herramientas pesadas, diccionarios de fuerza bruta y bases de datos que deben sobrevivir al reinicio de los chats.
* **Cierre del Círculo:** El LLM ya es capaz de ejecutar comandos en la terminal de forma autónoma y recibir el output procesado.

**Estado:** Bucle de ejecución técnica completado. Pendiente: optimización de prompts para ciclos de razonamiento autónomo.



## V **19/12/2025**

Jornada de estabilización y refinamiento técnico:

* **QA & Bug Fixing:** Corrección de errores al alternar ramas justo despues de un comando.
* **Interfaz de Ajustes:** Rediseño del panel de configuración (Shadcn/UI) para parámetros de inferencia: Temperatura, Top-P, Penalties y Max Tokens.
* **Sistema de Compatibilidad:** Implementación de una lógica de filtrado en el backend que valida y bloquea parámetros no soportados según el proveedor/modelo, evitando errores de API.

**Estado:** Sistema robusto y configuración de modelos optimizada. Listo para el desarrollo de ciclos autónomos.

---


Arreglada compatibilidad con gemini 3 flash preview, mejor interfaz, procesos activos visibles

Para mañana: que vaya el botón de stop, que pueda ver el estado de los procesos activos en la terminal pese a que ya haya pasado el mensaje de respuesta y ya empezar con modelos locales