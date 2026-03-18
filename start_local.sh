#!/bin/bash
# SeniorAdvisor - Script de arranque local
# Uso: bash start_local.sh

echo "=============================="
echo "  SeniorAdvisor - Backend"
echo "=============================="

# Verificar .env
if [ ! -f ".env" ]; then
    echo "ERROR: Falta el archivo .env"
    echo "Copia el .env con las credenciales de MongoDB, Google, etc."
    exit 1
fi

# Crear carpetas de uploads si no existen
mkdir -p uploads/gallery uploads/premium_gallery uploads/profile uploads/profiles uploads/personal

# Instalar dependencias si es necesario
if [ ! -d "venv" ]; then
    echo "Creando entorno virtual..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install -r requirements_local.txt

echo ""
echo "Iniciando backend en http://localhost:8001"
echo "CTRL+C para detener"
echo ""

python -m uvicorn server:app --host 0.0.0.0 --port 8001 --reload
