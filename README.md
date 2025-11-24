# Diseño y análisis de un agente LLM autónomo para auditorías de ciberseguridad en entornos aislados

**Autor:** Alejandro Barrena Millán  
**Fecha:** 14 de noviembre de 2025  
**Tipo de Proyecto:** Trabajo de Fin de Grado (TFG)

---

## 1. Idea del Proyecto

El objetivo principal es desarrollar una aplicación que integre un chatbot basado en un **Large Language Model (LLM)** con acceso autónomo a herramientas de ciberseguridad en una terminal. 

El flujo de trabajo propuesto es:
1. El usuario solicita una auditoría.
2. El LLM decide qué comandos ejecutar.
3. El sistema interpreta los resultados.
4. Se genera un informe final de la auditoría.

## 2. Motivación

Los LLMs actuales son potentes pero están limitados a responder preguntas teóricas. Darles acceso a herramientas reales de pentesting abre posibilidades muy interesantes:

* **Democratización:** Facilitar auditorías básicas para personas sin conocimientos profundos.
* **Automatización inteligente:** Un sistema que se adapta dinámicamente según los resultados que obtiene (no solo scripts estáticos).
* **Asistente:** Aceleración de tareas repetitivas en ciberseguridad.

Sin embargo, esto conlleva riesgos que hacen el proyecto técnicamente relevante:
* ¿Qué pasa con el *prompt injection*?
* ¿Puede manipularse el modelo para ejecutar comandos peligrosos?
* ¿Es posible manipular el resultado de una auditoría si el LLM analiza un archivo malicioso diseñado para engañarlo?

## 3. Objetivos

### 3.1. Objetivos Principales (Alcanzables)
1.  **Desarrollo de la aplicación:** Crear un sistema que conecte el LLM con una terminal/sandbox e integre herramientas de ciberseguridad (`nmap`, `nikto`, `sqlmap`, etc.).
2.  **Validación funcional:** Montar entornos de prueba con vulnerabilidades conocidas (como DVWA, Metasploitable) y evaluar si el LLM detecta y reporta los fallos correctamente.

### 3.2. Objetivos Secundarios (Si el tiempo lo permite)
1.  **Análisis contra prompt injection:** Diseñar ataques para manipular al LLM e implementar contramedidas.
2.  **Prevención de escalada de privilegios:** Asegurar que el agente no ejecute comandos peligrosos y probar ataques que intenten engañar al sistema.
3.  **Evaluación adversarial:** Batería de prompts maliciosos y estudio de robustez.

## 4. Tecnologías Base

* **LLM:** Posiblemente Gemini, OpenRouter (API), o modelos locales como Llama/Mistral (o despliegue en supercomputador).
* **Terminal Sandbox:** `Docker` para aislar la ejecución y garantizar la seguridad del host.
* **Herramientas de Auditoría:** `Kali Linux toolkit` (Nmap, Nikto, SQLMap, etc.).

## 5. Resultados Esperados

1.  Una aplicación funcional que demuestre la Prueba de Concepto (PoC).
2.  Pruebas que validen la utilidad práctica del sistema.
3.  Un análisis detallado de las limitaciones, especialmente en el ámbito de la seguridad.
4.  *(Opcional)* Estudio sobre prompt injection y contramedidas defensivas.

---

> **Aviso Legal:** Este proyecto ha sido desarrollado con fines estrictamente académicos y de investigación. El uso de herramientas de auditoría ofensiva debe realizarse únicamente en entornos controlados y autorizados. El autor no se hace responsable del mal uso de este software.
