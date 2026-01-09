#!/bin/bash

# --- CONFIGURACIÓN DE RUTAS ---
VENV_PATH="/home/alexbook/Documentos/Github/TFG/.venv/bin/activate"
BASE_DIR=$(pwd)

# 1. VERIFICAR SI DOCKER ESTÁ ARRANCADO
echo "🔍 Verificando estado de Docker..."
if ! docker info > /dev/null 2>&1; then
    echo "❌ ERROR: Docker no está arrancado."
    echo "⚠️  Por favor, abre Docker Desktop y vuelve a ejecutar este script."
    exit 1
fi

echo "✅ Docker está listo. Iniciando servicios..."

# 2. TERMINAL 1: KALI SANDBOX (Se abre, arranca y SE CIERRA solo)
# Al no poner "exec bash" al final, la ventana se cierra en cuanto termina el comando.
gnome-terminal --title="🐳 Docker Setup" -- bash -c "
    cd '$BASE_DIR/KaliLab' || exit;
    echo '🚀 Levantando infraestructura Docker en segundo plano...';
    docker compose up -d;
    echo '✅ Hecho. Cerrando esta ventana...';
    sleep 1;"

# Pequeña pausa para que Docker asigne IPs antes de que el Backend intente conectar
sleep 2

# 3. TERMINAL 2: BACKEND (Se mantiene abierto para logs)
gnome-terminal --title="🐍 Backend: FastAPI" -- bash -c "
    source '$VENV_PATH';
    cd '$BASE_DIR/LLM/backend' || exit;
    echo '🚀 Iniciando Uvicorn en puerto 4000...';
    uvicorn main:app --host 0.0.0.0 --port 4000 --reload;
    exec bash"

# 4. TERMINAL 3: FRONTEND (Se mantiene abierto para logs)
gnome-terminal --title="⚛️ Frontend: Next.js" -- bash -c "
    cd '$BASE_DIR/LLM/frontend' || exit;
    echo '🚀 Iniciando entorno de desarrollo Frontend...';
    npm run dev;
    exec bash"

echo "✨ Proceso completado."
echo "🐳 Docker levantado (ventana cerrada)."
echo "🖥️  Backend y Frontend corriendo en sus terminales."