#!/bin/bash

echo "=== Ejecutando Tests ==="
echo ""

cd docker
docker-compose -f docker-compose.dev.yml run --rm pharmacy-app-dev pytest tests/ -v
