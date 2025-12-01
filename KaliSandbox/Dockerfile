# -------------------------------------------------------------------
# FASE 1: BASE Y HERRAMIENTAS CLÁSICAS
# -------------------------------------------------------------------
FROM kalilinux/kali-rolling

# Actualizamos repositorios
RUN apt-get update

# Instalación de herramientas básicas de auditoría y sistema
RUN apt-get install -y \
    nmap sqlmap nikto hydra ffuf whatweb curl jq \
    iputils-ping netcat-traditional dnsutils samba-client \
    python3 python3-pip python3-flask wordlists \
    # Limpieza de caché para reducir peso
    && rm -rf /var/lib/apt/lists/*

# Instalación de Nuclei (Escáner de vulnerabilidades moderno)
RUN curl -L -o nuclei.zip https://github.com/projectdiscovery/nuclei/releases/download/v3.1.0/nuclei_3.1.0_linux_amd64.zip \
    && apt-get install -y unzip \
    && unzip -o nuclei.zip \
    && mv nuclei /usr/local/bin/ \
    && rm nuclei.zip

# Instalación de TLDR (Chuletas para que el LLM sepa usar comandos)
RUN pip3 install tldr --break-system-packages && \
    tldr --update_cache

# Descomprimir el diccionario Rockyou (Estándar para fuerza bruta)
RUN gzip -d /usr/share/wordlists/rockyou.txt.gz || true

# -------------------------------------------------------------------
# FASE 2: HERRAMIENTAS PARA WEB MODERNA (JUICE SHOP / APIS)
# -------------------------------------------------------------------

# 1. Instalamos Httpie, Git y SETUPTOOLS (Vital para instalar LinkFinder)
# IMPORTANTE: Ejecutamos 'apt-get update' de nuevo porque borramos la caché en la Fase 1.
RUN apt-get update && apt-get install -y \
    httpie \
    git \
    python3-setuptools \
    && rm -rf /var/lib/apt/lists/*

# 2. Descargar LinkFinder (Para que el LLM encuentre endpoints en archivos JS)
RUN git clone https://github.com/GerbenJavado/LinkFinder.git /opt/linkfinder \
    && cd /opt/linkfinder \
    && pip3 install -r requirements.txt --break-system-packages \
    && python3 setup.py install

# 3. Descargar Wordlists específicas de API (SecLists Mini)
RUN mkdir -p /usr/share/wordlists/seclists/Discovery/Web-Content/ \
    && curl -L -o /usr/share/wordlists/seclists/Discovery/Web-Content/api-endpoints.txt \
    https://raw.githubusercontent.com/danielmiessler/SecLists/master/Discovery/Web-Content/api-endpoints.txt

# -------------------------------------------------------------------
# FASE 3: EMPAQUETADO DE TU CÓDIGO (AISLAMIENTO)
# -------------------------------------------------------------------

# 1. Definimos la carpeta protegida donde vivirá TU CÓDIGO (API)
WORKDIR /app

# 2. Copiamos el contenido de tu carpeta 'script' local a '/app' dentro del Docker
COPY script/ /app/

# 3. Creamos la carpeta donde trabajará EL AGENTE (Sandbox para ejecutar comandos)
RUN mkdir -p /workspace

# 4. Creamos un archivo de bienvenida
RUN echo "Bienvenido al Agente de Ciberseguridad TFG" > /workspace/README.txt

# -------------------------------------------------------------------
# FASE 4: ARRANQUE
# -------------------------------------------------------------------

# El agente siempre empezará "sentado" en el workspace, no en la carpeta del código
WORKDIR /workspace

# Exponemos el puerto de la API
EXPOSE 5000

# Arrancamos la API Flask (usando ruta absoluta)
CMD ["python3", "/app/agent_api.py"]