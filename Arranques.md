# Guía de Arranque - Laboratorio TFG

Este documento contiene todas las instrucciones necesarias para instalar, configurar y arrancar el entorno Docker del proyecto.

---

## Índice
- [Requisitos previos](#requisitos-previos)
- [Instalación inicial](#instalación-inicial)
- [Arranque estándar](#arranque-estándar)
- [Comandos típicos por escenario](#comandos-típicos-por-escenario)
- [Troubleshooting](#troubleshooting)

---

## Requisitos previos

Antes de comenzar, asegúrate de tener instalado:

- **Docker**: versión 20.10 o superior
- **Docker Compose**: versión 1.29 o superior
- **Git**: para clonar el repositorio

### Verificar instalación

```bash
docker --version
docker compose version
```

Si no tienes Docker instalado, visita la [documentación oficial de Docker](https://docs.docker.com/get-docker/).

---

## Instalación inicial

### 1. Clonar el repositorio

```bash
git clone https://github.com/Alexeido/TFG.git
cd TFG/KaliSandbox
```

### 2. Construir las imágenes Docker

Este paso solo es necesario la **primera vez** o cuando hagas cambios en el `Dockerfile`:

```bash
docker compose build
```

**Nota**: La construcción puede tardar entre 5-15 minutos dependiendo de tu conexión a internet, ya que descarga:
- Imagen base de Kali Linux
- Herramientas de pentesting (nmap, sqlmap, nikto, hydra, ffuf, nuclei, etc.)
- Imágenes de las víctimas (DVWA, Metasploitable2, OWASP Juice Shop)

### 3. Verificar que las imágenes se crearon correctamente

```bash
docker images | grep -E "agente-tfg|vulnerables|metasploitable|juice-shop"
```

Deberías ver al menos 4 imágenes listadas.

---

## Arranque estándar

Una vez construidas las imágenes, puedes arrancar el laboratorio completo:

### Levantar todos los servicios

```bash
docker compose up -d
```

El flag `-d` (detached) ejecuta los contenedores en segundo plano.

### Verificar que los contenedores están corriendo

```bash
docker compose ps
```

Deberías ver 4 contenedores activos:
- `agente-tfg` (Atacante) - IP: 10.5.0.2
- `victima-dvwa` (DVWA) - IP: 10.5.0.3
- `victima-meta` (Metasploitable2) - IP: 10.5.0.4
- `victima-juice` (OWASP Juice Shop) - IP: 10.5.0.5

### Verificar conectividad de red

Desde el contenedor del agente, prueba hacer ping a las víctimas:

```bash
docker exec agente-tfg ping -c 2 10.5.0.3
docker exec agente-tfg ping -c 2 10.5.0.4
docker exec agente-tfg ping -c 2 10.5.0.5
```

### Acceso a servicios web

- **DVWA**: http://localhost:8080 (Credenciales: `admin` / `password`)
- **Juice Shop**: http://localhost:3000
- **API del Agente**: http://localhost:5000

---

## Comandos típicos por escenario

### Desarrollo activo (con logs en vivo)

Si estás desarrollando y quieres ver los logs en tiempo real:

```bash
docker compose up
```

Para detenerlo, presiona `Ctrl+C`.

### Ver logs de un servicio específico

```bash
# Ver logs del agente
docker compose logs -f attacker

# Ver logs de DVWA
docker compose logs -f victim

# Ver logs de Metasploitable2
docker compose logs -f meta_victim

# Ver logs de Juice Shop
docker compose logs -f juice_victim
```

El flag `-f` (follow) mantiene el stream de logs abierto.

### Acceder a la terminal del agente

Para ejecutar comandos manualmente dentro del contenedor del agente:

```bash
docker exec -it agente-tfg /bin/bash
```

Una vez dentro, puedes ejecutar herramientas como:

```bash
nmap 10.5.0.3
sqlmap -u "http://10.5.0.3/vulnerabilities/sqli/"
ffuf -u http://10.5.0.5/FUZZ -w /usr/share/wordlists/rockyou.txt
```

Para salir de la terminal: `exit`

### Reiniciar un servicio específico

```bash
# Reiniciar solo el agente
docker compose restart attacker

# Reiniciar solo DVWA
docker compose restart victim
```

### Detener todos los servicios

```bash
docker compose down
```

**Nota**: Esto **NO** borra las imágenes ni los volúmenes, solo detiene los contenedores.

### Detener y eliminar todo (incluyendo volúmenes)

```bash
docker compose down -v
```

⚠️ **Cuidado**: Esto eliminará datos persistentes (bases de datos, configuraciones, etc.).

### Reconstruir el agente tras cambios en el código

Si modificas `agent_api.py` o el `Dockerfile`:

```bash
docker compose down
docker compose build attacker
docker compose up -d
```

O en una sola línea:

```bash
docker compose up -d --build attacker
```

### Limpiar contenedores, imágenes y caché

Si necesitas liberar espacio o empezar de cero:

```bash
# Eliminar contenedores detenidos
docker container prune -f

# Eliminar imágenes no utilizadas
docker image prune -a -f

# Eliminar TODO (contenedores, imágenes, redes, volúmenes)
docker system prune -a --volumes -f
```

⚠️ **Advertencia**: El último comando eliminará **todas** las imágenes y volúmenes Docker de tu sistema, no solo los del proyecto.

---

## Troubleshooting

### Problema: "Port already in use"

**Error**: `Bind for 0.0.0.0:5000 failed: port is already allocated`

**Solución**: Otro servicio está usando el puerto. Ciérralo o cambia el puerto en `docker-compose.yml`:

```yaml
ports:
  - "5001:5000"  # Usa 5001 en el host
```

### Problema: "Cannot connect to Docker daemon"

**Solución**: Asegúrate de que Docker esté corriendo:

```bash
sudo systemctl start docker
```

### Problema: Contenedor `meta_victim` se detiene inmediatamente

**Solución**: Verifica que `tty: true` y `stdin_open: true` estén presentes en el servicio `meta_victim` del `docker-compose.yml`.

### Problema: No hay conectividad entre contenedores

**Solución**: Verifica que la red esté creada correctamente:

```bash
docker network inspect kalisandbox_hacking_net
```

Si no existe, recrea los contenedores:

```bash
docker compose down
docker compose up -d
```

### Problema: Cambios en `agent_api.py` no se reflejan

**Solución**: Si usas volúmenes (`volumes: ./script:/app`), los cambios deberían reflejarse automáticamente. Si no, reinicia el servicio:

```bash
docker compose restart attacker
```

---

## Resumen de comandos más usados

| Acción | Comando |
|--------|---------|
| Primera instalación | `docker compose build` |
| Arrancar todo | `docker compose up -d` |
| Ver estado | `docker compose ps` |
| Ver logs (agente) | `docker compose logs -f attacker` |
| Entrar al agente | `docker exec -it agente-tfg /bin/bash` |
| Reiniciar agente | `docker compose restart attacker` |
| Detener todo | `docker compose down` |
| Reconstruir agente | `docker compose up -d --build attacker` |
| Limpiar todo | `docker compose down -v && docker system prune -a -f` |

---

## Notas finales

- **Modo desarrollo**: El volumen `./script:/app` permite editar código en tu máquina y verlo reflejado dentro del contenedor sin reconstruir.
- **Red aislada**: Todos los contenedores están en la red `10.5.0.0/24`, invisible desde tu red local.
- **Persistencia**: Los datos de las víctimas (bases de datos, configuraciones) se mantienen mientras no uses `docker compose down -v`.

Para más información, consulta la [documentación oficial de Docker Compose](https://docs.docker.com/compose/).
