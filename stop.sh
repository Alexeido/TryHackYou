#!/bin/bash

# --- CONFIGURACIÓN ---
BASE_DIR=$(pwd)
BACKEND_PORT=4000
FRONTEND_PORT=3000

echo "🛑 Iniciando parada del sistema TFG..."

# 1. PARAR DOCKER
echo "🐳 Deteniendo infraestructura Docker..."
if docker info > /dev/null 2>&1; then
    cd "$BASE_DIR/KaliSandbox" || exit
    docker compose down
    echo "✅ Contenedores detenidos y eliminados."
else
    echo "⚠️  Docker no parece estar corriendo, saltando este paso."
fi

# 2. CERRAR BACKEND (Puerto 4000)
echo "🐍 Cerrando Backend (Puerto $BACKEND_PORT)..."
BACKEND_PID=$(lsof -t -i:$BACKEND_PORT)
if [ -z "$BACKEND_PID" ]; then
    echo "ℹ️  No se encontró ningún proceso en el puerto $BACKEND_PORT."
else
    kill -9 $BACKEND_PID
    echo "✅ Proceso Backend finalizado."
fi

# 3. CERRAR FRONTEND (Puerto 3000)
echo "⚛️  Cerrando Frontend (Puerto $FRONTEND_PORT)..."
FRONTEND_PID=$(lsof -t -i:$FRONTEND_PORT)
if [ -z "$FRONTEND_PID" ]; then
    # Intento secundario por nombre de proceso si el puerto varía
    pkill -f "next-dev"
    echo "✅ Proceso Frontend finalizado."
else
    kill -9 $FRONTEND_PID
    echo "✅ Proceso Frontend finalizado."
fi

# 4. LIMPIEZA EXTRA DE TERMINALES
# Esto intentará cerrar las terminales que abrimos con gnome-terminal
echo "🪟  Limpiando terminales..."
pkill -f "gnome-terminal --title=Backend: FastAPI"
pkill -f "gnome-terminal --title=Frontend: Next.js"

echo "✨ ¡Todo limpio! Sistema detenido correctamente."