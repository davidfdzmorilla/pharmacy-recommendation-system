#!/bin/bash

echo "=== Shell Interactivo - Contenedor Desarrollo ==="
echo ""

cd docker
docker-compose -f docker-compose.dev.yml run --rm pharmacy-app-dev /bin/bash
