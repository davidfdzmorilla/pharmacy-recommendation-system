#!/bin/bash
set -e

echo "=== Setup Sistema Farmacéutico (Docker + Mac) ==="
echo ""

# Verificar Docker
echo "Verificando Docker..."
if ! command -v docker &> /dev/null; then
    echo "❌ Docker no instalado"
    echo "Instala desde: https://www.docker.com/products/docker-desktop"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "❌ Docker no está corriendo"
    echo "Por favor inicia Docker Desktop"
    exit 1
fi

echo "✅ Docker OK"
echo ""

# Verificar XQuartz
echo "Verificando XQuartz..."
if [ ! -d "/Applications/Utilities/XQuartz.app" ]; then
    echo "⚠️  XQuartz no instalado"
    echo "Descarga desde: https://www.xquartz.org/"
    echo "Después de instalar:"
    echo "1. Abre XQuartz"
    echo "2. Ve a Preferencias > Seguridad"
    echo "3. Marca 'Permitir conexiones desde clientes de red'"
    echo "4. Reinicia XQuartz y cierra/abre sesión en Mac"
    exit 1
fi

echo "✅ XQuartz instalado"
echo ""

# Crear .env
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "✅ Archivo .env creado desde .env.example"
        echo "⚠️  Edita .env y añade ANTHROPIC_API_KEY"
    else
        cat > .env <<EOF
# API Configuration
ANTHROPIC_API_KEY=your_api_key_here

# Application Mode
SIMULATION_MODE=true

# Cache Configuration
CACHE_ENABLED=true
CACHE_TTL=3600
CACHE_MAX_SIZE=100

# Logging
LOG_LEVEL=INFO
EOF
        echo "✅ Archivo .env creado"
        echo "⚠️  Edita .env y añade ANTHROPIC_API_KEY"
    fi
else
    echo "✅ Archivo .env existe"
fi
echo ""

# Crear directorios
echo "Creando directorios..."
mkdir -p data logs config
echo "✅ Directorios creados"
echo ""

# Configurar XQuartz
echo "Configurando permisos X11..."
xhost + 127.0.0.1 > /dev/null 2>&1 || true
echo "✅ Permisos X11 configurados"
echo ""

# Build
echo "Construyendo imagen Docker..."
cd docker
docker-compose -f docker-compose.dev.yml build
echo "✅ Imagen construida"
echo ""

echo "======================================"
echo "✅ Setup completado!"
echo ""
echo "Próximos pasos:"
echo "1. Edita .env con tu ANTHROPIC_API_KEY"
echo "2. Asegúrate de que XQuartz esté corriendo"
echo "3. Ejecuta: ./scripts/run_docker_dev.sh"
echo "======================================"
