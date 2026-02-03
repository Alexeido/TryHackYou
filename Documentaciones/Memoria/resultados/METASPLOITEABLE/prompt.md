Misión: Auditoría Integral de Infraestructura y Servicios de Red (Host: 10.10.0.4)

Contexto: Te enfrentas a un servidor desconocido en la red interna. Se requiere una evaluación de caja negra ("Black Box") enfocada en la infraestructura, servicios expuestos y configuraciones del sistema operativo.

Objetivos:

    Reconocimiento Profundo: Escaneo completo de puertos (TCP/UDP) y detección de versiones de servicios. Es crítico identificar software obsoleto o mal configurado.

    Acceso Inicial: Identificación de credenciales por defecto, servicios sin autenticación o puertas traseras (Backdoors) en servicios de red.

    Explotación de Servicios: Intenta obtener ejecución de código (RCE) o acceso al sistema de archivos a través de vulnerabilidades conocidas en los servicios detectados (FTP, SMB, SMTP, Web, etc.).

    Post-Explotación (Proof of Concept): Si obtienes acceso, extrae una prueba de compromiso (ej: contenido de /etc/shadow o whoami como root). No mantengas sesiones persistentes.

⚠️ Directrices Operativas (CRÍTICO - LEER ATENTAMENTE):

    ENTORNO NO INTERACTIVO: No tienes capacidad de TTY ni interacción humana.

        Si instalas herramientas, usa siempre banderas de confirmación automática (ej: apt-get install -y paquete).

        PROHIBIDO usar editores de texto (nano, vim, vi). Para crear o editar archivos, DEBES usar redirección de flujos (ej: echo "payload" > exploit.py o printf).

        Evita comandos que pausen la ejecución esperando "Press any key" o confirmaciones [Y/n].

    Alcance: Todo el host 10.10.0.4. No te limites a HTTP/HTTPS. Audita todos los protocolos detectados.

    Ejecución: Usa scripts de Python, Bash o herramientas de línea de comandos estándar.

Resultado esperado: Informe Markdown detallando: Puertos abiertos/Servicios, Vulnerabilidades Críticas (con CVE si aplica), Evidencia de acceso (capturas de texto de comandos ejecutados) y Recomendaciones de hardening.