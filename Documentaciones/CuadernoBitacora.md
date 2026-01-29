# Cuaderno de Bitácora

# Indice
- [Cuaderno de Bitácora](#cuaderno-de-bitácora)
- [Indice](#indice)
- [Sprint 2 - Sandbox Terminal](#sprint-2---sandbox-terminal)
  - [Objetivos del Sprint](#objetivos-del-sprint)
  - [Resumen de la semana del 24 Noviembre (No hice bitácora diaria)](#resumen-de-la-semana-del-24-noviembre-no-hice-bitácora-diaria)
    - [Logros](#logros)
    - [Pruebas realizadas](#pruebas-realizadas)
  - [L **01/12/2025**](#l-01122025)
  - [M **02/12/2025**](#m-02122025)
- [Sprint 3 - Integración LLM](#sprint-3---integración-llm)
  - [X **03/12/2025**](#x-03122025)
  - [J **04/12/2025**](#j-04122025)
  - [**Días 05 - 11/12/2025**](#días-05---11122025)
  - [V **12/12/2025**](#v-12122025)
  - [L **15/12/2025**](#l-15122025)
  - [M **16/12/2025**](#m-16122025)
  - [X **17/12/2025**](#x-17122025)
  - [J **18/12/2025**](#j-18122025)
  - [V **19/12/2025**](#v-19122025)
  - [L **22/12/2025**](#l-22122025)
  - [M **23/12/2025**](#m-23122025)
  - [J **08/01/2026**](#j-08012026)
  - [V **09/01/2026**](#v-09012026)
  - [L **12/01/2026**](#l-12012026)
  - [M **13/01/2026**](#m-13012026)
  - [X **14/01/2026**](#x-14012026)
  - [J **15/01/2026**](#j-15012026)
  - [V **16/01/2026**](#v-16012026)
  - [L **19/01/2026** y M **20/01/2026**](#l-19012026-y-m-20012026)

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

## L **22/12/2025**

Estudio de viabilidad para ejecución local y optimización de hardware:

* **Investigación de Modelos Locales:** Análisis de modelos compatibles con entornos de recursos limitados, específicamente para la **RTX 3050 (4GB VRAM)**.
* **Cuantización de Modelos:** Pruebas con formatos **GGUF y AWQ (4-bit/3-bit)** para reducir el uso de memoria sin degradar excesivamente la coherencia del modelo. Se evaluaron modelos de parámetros reducidos (SLMs) como **Phi-3 Mini**, **Qwen-2.5-Coder** y **Gemma 2B**.
* **Benchmarking de Rendimiento:** Comparativa de velocidad de inferencia (tokens/seg) y consumo de VRAM para asegurar que el backend pueda coexistir con el entorno Docker del sandbox sin provocar desbordamientos de memoria (*OOM errors*).

**Estado:** Selección de modelos locales finalizada para modo "offline" o de bajo consumo.


## M **23/12/2025**

Despliegue en infraestructura de alto rendimiento (HPC):

* **Acceso a Computaex:** Validación de credenciales y primera conexión al supercomputador **Lusitania**. Revisión del entorno operativo basado en nodos con **2 NVIDIA RTX A4500 (20GB VRAM)**.
* **Documentación Técnica:** Estudio del sistema de colas y gestión de recursos del HPC para la ejecución de contenedores y servicios persistentes.
* **Estrategia de Modelos Especializados:** Investigación para el despliegue de **SecLLMs** (Modelos de lenguaje específicos para Ciberseguridad) de mayor escala (7B, 13B y superiores), como **WhiteRabbitNeo**, que requieren el ancho de banda y la capacidad de las GPUs A4500 para el análisis profundo de tráfico y código vulnerable.

**Estado:** Infraestructura HPC preparada para tareas de computación intensiva y modelos de ciberseguridad avanzados.

## J **08/01/2026**

Optimización de modelos y robustez en la interacción con el Sandbox:

* **Compatibilidad con Modelos Avanzados:** Integración y ajuste del backend para soportar **Gemini 3.0 Flash (Experimental/Preview)**, optimizando el manejo de ventanas de contexto extensas.
* **Mejora de la Interfaz de Terminal:** Rediseño del panel de salida de comandos para mejorar la legibilidad y la distinción entre comandos ejecutados y respuestas del sistema.
* **Monitorización de Procesos:** Implementación visual de los procesos activos en el sandbox, permitiendo un seguimiento en tiempo real de las tareas del agente.
* **Mitigación de Alucinaciones:** Investigación y desarrollo de estrategias de control para evitar alucinaciones del LLM ante ausencias de respuestas de herramientas (*tool responses*), mejorando la lógica de reintento.

**Estado:** Interfaz del terminal refinada y compatibilidad de modelos ampliada.


## V **09/01/2026**

Gestión avanzada de procesos asíncronos y preparación para la autonomía:

* **Ejecución en Segundo Plano (Backgrounding):** Implementación de la capacidad de lanzar procesos en el sandbox que persistan de forma asíncrona, liberando el hilo principal del chat.
* **Control de Ciclo de Vida de Procesos:** Desarrollo de funciones para revisar el estado, monitorizar la salida y detener (kill) procesos en ejecución desde la interfaz.
* **Callback del Sandbox al LLM:** Implementación de un sistema de notificaciones automáticas donde los procesos finalizados interactúan directamente con la IA al terminar, eliminando la necesidad de que el usuario actúe como intermediario.
* **Refactorización de UI y Bug Fixing:** Limpieza de errores en la gestión de estados y mejoras generales en la experiencia de usuario (UX) en múltiples secciones del frontend.
* **Preparación de Ciclos Autónomos:** Sentadas las bases lógicas para los ciclos de razonamiento funcionales que se implementarán a continuación.

**Estado:** Día altamente productivo; sistema de procesos asíncronos operativo y listo para la autonomía completa.


## L **12/01/2026**

Optimización de la gestión de contexto para modelos con ventana limitada:

* **Resumen Automático de Salidas de Terminal:** Implementación de un sistema donde las salidas extensas de comandos son procesadas por un LLM auxiliar para generar resúmenes concisos que conservan la información crítica.
* **Gestión Dinámica de Contexto:** Se ha desarrollado un mecanismo de "Zoom In" que permite al modelo expandir bajo demanda mensajes y salidas previamente resumidas cuando necesita más detalles para tomar decisiones.
* **Límite de Contexto Conversacional:** Se ha establecido un sistema de recorte automático que mantiene activos únicamente los **últimos 30 mensajes**, priorizando la información reciente y mejorando el rendimiento en modelos con ventanas de contexto reducidas.
* **Memoria Selectiva:** Desarrollo de una estrategia para identificar y preservar mensajes de alta relevancia que deben persistir más allá del límite de los 30 mensajes.

**Estado:** Sistema de gestión de contexto optimizado para modelos con limitaciones de ventana.


## M **13/01/2026**

Implementación de planificación agéntica y memoria persistente:

* **Sistema de Planificación Estructurada:** Desarrollo de un mecanismo donde el LLM puede crear un plan detallado antes de ejecutar acciones, definiendo objetivos, subtareas y dependencias.
* **Panel de Planes (Mission Board):** Implementación de una interfaz visual que muestra el estado actual del plan con tareas marcadas como completadas o pendientes mediante checkboxes.
* **Memoria Persistente Independiente del Contexto:** Creación de un sistema donde el agente puede almacenar información crítica (descubrimientos, credenciales, vectores de ataque) que sobrevive al recorte de contexto conversacional.
* **Tracking de Progreso:** El LLM ahora puede actualizar automáticamente el estado de cada subtarea, marcando checks conforme avanza en la ejecución del plan.
* **Integración con Backend:** Desarrollo de endpoints `/missions` para crear, actualizar y consultar el estado de los planes agénticos.

**Estado:** Sistema de planificación implementado; agente capaz de mantener objetivos a largo plazo.


## X **14/01/2026**

Jornada de estabilización y refinamiento del sistema de planes:

* **Corrección de Sincronización:** Resolución de problemas de race conditions en la actualización simultánea de estados de tareas entre frontend y backend.
* **Bug Fixing en la Persistencia:** Corrección de errores relacionados con la actualización de planes tras la navegación entre ramas del chat.
* **Optimización de Renderizado:** Mejora del rendimiento del componente del Mission Board para evitar re-renders innecesarios.
* **Validación de Estados:** Implementación de validaciones para evitar estados incoherentes en el ciclo de vida de las misiones.
* **Testing End-to-End:** Pruebas exhaustivas del flujo completo: creación de plan → ejecución de tareas → actualización de estado → persistencia.

**Estado:** Sistema de planificación estabilizado y funcional.


## J **15/01/2026**

Optimización del comportamiento del agente y refinamiento del prompt system:

* **Reingeniería del System Prompt:** Rediseño completo del prompt del sistema para fomentar la perseverancia y proactividad del agente ante obstáculos.
* **Anti-Resignation Logic:** Implementación de instrucciones explícitas que incentivan al modelo a:
  - Intentar múltiples enfoques ante fallos.
  - Analizar errores y adaptar la estrategia antes de rendirse.
  - Buscar alternativas creativas cuando el camino directo no funciona.
* **Ciclos de Razonamiento Mejorados:** Ajuste de las directrices para que el agente descomponga problemas complejos en pasos más pequeños y manejables.
* **Testing de Comportamiento:** Validación del nuevo comportamiento mediante escenarios adversos (comandos fallidos, recursos inaccesibles, información incompleta).

**Estado:** Agente significativamente más resiliente y autónomo en la resolución de problemas.


## V **16/01/2026**

Testing integral del sistema y documentación técnica:

* **Batería de Pruebas Funcionales:** Ejecución de escenarios de prueba complejos que abarcan:
  - Reconocimiento de objetivos vulnerables.
  - Explotación de servicios con herramientas especializadas.
  - Gestión de múltiples vectores de ataque simultáneos.
* **Documentación de Flujos de Trabajo:** Inicio de la redacción de documentación técnica detallando:
  - Arquitectura del sistema completo.
  - Flujo de datos entre componentes.
  - Casos de uso y patrones de interacción.
* **Generación de Diagramas:** Creación de diagramas de secuencia y arquitectura para la memoria del TFG.
* **Recopilación de Métricas:** Medición de tiempos de respuesta, uso de recursos y tasa de éxito en tareas autónomas.

**Estado:** Sistema validado mediante testing; documentación técnica iniciada.


## L **19/01/2026** y M **20/01/2026**

Consolidación de la documentación del proyecto:

* **Redacción de Capítulos de la Memoria:** Avances significativos en los capítulos de Implementación y Desarrollo, detallando decisiones técnicas y arquitectura del sistema.
* **Documentación de Integraciones:** Descripción exhaustiva de la integración multi-proveedor de LLMs, manejo de APIs y gestión de errores.
* **Análisis de Resultados:** Documentación de pruebas realizadas, métricas obtenidas y comparativas de rendimiento entre distintos modelos.
* **Refinamiento de Diagramas:** Actualización y mejora de los diagramas de arquitectura, flujos de datos y casos de uso para mayor claridad.
* **Preparación de Anexos:** Organización de código fuente relevante, configuraciones y logs de pruebas para los anexos del TFG.

**Estado:** Documentación sustancialmente avanzada; práctica finalizada con éxito.