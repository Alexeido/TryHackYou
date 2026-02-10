
# **ESTRUCTURA DE PRESENTACIÓN TFG (≈20 minutos)**

## **1. PORTADA Y CONTEXTO** *(2 min)*
- **Slide 1:** Título, autor, tutores y fecha
- **Slide 2:** Motivación del proyecto
  - Convergencia IA + Ciberseguridad
  - Brecha de profesionales cualificados
  - Oportunidad de automatización con LLMs

---

## **2. OBJETIVOS DEL PROYECTO** *(2 min)*
- **Slide 3:** Objetivo General
  - Diseño e implementación de un agente LLM autónomo para auditorías de ciberseguridad
- **Slide 4:** Objetivos Específicos (visual con iconos)
  - Arquitectura aislada y persistente
  - Motor agéntico con razonamiento
  - Evaluación multi-modelo (local/HPC/cloud)
  - Interfaz Human-in-the-Loop
  - Validación en entornos controlados

---

## **3. ESTADO DEL ARTE** *(3 min)*
- **Slide 5:** Marco Teórico - Agentes Autónomos
  - Evolución: LLM reactivo → Agente autónomo
  - Arquitectura cognitiva (Perfil, Memoria, Planificación, Acción)
- **Slide 6:** Herramientas Actuales y Limitaciones
  - PentestGPT (referencia principal)
  - Gap identificado: falta de interfaz visual, análisis de seguridad propia limitado

---

## **4. ARQUITECTURA DEL SISTEMA** *(4 min)*
- **Slide 7:** Visión General - Microservicios
  - Diagrama de arquitectura (KaliSandbox + Backend + Frontend)
  - Flujo de comunicación (REST + SSE)
- **Slide 8:** KaliSandbox - Entorno de Ejecución
  - Contenedor Docker con Kali Linux
  - API Flask para ejecución de comandos
  - Sistema Git para persistencia por conversación
  - Red aislada con 3 máquinas víctimas
- **Slide 9:** Backend - Orquestador Inteligente
  - FastAPI con soporte multi-proveedor
  - Gestión agéntica (misiones, tool calling)
  - Base de datos SQLite con árbol de conversación
- **Slide 10:** Frontend - Interfaz de Supervisión
  - Next.js con streaming en tiempo real
  - Panel de misiones y aprobación de comandos
  - Visualización del árbol de conversación

---

## **5. METODOLOGÍA** *(2 min)*
- **Slide 11:** Gestión del Proyecto
  - Scrum adaptado (7 sprints en 12 semanas)
  - Diagrama de Gantt (planificado vs real)
  - 315 horas totales, 107 subtareas en GitHub Projects
- **Slide 12:** Configuración Experimental
  - 3 niveles de infraestructura: Local (RTX 3050) / HPC (COMPUTAEX 2x A4500) / Cloud APIs
  - 8 modelos evaluados
  - 3 entornos de prueba: DVWA / Metasploitable2 / Juice Shop

---

## **6. RESULTADOS** *(5 min)*
- **Slide 13:** Eficacia por Entorno - DVWA
  - Tabla comparativa: Cloud 100%, HPC 0%, Local 0%
  - Captura de pantalla del agente en acción
- **Slide 14:** Eficacia por Entorno - Metasploitable2
  - Primer modelo HPC exitoso (gpt-oss 20b al tercer intento)
  - Obtención de shell y escalada de privilegios con modelos Cloud
- **Slide 15:** Eficacia por Entorno - Juice Shop
  - Mayor desafío (arquitectura SPA moderna)
  - Auth Bypass y exfiltración solo en Cloud y Qwen HPC
- **Slide 16:** Gráfico Comparativo Global
  - Gráfico de barras agrupado con tasa de éxito por modelo y entorno
  - Ranking final con Score ponderado
- **Slide 17:** Human-in-the-Loop - Resultados
  - 642 comandos ejecutados, 92.8% precisión del clasificador
  - Solo 4.05% requieren aprobación (HIGH/CRITICAL)
  - 5 falsos negativos críticos (0.78%)
  - Métricas de autonomía: Cloud >94%, HPC 75-93%

---

## **7. DEMOSTRACIÓN (OPCIONAL)** *(1-2 min)*
- **Slide 18:** Capturas de Pantalla de la Interfaz
  - Panel principal con chat streaming
  - Mission Board con tareas del agente
  - Aprobación de comando peligroso
  - Terminal integrado con salida de herramientas

---

## **8. CONCLUSIONES** *(2 min)*
- **Slide 19:** Logros Alcanzados
  - ✅ Arquitectura funcional con aislamiento total
  - ✅ Modelos Cloud: 100% eficacia
  - ✅ Sistema HITL operativo con precisión >92%
  - ⚠️ Brecha significativa entre Cloud y Local/HPC
  - ❌ Análisis adversario pendiente (trabajo futuro)
- **Slide 20:** Trabajos Futuros y Cierre
  - Mejora clasificador (AST parsing)
  - Optimización dinámica de contexto
  - Validación en entornos reales complejos
  - Análisis de seguridad adversaria (prompt injection)
  - Mensaje final: viabilidad del paradigma agéntico demostrada

---
## **Extra**
### **DISTRIBUCIÓN TEMPORAL SUGERIDA:**
1. Contexto y motivación: **2 min**
2. Objetivos: **2 min**
3. Estado del arte: **3 min**
4. Arquitectura: **4 min**
5. Metodología: **2 min**
6. Resultados: **5 min**
7. Conclusiones: **2 min**
8. **Total: 20 minutos**

---

### **RECOMENDACIONES ADICIONALES:**

**Visuales clave a preparar:**
- Diagrama de arquitectura de microservicios
- Topología de red Docker con las 4 máquinas
- Cronograma Gantt comparativo (planificado vs real)
- Gráfico de barras de eficacia por entorno
- Gráfico de tarta/donut de comandos por nivel de riesgo
- Capturas de la interfaz mostrando el agente en acción

**Aspectos a enfatizar:**
- La brecha entre modelos Cloud (100% éxito) vs Local (0% éxito) es el resultado más relevante
- El sistema de persistencia con Git es innovador
- La precisión del 92.8% en HITL con solo 4.05% de comandos requiriendo aprobación demuestra equilibrio entre autonomía y seguridad
- El acceso a COMPUTAEX fue clave para la investigación HPC

**Transiciones sugeridas:**
- De estado del arte a arquitectura: "Identificadas las limitaciones, diseñamos una solución modular..."
- De arquitectura a metodología: "Para validar este diseño, seguimos una metodología ágil..."
- De metodología a resultados: "Tras 14 auditorías completas, los datos confirman..."