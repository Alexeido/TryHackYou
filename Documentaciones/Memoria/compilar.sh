#!/bin/bash

# Nos aseguramos de estar en la carpeta donde está el script
cd "$(dirname "$0")"

# --- OPCIONAL: Activar el entorno virtual de Python ---
# Esto ayuda si usas paquetes de LaTeX que llaman a Python
if [ -f "./.venv/bin/activate" ]; then
    source ./.venv/bin/activate
    echo "Entorno virtual activado..."
fi

echo "Iniciando compilación de LaTeX..."

# Primera pasada de pdflatex
pdflatex -shell-escape -interaction=nonstopmode main.tex

# Procesar la bibliografía
bibtex main

# Segundas pasadas para referencias y citas
pdflatex -shell-escape -interaction=nonstopmode main.tex
pdflatex -shell-escape -interaction=nonstopmode main.tex

echo ""
echo "Compilación terminada. Revisa main.pdf"

# Simular el "pause" de Windows
read -p "Presiona Enter para cerrar..."