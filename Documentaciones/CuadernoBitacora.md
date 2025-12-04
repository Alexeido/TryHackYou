# Cuaderno de Bitácora

# Sprint 2 - Sandbox Terminal

## Objetivos del Sprint
Los objetivos principales para este sprint son:

1. **Desarrollar una API funcional** que permita la interacción con un entorno de sandbox terminal
2. **Implementar un sandbox terminal** mediante contenedores Docker, que actúe como entorno aislado de ejecución
3. **Crear una máquina víctima de pruebas** para validar las capacidades del sistema
4. **Establecer la interconexión** entre el sandbox terminal y la máquina víctima, permitiendo que ambos componentes se comuniquen de forma efectiva

El enfoque de este sprint es construir los cimientos técnicos del proyecto, estableciendo la infraestructura base sobre la que se desarrollarán las funcionalidades más avanzadas en sprints posteriores.

---

## Resumen de la semana del 24 Noviembre
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

Objetivos para hoy:

- ~~**Selección de LLMs locales:** Evaluar modelos locales según disponibilidad de VRAM preparar una lista corta de opciones según VRAM.~~
- ~~**Relleno de anexos del TFG:** Preguntar si tengo que hacer algo en docs o simplemente memoria.~~
- **Análisis de requisitos para el siguiente sprint (integración LLM):** Definir las interfaces API necesarias, estructura de datos y flujos de comunicación entre el agente y el modelo LLM.

Criterios de éxito:

- Lista de modelos LLM candidatos con notas sobre compatibilidad por VRAM.
- Anexos del TFG rellenados.
- Backlog inicial del siguiente sprint con tareas claras y estimaciones.

**Estado actual:** En progreso