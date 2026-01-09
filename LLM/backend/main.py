"""
main.py - Punto de entrada del servidor FastAPI.

Este archivo solo se encarga de:
1. Configurar la aplicación FastAPI
2. Registrar los routers
3. Inicializar la base de datos al arrancar

La lógica está separada en módulos:
- database.py: Gestión de SQLite
- models.py: Modelos Pydantic
- routes/: Endpoints organizados por funcionalidad
"""

import asyncio
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Importar inicialización de BD y actualización de scores
from database import init_db
from scoring import update_scores_from_internet

# Importar job monitor para background jobs
from job_monitor import start_job_monitor, stop_job_monitor

# Importar routers
from routes.health import router as health_router
from routes.conversations import router as conversations_router
from routes.chat import router as chat_router
from routes.messages import router as messages_router
from routes.jobs import router as jobs_router

# Importar la lógica de discovery que ya existe
from routes_legacy import router as legacy_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan: código que se ejecuta al arrancar y cerrar el servidor.
    """
    # === ARRANQUE ===
    print("🚀 Iniciando servidor...")
    
    # Inicializar base de datos
    init_db()
    
    # Actualizar scores en background
    t = threading.Thread(target=update_scores_from_internet)
    t.start()
    
    # Iniciar monitor de jobs en background
    start_job_monitor(interval=5.0)
    
    print("✅ Servidor listo!")
    
    yield  # El servidor está corriendo
    
    # === CIERRE ===
    print("👋 Cerrando servidor...")
    stop_job_monitor()


# =============================================================================
# CREAR APP
# =============================================================================

app = FastAPI(
    title="Cerebro LLM",
    description="Backend para el agente de ciberseguridad con soporte multi-proveedor",
    version="6.0.0",
    lifespan=lifespan
)

# =============================================================================
# CORS (para que el frontend pueda conectar)
# =============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, limitar a dominios específicos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# REGISTRAR ROUTERS
# =============================================================================

# Nuevos endpoints modulares
app.include_router(health_router)
app.include_router(conversations_router)
app.include_router(chat_router)
app.include_router(messages_router)
app.include_router(jobs_router)

# Endpoints legacy (discovery de modelos)
app.include_router(legacy_router)


# =============================================================================
# ROOT ENDPOINT
# =============================================================================

@app.get("/")
async def root():
    """Endpoint raíz - información básica."""
    return {
        "name": "Cerebro LLM",
        "version": "6.0.0",
        "docs": "/docs",
        "health": "/health"
    }
