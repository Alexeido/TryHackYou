# -------------------------------------------------------------------
# FASE 1: BASE Y HERRAMIENTAS CLÁSICAS + NETWORKING
# -------------------------------------------------------------------
FROM kalilinux/kali-rolling

# Actualizamos repositorios e instalamos herramientas core
RUN apt-get update && apt-get install -y \
    nmap sqlmap nikto hydra ffuf whatweb curl jq exploitdb wget \
    iputils-ping netcat-traditional dnsutils samba-client \
    python3 python3-pip python3-flask python3-setuptools wordlists \
    git unzip lynx chromium 

# Actualizamos la base de datos de exploits (Searchsploit)

# -------------------------------------------------------------------
# FASE 2: RECONOCIMIENTO Y WEB MODERNA (ProjectDiscovery + Arjun)
# -------------------------------------------------------------------

# 1. Nuclei (Vulnerabilidades)
RUN curl -L -o nuclei.zip https://github.com/projectdiscovery/nuclei/releases/download/v3.1.0/nuclei_3.1.0_linux_amd64.zip \
    && unzip -o nuclei.zip && mv nuclei /usr/local/bin/ && rm nuclei.zip

# 2. Katana (Spidering con soporte Headless/JS)
RUN curl -L -o katana.zip https://github.com/projectdiscovery/katana/releases/download/v1.1.0/katana_1.1.0_linux_amd64.zip \
    && unzip -o katana.zip && mv katana /usr/local/bin/ && rm katana.zip

# 3. Subfinder (Descubrimiento de subdominios)
RUN curl -L -o subfinder.zip https://github.com/projectdiscovery/subfinder/releases/download/v2.6.3/subfinder_2.6.3_linux_amd64.zip \
    && unzip -o subfinder.zip && mv subfinder /usr/local/bin/ && rm subfinder.zip

# 4. Arjun (Descubrimiento de parámetros ocultos)
RUN pip3 install arjun --break-system-packages

# -------------------------------------------------------------------
# FASE 3: EXTRACCIÓN Y ANÁLISIS DE JS
# -------------------------------------------------------------------

# pup (HTML parsing), tldr (ayuda para comandos)
RUN curl -L -o pup.zip https://github.com/ericchiang/pup/releases/download/v0.4.0/pup_v0.4.0_linux_amd64.zip \
    && unzip -o pup.zip && mv pup /usr/local/bin/ && rm pup.zip
RUN pip3 install tldr --break-system-packages && tldr --update_cache

# LinkFinder y SecretFinder
RUN git clone https://github.com/GerbenJavado/LinkFinder.git /opt/linkfinder \
    && cd /opt/linkfinder && pip3 install -r requirements.txt --break-system-packages \
    && python3 setup.py install

RUN git clone https://github.com/m4ll0k/SecretFinder.git /opt/secretfinder \
    && cd /opt/secretfinder && pip3 install -r requirements.txt --break-system-packages

# Instalación de OWASP ZAP (Versión Cross-Platform) y zap-cli
# Usamos --ignore-installed para evitar conflictos con paquetes del sistema (click)
RUN apt-get install -y zaproxy \
    && pip3 install zapcli --ignore-installed --break-system-packages \
    && pip3 install --upgrade urllib3 requests --break-system-packages 

# -------------------------------------------------------------------
# FASE 4: AISLAMIENTO, PERSISTENCIA Y API
# -------------------------------------------------------------------

# Instalación de librerías Python necesarias
RUN pip3 install flask-cors gitpython --break-system-packages

WORKDIR /app
COPY script/ /app/

# Configuración de carpetas y permisos
RUN mkdir -p /workspace /workspace_persistent /workspace_sessions && \
    chmod -R 777 /workspace_persistent /workspace_sessions

# Descomprimir Rockyou
RUN gzip -d /usr/share/wordlists/rockyou.txt.gz || true

# -------------------------------------------------------------------
# FASE 5: ARRANQUE
# -------------------------------------------------------------------
WORKDIR /workspace
EXPOSE 5000
CMD ["python3", "/app/agent_api.py"]