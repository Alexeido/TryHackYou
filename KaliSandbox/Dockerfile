# -------------------------------------------------------------------
# FASE 1: BASE Y HERRAMIENTAS (Igual que antes)
# -------------------------------------------------------------------
FROM kalilinux/kali-rolling

# Actualizamos repositorios
RUN apt-get update

# Instalación de herramientas
RUN apt-get install -y \
    nmap sqlmap nikto hydra ffuf whatweb curl jq \
    iputils-ping netcat-traditional dnsutils samba-client \
    python3 python3-pip python3-flask wordlists \
    # Limpieza
    && rm -rf /var/lib/apt/lists/*

# Instalación de Nuclei (Versión corregida)
RUN curl -L -o nuclei.zip https://github.com/projectdiscovery/nuclei/releases/download/v3.1.0/nuclei_3.1.0_linux_amd64.zip \
    && apt-get install -y unzip \
    && unzip -o nuclei.zip \
    && mv nuclei /usr/local/bin/ \
    && rm nuclei.zip

# Instalación de TLDR (Chuletas para el LLM)
RUN pip3 install tldr --break-system-packages && \
    tldr --update_cache

# Descomprimir rockyou
RUN gzip -d /usr/share/wordlists/rockyou.txt.gz || true

# -------------------------------------------------------------------
# FASE 2: EMPAQUETADO DE TU CÓDIGO (Aislamiento)
# -------------------------------------------------------------------

# 1. Creamos la carpeta donde vivirá TU CÓDIGO (Intocable para el agente)
WORKDIR /app

# 2. Copiamos el contenido de tu carpeta 'script' local a '/app'
# IMPORTANTE: Como el Dockerfile está fuera de 'script', la ruta es así:
COPY script/ /app/

# 3. Creamos la carpeta donde trabajará EL AGENTE (Sandbox dentro del Sandbox)
RUN mkdir -p /workspace

# 4. (Opcional) Puedes crear algún archivo dummy para que no esté vacía del todo
RUN touch /workspace/README.txt

# -------------------------------------------------------------------
# FASE 3: ARRANQUE
# -------------------------------------------------------------------

# Definimos que, por defecto, cualquier comando manual empiece en el workspace
WORKDIR /workspace

# Exponemos el puerto
EXPOSE 5000

# Arrancamos la API (usando ruta absoluta porque ahora estamos en /workspace)
CMD ["python3", "/app/agent_api.py"]
