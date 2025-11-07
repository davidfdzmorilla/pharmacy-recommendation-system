#!/bin/bash
set -e

echo "=== Iniciando Sistema Farmacéutico (Modo Desarrollo) ==="
echo ""

# Verificar XQuartz
if ! pgrep -x "XQuartz" > /dev/null; then
    echo "Iniciando XQuartz..."
    open -a XQuartz
    echo "Esperando a que XQuartz inicie..."
    sleep 5
fi

# Configurar DISPLAY
export DISPLAY=host.docker.internal:0
echo "✅ DISPLAY configurado: $DISPLAY"

# Configurar permisos X11
xhost + 127.0.0.1 > /dev/null 2>&1 || true
echo "✅ Permisos X11 configurados"
echo ""

# Verificar si existe estructura básica
if [ ! -d "raspberry_app" ]; then
    echo "⚠️  Estructura de proyecto no existe aún"
    echo "Se creará en el primer sprint de desarrollo"
    echo ""
fi

echo "=== Iniciando contenedor Docker ==="
echo "Presiona Ctrl+C para detener"
echo ""

# Ejecutar app
cd docker
docker-compose -f docker-compose.dev.yml up

# Cleanup al salir
trap 'docker-compose -f docker-compose.dev.yml down' EXIT
