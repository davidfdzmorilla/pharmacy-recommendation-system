# 🏥 Sistema de Recomendación de Productos para Farmacia

Sistema de punto de venta inteligente para farmacias con recomendaciones contextuales en tiempo real impulsadas por Claude AI.

## 📋 Descripción

Sistema diseñado para ejecutarse en **Raspberry Pi 4** con lector de código de barras USB, que proporciona recomendaciones terapéuticas inteligentes basadas en los productos escaneados. El desarrollo se realiza localmente en Mac usando Docker + XQuartz para facilitar el testing y desarrollo.

### ✨ Características Principales

- 🔍 **Escaneo de códigos de barras EAN-13** mediante lector USB o simulador
- 🤖 **Recomendaciones contextuales** con Claude Sonnet 4 basadas en el carrito completo
- 💾 **Base de datos SQLite local** con 100+ productos farmacéuticos
- ⚡ **Sistema de caché inteligente** (LRU + TTL) para optimizar llamadas a la API
- 🎨 **Interfaz gráfica tkinter** responsiva y sin bloqueos
- 📊 **Historial de ventas** con análisis de productos
- 🔄 **Modo simulación** para desarrollo y testing sin hardware físico
- 🏥 **Recomendaciones farmacéuticas** basadas en interacciones terapéuticas

### 🎯 Ejemplo de Uso

```
Usuario escanea: Ibuprofeno 600mg
Sistema recomienda automáticamente:
  → Omeprazol (protector gástrico)
  → Probióticos (si hay antibióticos en el carrito)
  → Crema antiinflamatoria tópica complementaria
```

## 🛠️ Stack Tecnológico

| Componente | Tecnología |
|------------|------------|
| **Lenguaje** | Python 3.11 |
| **IA** | Anthropic Claude API (Sonnet 4) |
| **Base de Datos** | SQLite 3 |
| **GUI** | tkinter |
| **Hardware** | Lector de barras USB (evdev) |
| **Containerización** | Docker + Docker Compose |
| **Display (Mac)** | XQuartz (X11) |
| **Testing** | pytest + pytest-cov |

## 📦 Requisitos Previos

### Para Desarrollo en Mac

- **macOS** (testeado en macOS Ventura+)
- **Docker Desktop** 4.0+ ([Descargar](https://www.docker.com/products/docker-desktop))
- **XQuartz** 2.8+ ([Descargar](https://www.xquartz.org/))
- **Cuenta Anthropic** con API Key ([Obtener aquí](https://console.anthropic.com/))

### Para Producción en Raspberry Pi

- **Raspberry Pi 4** (4GB RAM recomendado)
- **Raspberry Pi OS** (Bookworm o superior)
- **Lector de código de barras USB** compatible con HID
- Python 3.11+

## 🚀 Instalación y Configuración

### Opción 1: Desarrollo en Mac (Recomendado)

#### 1️⃣ Instalar Dependencias

```bash
# Instalar Docker Desktop
# Descargar desde: https://www.docker.com/products/docker-desktop

# Instalar XQuartz
# Descargar desde: https://www.xquartz.org/
```

#### 2️⃣ Configurar XQuartz

```bash
# Abrir XQuartz
open -a XQuartz

# En XQuartz > Preferencias > Seguridad:
# ✅ Activar "Permitir conexiones desde clientes de red"

# IMPORTANTE: Cerrar sesión y volver a iniciar sesión en macOS
```

#### 3️⃣ Clonar y Configurar el Proyecto

```bash
# Clonar repositorio
git clone <url-del-repositorio>
cd pharmacy-recommendation-system

# Dar permisos a los scripts
chmod +x scripts/*.sh

# Ejecutar setup automático
./scripts/setup_docker.sh
```

#### 4️⃣ Configurar API Key

```bash
# Copiar archivo de ejemplo
cp config/.env.example .env

# Editar y añadir tu API key
nano .env
```

Añade tu clave de Anthropic:
```bash
ANTHROPIC_API_KEY=tu_clave_api_aqui
SIMULATION_MODE=true
```

#### 5️⃣ Iniciar la Aplicación

```bash
# Esto iniciará XQuartz automáticamente si es necesario
./scripts/run_docker_dev.sh
```

### Opción 2: Instalación en Raspberry Pi

```bash
# Copiar proyecto a Raspberry Pi
scp -r pharmacy-recommendation-system pi@raspberrypi.local:~

# Conectar por SSH
ssh pi@raspberrypi.local
cd pharmacy-recommendation-system

# Ejecutar instalación nativa
chmod +x scripts/*.sh
./scripts/setup_raspberry.sh

# Configurar variables de entorno
cp config/.env.example .env
nano .env  # Añadir ANTHROPIC_API_KEY y SIMULATION_MODE=false

# Iniciar aplicación
source venv/bin/activate
python raspberry_app/main.py
```

## 💻 Uso

### Desarrollo Diario

```bash
# Iniciar aplicación
./scripts/run_docker_dev.sh

# La aplicación se abrirá con:
# - Panel izquierdo: Carrito de compra
# - Panel derecho: Recomendaciones inteligentes
# - Botón "Abrir Simulador": Para escanear códigos de barras

# Detener: Ctrl+C
```

### Simulador de Códigos de Barras

En modo desarrollo (`SIMULATION_MODE=true`), usa el simulador integrado:

1. Click en **"Abrir Simulador"**
2. Introduce un código EAN-13 (13 dígitos)
3. Presiona Enter o click en **"Escanear"**
4. El producto se añadirá al carrito
5. Tras 1.5 segundos sin escanear, aparecerán recomendaciones

**Códigos de ejemplo incluidos:**
- `8470001234567` - Ibuprofeno 600mg
- `8470001234568` - Paracetamol 1g
- `8470001234569` - Omeprazol 20mg
- (Ver `data/sample_products.json` para más)

### Gestión de Base de Datos

```bash
# Inicializar base de datos
cd docker
docker-compose -f docker-compose.dev.yml run --rm pharmacy-app-dev \
  python scripts/init_database.py

# Importar productos de ejemplo (100 productos)
docker-compose -f docker-compose.dev.yml run --rm pharmacy-app-dev \
  python scripts/import_products.py

# Inspeccionar base de datos
./scripts/shell.sh
sqlite3 data/pharmacy.db
```

## 🧪 Testing

```bash
# Ejecutar todos los tests
./scripts/run_tests.sh

# Tests específicos
cd docker
docker-compose -f docker-compose.dev.yml run --rm pharmacy-app-dev \
  pytest tests/test_api_client.py -v

# Con cobertura
docker-compose -f docker-compose.dev.yml run --rm pharmacy-app-dev \
  pytest --cov=raspberry_app tests/
```

## 📊 Arquitectura del Sistema

```
┌─────────────────────────────────────────────┐
│           APLICACIÓN PYTHON                 │
│                                             │
│  Barcode Reader ──→ Shopping Cart Manager  │
│       ↓                     ↓               │
│  Simulator          Recommendation Engine   │
│                             ↓               │
│                  ┌──────────┴──────────┐   │
│                  ↓          ↓          ↓   │
│              Cache      Claude API  SQLite  │
│           (LRU+TTL)                         │
└─────────────────────────────────────────────┘
                     ↓
          ┌──────────────────┐
          │ Anthropic Claude │
          │   API (Cloud)    │
          └──────────────────┘
```

### Flujo de Datos

1. Usuario escanea producto → Validación en base de datos
2. Producto añadido al carrito → Actualización de UI
3. Debounce de 1.5s → Evita llamadas excesivas a API
4. Generación de hash del carrito → Búsqueda en caché
5. Si hay caché → Mostrar recomendaciones (< 50ms)
6. Si no hay caché → Llamada a Claude API (< 2s)
7. Parsing y almacenamiento → Actualización de UI sin bloqueos

## 🎨 Estructura del Proyecto

```
pharmacy-recommendation-system/
├── raspberry_app/          # Código fuente principal
│   ├── api/               # Cliente Claude + caché
│   ├── barcode/           # Lector + simulador
│   ├── database/          # SQLite + modelos
│   ├── ui/                # Interfaz tkinter
│   ├── utils/             # Utilidades
│   ├── config.py          # Configuración
│   └── main.py            # Punto de entrada
├── docker/                # Dockerfiles y compose
├── scripts/               # Scripts de automatización
├── tests/                 # Tests unitarios e integración
├── data/                  # Base de datos + productos
├── config/                # Configuración (.env)
└── docs/                  # Documentación adicional
```

## ⚙️ Configuración Avanzada

### Variables de Entorno

Edita `.env` para personalizar:

```bash
# API Configuration
ANTHROPIC_API_KEY=tu_clave_aqui
CLAUDE_MODEL=claude-sonnet-4-20250514

# Application Mode
SIMULATION_MODE=true  # false para usar lector USB real

# Cache Configuration
CACHE_ENABLED=true
CACHE_TTL=3600        # 1 hora en segundos
CACHE_MAX_SIZE=100    # Máximo de entradas en caché

# Performance
API_TIMEOUT=10        # Timeout de API en segundos
DEBOUNCE_DELAY=1.5    # Delay antes de llamar API

# Logging
LOG_LEVEL=INFO        # DEBUG, INFO, WARNING, ERROR
```

## 🔧 Troubleshooting

### La GUI no aparece en Mac

```bash
# Verificar que XQuartz está corriendo
pgrep XQuartz

# Si no está corriendo, iniciarlo
open -a XQuartz

# Dar permisos X11
xhost + 127.0.0.1

# Verificar variable DISPLAY
echo $DISPLAY  # Debe mostrar: host.docker.internal:0

# Reiniciar contenedor
docker-compose -f docker/docker-compose.dev.yml restart
```

### Error "Cannot connect to X server"

```bash
# Solución rápida
export DISPLAY=host.docker.internal:0
xhost + 127.0.0.1
./scripts/run_docker_dev.sh
```

### Lector de barras no detectado (Raspberry Pi)

```bash
# Listar dispositivos de entrada
ls -l /dev/input/

# Añadir usuario al grupo input
sudo usermod -a -G input $USER

# Dar permisos
sudo chmod +r /dev/input/event*

# Reiniciar sesión
```

### Performance lento

```bash
# Aumentar recursos de Docker Desktop
# Docker Desktop > Preferences > Resources
# Asignar mínimo: 4GB RAM, 2 CPUs

# Limpiar Docker
docker system prune -a

# Reducir tamaño de caché en .env
CACHE_MAX_SIZE=50
```

## 📈 Métricas de Rendimiento

| Métrica | Objetivo | Típico |
|---------|----------|---------|
| Tiempo de respuesta (con caché) | < 100ms | ~50ms |
| Tiempo de respuesta (sin caché) | < 2s | ~1.2s |
| Uso de memoria | < 500MB | ~350MB |
| Tasa de acierto de caché | > 60% | ~75% |
| Productos en BD | 100+ | 100 |

## 🗺️ Roadmap

- [x] **Fase 0**: Setup Docker + XQuartz
- [ ] **Fase 1**: Base de datos + Dataset de 100 productos
- [ ] **Fase 2**: Lector de código de barras + Simulador
- [ ] **Fase 3**: Cliente API Claude + Sistema de caché
- [ ] **Fase 4**: Interfaz gráfica tkinter
- [ ] **Fase 5**: Integración y testing
- [ ] **Fase 6**: Deployment a Raspberry Pi

## 🤝 Contribución

Las contribuciones son bienvenidas. Por favor:

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📝 Licencia

Este proyecto es privado y está en desarrollo.

## 👥 Autor

David Fernández Morilla

## 🙏 Agradecimientos

- **Anthropic** - Por la API de Claude
- **Comunidad Python** - Por las excelentes librerías
- **Comunidad Open Source** - Por Docker, tkinter, y herramientas de desarrollo

## 📞 Soporte

Para reportar bugs o solicitar features, por favor abre un issue en el repositorio.

---

**Nota**: Este proyecto está en desarrollo activo. Las características y API pueden cambiar.
