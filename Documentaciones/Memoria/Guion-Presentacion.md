
# **ESTRUCTURA DE DEFENSA TFG: TryHackYou**

## **BLOQUE 1: CONTEXTO Y FUNDAMENTACIÓN**

### **Slide 1: Portada**

* **Visual:** Título, logos UEX, nombre y tutores.
* **Guion:** "Buenos días. Mi nombre es Alejandro Barrena Millán y presento mi TFG: **'Diseño y análisis de un agente LLM autónomo para auditorías de ciberseguridad en entornos aislados'**. Tutorizado por Pablo García y Alberto Fernández, este trabajo explora cómo la IA puede pasar de ser un asistente a un operador autónomo en ciberseguridad."

### **Slide 2: Agradecimientos (Fundación COMPUTAEX)**

* **Visual:** Logotipo de Computaex y especificaciones (2x NVIDIA RTX A4500).
* **Guion:** "Antes de entrar en materia, mi agradecimiento a la **Fundación COMPUTAEX**. La cesión de sus nodos de alto rendimiento fue la pieza clave para evaluar modelos de gran escala (hasta 30B) en un entorno privado, algo que hoy es vital para la soberanía del dato en las empresas."

### **Slide 3: Índice**

* **Visual:** Lista numerada (Intro, Objetivos, Estado del Arte, Metodología, Arquitectura, Resultados, Conclusiones).
* **Guion:** "Seguiremos este orden: contextualizaremos el problema, explicaremos la arquitectura técnica de la herramienta **TryHackYou**, analizaremos los resultados obtenidos en laboratorios reales y cerraremos con las conclusiones."

### **Slide 4: Introducción**

* **Visual:** Imágenes 1 y 2 (Evolución IA y Sociedad Digital).
* **Guion:** "Estamos en una transformación histórica. La IA ha evolucionado del simple microchip al agente con capacidad de acción. Vivimos en una sociedad digital con dependencia total de dispositivos conectados, lo que ha disparado la superficie de ataque a niveles que la intervención manual ya no puede cubrir."

### **Slide 5: Motivación**

* **Visual:** Imagen 3 (Brecha de seguridad: barra alta de usuarios vs barra baja de expertos).
* **Guion:** "La realidad es preocupante: hay una brecha crítica de profesionales. Mientras el número de usuarios y dispositivos crece exponencialmente, el de expertos en ciberseguridad no lo hace al mismo ritmo. Mi motivación es crear un 'multiplicador de fuerza': una IA que ayude al auditor a automatizar lo tedioso para centrarse en lo crítico."

### **Slide 6: Objetivos**

* **Visual:** Cuadrados rounded con iconos de Sandbox, Razonamiento, HITL y Benchmarking.
* **Guion:** "El objetivo principal es crear **TryHackYou**: un ecosistema agéntico para auditorías proactivas. Para ello, nos propusimos cuatro hitos: una arquitectura aislada en Docker, un motor de razonamiento capaz de tomar decisiones, una interfaz de supervisión humana y una comparativa exhaustiva entre modelos Cloud y Locales."

### **Slide 7: Alcance**

* **Visual:** Iconos de Red interna, Laboratorios y Seguridad.
* **Guion:** "El alcance se centra en auditorías de red interna y aplicaciones web. No pretendemos sustituir al humano, sino dotarle de una herramienta que gestione el ciclo de vida del pentesting en entornos controlados, analizando incluso los riesgos de 'Prompt Injection' que la propia IA podría sufrir."

---

## **BLOQUE 2: ESTADO DEL ARTE Y METODOLOGÍA**

### **Slide 8: Estado del Arte I - Agentes Autónomos**

* **Visual:** Imagen de los 4 módulos (Perfil, Memoria, Planificación, Acción).
* **Guion:** "¿Qué es un agente autónomo? Es una entidad que percibe, razona y actúa. Su 'cerebro' es el LLM, pero se apoya en cuatro módulos: el **Perfil** define sus reglas; la **Memoria** gestiona el contexto; la **Planificación** permite no improvisar mediante *Chain-of-Thought*; y la **Acción** usa el *Function Calling* para ejecutar comandos reales."

### **Slide 9: Estado del Arte II - Herramientas Actuales**

* **Visual:** Comparativa PentestGPT (CLI) vs AutoAttacker.
* **Guion:** "Hoy la referencia es **PentestGPT**, una herramienta de terminal brillante pero con barreras: es compleja de usar para no expertos y no genera informes estructurados. Por otro lado, trabajos como **AutoAttacker** usan aprendizaje por refuerzo. Mi propuesta busca unir la potencia técnica con una interfaz visual que fomente la cultura de seguridad."

### **Slide 10: Metodología**

* **Visual:** Tablero GitHub Projects y gráfico de horas (315h).
* **Guion:** "He seguido un **SCRUM Adaptado** en 7 Sprints. Gracias a completar la base antes de tiempo, pivoté para reinvertir horas en calidad técnica. Gestioné **107 tareas en GitHub Projects**, acumulando un total de **315 horas** de ejecución real para pasar de un prototipo a un sistema robusto."

---

## **BLOQUE 3: IMPLEMENTACIÓN (CORE TÉCNICO)**

### **Slide 11: Visión General de Arquitectura**

* **Visual:** Icono arquitectura microservicios. Diagrama de bloques (Frontend, Backend, Sandbox).
* **Guion:** "TryHackYou se basa en tres microservicios desacoplados. Esto garantiza que si el agente comete un error en el sandbox, el resto del sistema sigue intacto. Usamos **FastAPI** para la lógica y **Next.js** para la interfaz, comunicados mediante eventos en tiempo real (SSE)."

### **Slide 12: KaliSandbox y Persistencia**

* **Visual:** Iconos Docker, Kali, Git y Flask. Esquema de commits.
* **Guion:** "El sandbox es un contenedor Kali Linux aislado. La gran innovación es la **Persistencia con Git**: cada comando del agente genera un 'commit'. Si el agente se equivoca o el sistema de archivos cambia, podemos revertir el estado o crear ramas de investigación, manteniendo el contexto de la IA siempre alineado con la realidad del sistema."

### **Slide 13: Backend LLM I - Orquestación y Estructura**

* **Visual:** Iconos Proveedor LLM, SQLite, Árbol y Misiones.
* **Guion:** "(DETALLADO) El Backend es el cerebro orquestador. Implementé un **Patrón Factory** que permite conectar cualquier modelo (OpenAI, Anthropic o los locales en COMPUTAEX) de forma transparente. A diferencia de un chat normal, aquí guardamos todo en un **árbol de mensajes en SQLite**. Esto permite que el agente 'ramifique' su pensamiento: si una vía de ataque falla, vuelve al nodo anterior y explora otra opción. Además, gestionamos la auditoría mediante **Misiones**: el sistema descompone un objetivo grande en pequeñas tareas técnicas que el agente va completando y reportando."

### **Slide 14: Backend LLM II - Loop Agéntico y Seguridad**

* **Visual:** Imágenes Loop Agéntico y Sistema de Seguridad.
* **Guion:** "(DETALLADO) El corazón del sistema es un loop continuo: **Razonamiento -> Acción -> Observación**. Pero lo más crítico es mi capa de **Seguridad Human-in-the-Loop**. He desarrollado un clasificador que analiza cada comando antes de ejecutarlo. Si el agente intenta algo peligroso, el Backend bloquea la ejecución y pide permiso al humano. Esto nos permite tener un agente autónomo para lo rutinario pero bajo control total en lo crítico. También aplicamos una **Optimización de Contexto** constante (imagen de embudo) para que el agente no se sature con logs infinitos y mantenga el foco en el objetivo."

### **Slide 15: Frontend LLM**

* **Visual:** Captura del Mission Board y panel de aprobación.
* **Guion:** "El Frontend en Next.js es la ventana del auditor. Su pieza central es el **Mission Board**, donde se ve el progreso de la misión en tiempo real. Está diseñado para reducir la carga cognitiva: el humano no necesita leer miles de líneas de log, solo supervisar las decisiones que el Backend marca como relevantes."

---

## **BLOQUE 4: RESULTADOS Y CONCLUSIONES**

### **Slide 16: Configuración Experimental**

* **Visual:** Imágenes de DVWA, Metasploitable 2 y Juice Shop.
* **Guion:** "Validamos el sistema en 14 auditorías reales contra tres entornos: **DVWA** (web clásica), **Metasploitable2** (red e infraestructura) y **Juice Shop** (aplicación moderna SPA). Evaluamos 8 modelos divididos en tres niveles: Local, HPC (Computaex) y Cloud."

### **Slide 17: Resultados: La Brecha de Eficacia**

* **Visual:** Gráfico de barras (Cloud 100% vs resto).
* **Guion:** "Los resultados son claros: los modelos **Cloud logran un 100% de éxito**. Sin embargo, en el entorno **HPC obtuvimos un hito**: el modelo **gpt-oss 20b** logró una shell y escalada de privilegios en Metasploitable2. Esto confirma que por encima de los 20B de parámetros, la IA local empieza a ser útil para seguridad, mientras que los modelos pequeños (<7B) colapsan por alucinaciones."

### **Slide 18: Análisis del Sistema HITL**

* **Visual:** Gráfico de tarta (90% safe vs 4% critical) y métrica de 92.8% precisión.
* **Guion:** "Nuestro sistema de seguridad funcionó con una **precisión del 92.8%**. Lo más importante es la fluidez: el humano solo tuvo que intervenir en el **4% de los comandos**. Logramos un sistema que es autónomo para trabajar, pero que sabe cuándo detenerse y pedir ayuda, con solo un 0.78% de falsos negativos en scripts muy complejos."

### **Slide 19: Conclusiones**

* **Visual:** Resumen de checks (Arquitectura, Persistencia, HITL).
* **Guion:** "Concluyendo: hemos construido una arquitectura de microservicios funcional y persistente. Hemos demostrado que la autonomía supervisada es el camino equilibrado y hemos identificado la barrera técnica de los modelos locales. Aunque postergué el análisis adversario para priorizar la estabilidad, la base de TryHackYou es sólida."

### **Slide 20: Trabajos Futuros y Cierre**

* **Visual:** QR al repositorio GitHub y puntos de futuro (AST Parser, RAG).
* **Guion:** "El futuro pasa por mejorar el clasificador de riesgo con un **parser AST** y aplicar **RAG** para una memoria a largo plazo. La viabilidad de los agentes autónomos en ciberseguridad es una realidad. Muchas gracias, queda el repositorio a su disposición y estoy abierto a sus preguntas."

