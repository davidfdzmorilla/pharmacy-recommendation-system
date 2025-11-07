# Plan de Trabajo Técnico Completo
## Sistema de Recomendación de Productos para Farmacia
### Desarrollo Local (Mac + Docker) → Deployment Raspberry Pi

---

## ÍNDICE

1. [Contexto del Proyecto](#contexto-del-proyecto)
2. [Arquitectura del Sistema](#arquitectura-del-sistema)
3. [Estructura de Directorios](#estructura-de-directorios)
4. [Configuración Docker](#configuración-docker)
5. [Especificaciones Técnicas](#especificaciones-técnicas)
6. [Implementación Fase por Fase](#implementación-fase-por-fase)
7. [Scripts y Configuración](#scripts-y-configuración)
8. [Instrucciones de Uso](#instrucciones-de-uso)
9. [Migración a Raspberry Pi](#migración-a-raspberry-pi)
10. [Troubleshooting](#troubleshooting)

---

## CONTEXTO DEL PROYECTO

### Objetivo
Desarrollar un sistema de punto de venta para farmacia con recomendaciones inteligentes en tiempo real usando Claude AI.

### Hardware Final
- **Producción**: Raspberry Pi 4 (4GB RAM) con lector de código de barras USB
- **Desarrollo**: Mac con Docker + XQuartz para GUI

### Características Principales
- ✅ Escaneo de códigos de barras EAN-13
- 🤖 Recomendaciones contextuales con Claude Sonnet 4
- 💾 Base de datos SQLite local
- ⚡ Sistema de caché inteligente con LRU
- 🎨 Interfaz gráfica tkinter
- 📊 Historial de ventas
- 🔄 Modo simulación para testing sin hardware

### Requisitos Críticos
- Tiempo de respuesta < 2 segundos tras escanear
- Recomendaciones actualizadas dinámicamente según carrito completo
- Consumo de memoria < 500MB
- Interfaz sin bloqueos durante llamadas API

---

## ARQUITECTURA DEL SISTEMA

```
┌─────────────────────────────────────────────────────────────┐
│                     DOCKER CONTAINER                         │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              APLICACIÓN PYTHON (tkinter)               │ │
│  │                                                        │ │
│  │  ┌──────────────┐    ┌──────────────┐                │ │
│  │  │ Barcode      │    │ Shopping     │                │ │
│  │  │ Reader/      │───▶│ Cart         │                │ │
│  │  │ Simulator    │    │ Manager      │                │ │
│  │  └──────────────┘    └──────┬───────┘                │ │
│  │                              │                        │ │
│  │                              ▼                        │ │
│  │                    ┌──────────────────┐              │ │
│  │                    │ Recommendation   │              │ │
│  │                    │ Engine           │              │ │
│  │                    └────────┬─────────┘              │ │
│  │                             │                        │ │
│  │         ┌───────────────────┼─────────────────┐     │ │
│  │         ▼                   ▼                 ▼     │ │
│  │  ┌────────────┐      ┌───────────┐    ┌─────────┐ │ │
│  │  │ Cache      │      │ Claude    │    │ SQLite  │ │ │
│  │  │ Manager    │      │ API       │    │ DB      │ │ │
│  │  │ (LRU+TTL)  │      │ Client    │    │         │ │ │
│  │  └────────────┘      └───────────┘    └─────────┘ │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │ Anthropic Claude │
                    │ API (External)   │
                    └──────────────────┘
```

### Flujo de Datos

1. **Usuario escanea producto** → Barcode Reader captura EAN-13
2. **Validación** → Database lookup por código de barras
3. **Actualización de carrito** → Shopping Cart Manager
4. **Trigger con debounce** → Espera 1.5s tras último escaneo
5. **Generación de hash** → Hash del carrito para caché
6. **Verificación de caché** → Si existe, devolver recomendaciones
7. **Llamada a Claude API** → Si no hay caché
8. **Parseo y almacenamiento** → Guardar en caché + mostrar en UI
9. **Actualización de UI** → Sin bloquear interfaz (threading)

---

## ESTRUCTURA DE DIRECTORIOS

```
pharmacy-recommendation-system/
├── docker/
│   ├── Dockerfile                    # Producción/similar a RPi
│   ├── Dockerfile.dev                # Desarrollo con hot-reload
│   ├── docker-compose.yml            # Compose producción
│   └── docker-compose.dev.yml        # Compose desarrollo
│
├── raspberry_app/
│   ├── __init__.py
│   ├── main.py                       # Punto de entrada
│   ├── config.py                     # Configuración centralizada
│   │
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ventana principal
│   │   ├── cart_widget.py            # Widget del carrito
│   │   ├── recommendations_widget.py # Widget recomendaciones
│   │   └── styles.py                 # Estilos UI
│   │
│   ├── barcode/
│   │   ├── __init__.py
│   │   ├── reader.py                 # Lector USB (evdev)
│   │   └── simulator.py              # Simulador testing
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── claude_client.py          # Cliente Anthropic API
│   │   ├── prompt_builder.py         # Constructor de prompts
│   │   └── cache_manager.py          # Caché LRU+TTL
│   │
│   ├── database/
│   │   ├── __init__.py
│   │   ├── db_manager.py             # Gestor SQLite
│   │   ├── models.py                 # Modelos de datos
│   │   └── schema.sql                # Esquema DDL
│   │
│   └── utils/
│       ├── __init__.py
│       ├── logger.py                 # Sistema logging
│       └── validators.py             # Validadores
│
├── data/
│   ├── pharmacy.db                   # Base de datos SQLite
│   └── sample_products.json          # 100 productos ejemplo
│
├── config/
│   ├── .env.example                  # Template variables entorno
│   └── settings.yaml                 # Configuración app
│
├── scripts/
│   ├── setup_docker.sh               # Setup Mac + Docker
│   ├── setup_raspberry.sh            # Setup RPi nativo
│   ├── run_docker_dev.sh             # Ejecutar en dev
│   ├── run_tests.sh                  # Ejecutar tests
│   ├── shell.sh                      # Shell interactivo
│   ├── init_database.py              # Inicializar DB
│   └── import_products.py            # Importar productos
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                   # Fixtures pytest
│   ├── test_barcode_reader.py
│   ├── test_api_client.py
│   ├── test_cache.py
│   ├── test_database.py
│   └── test_integration.py
│
├── docs/
│   ├── INSTALLATION.md
│   ├── API_INTEGRATION.md
│   ├── TESTING.md
│   └── ARCHITECTURE.md
│
├── logs/                             # Logs aplicación
├── .dockerignore
├── .gitignore
├── requirements.txt                  # Dependencias producción
├── requirements-dev.txt              # Dependencias desarrollo
└── README.md
```

---

## CONFIGURACIÓN DOCKER

### Dockerfile (Producción)

**Ubicación**: `docker/Dockerfile`

```dockerfile
FROM python:3.11-slim-bookworm

# Variables de entorno
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

# Instalar dependencias del sistema (similares a Raspberry Pi OS)
RUN apt-get update && apt-get install -y \
    python3-tk \
    libevdev-dev \
    sqlite3 \
    x11-apps \
    && rm -rf /var/lib/apt/lists/*

# Crear usuario no-root
RUN useradd -m -u 1000 pharmacy && \
    mkdir -p /app /app/data /app/logs && \
    chown -R pharmacy:pharmacy /app

WORKDIR /app

# Copiar requirements
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copiar código
COPY --chown=pharmacy:pharmacy . .

# Cambiar a usuario no-root
USER pharmacy

# Exponer display para GUI (X11)
ENV DISPLAY=:0

# Comando por defecto
CMD ["python", "raspberry_app/main.py"]
```

### Dockerfile.dev (Desarrollo)

**Ubicación**: `docker/Dockerfile.dev`

```dockerfile
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

# Instalar dependencias + herramientas de desarrollo
RUN apt-get update && apt-get install -y \
    python3-tk \
    libevdev-dev \
    sqlite3 \
    x11-apps \
    git \
    vim \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 pharmacy && \
    mkdir -p /app /app/data /app/logs && \
    chown -R pharmacy:pharmacy /app

WORKDIR /app

# Copiar requirements incluyendo dev
COPY requirements.txt requirements-dev.txt ./
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install -r requirements-dev.txt

USER pharmacy

ENV DISPLAY=:0

# En dev, el código se monta como volumen
CMD ["python", "raspberry_app/main.py"]
```

### docker-compose.dev.yml

**Ubicación**: `docker/docker-compose.dev.yml`

```yaml
version: '3.8'

services:
  pharmacy-app-dev:
    build:
      context: ..
      dockerfile: docker/Dockerfile.dev
    container_name: pharmacy-app-dev
    environment:
      - DISPLAY=${DISPLAY}
      - SIMULATION_MODE=true
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - PYTHONPATH=/app
    env_file:
      - ../.env
    volumes:
      # Hot-reload: montar código como volumen
      - ../raspberry_app:/app/raspberry_app
      - ../scripts:/app/scripts
      - ../tests:/app/tests
      - ../data:/app/data
      - ../logs:/app/logs
      # X11 para GUI en Mac
      - /tmp/.X11-unix:/tmp/.X11-unix:rw
    network_mode: host
    stdin_open: true
    tty: true
    command: python raspberry_app/main.py
```

### .dockerignore

```
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
ENV/
.env
.venv
*.egg-info/
dist/
build/
.pytest_cache/
.coverage
htmlcov/
.git/
.gitignore
.DS_Store
*.log
logs/
data/pharmacy.db
docker/
README.md
docs/
```

---

## ESPECIFICACIONES TÉCNICAS

### Dependencias

**requirements.txt**:
```txt
# Core API
anthropic==0.40.0

# Environment & Config
python-dotenv==1.0.0
pyyaml==6.0.1

# Database
sqlalchemy==2.0.23

# GUI (tkinter viene con Python)
Pillow==10.1.0

# Barcode reading
evdev==1.6.1; sys_platform == 'linux'
pynput==1.7.6

# HTTP & Utilities
requests==2.31.0
cachetools==5.3.2
```

**requirements-dev.txt**:
```txt
# Testing
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
pytest-mock==3.12.0

# Code quality
black==23.11.0
pylint==3.0.2
mypy==1.7.1
flake8==6.1.0

# Development
ipython==8.18.0
ipdb==0.13.13
```

### Esquema de Base de Datos

**Ubicación**: `raspberry_app/database/schema.sql`

```sql
-- Tabla de productos
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ean TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    price REAL NOT NULL,
    category TEXT NOT NULL,
    active_ingredient TEXT,
    description TEXT,
    stock INTEGER DEFAULT 0,
    requires_prescription BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_products_ean ON products(ean);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
CREATE INDEX IF NOT EXISTS idx_products_active_ingredient ON products(active_ingredient);

-- Tabla de ventas
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    total REAL NOT NULL,
    items_count INTEGER NOT NULL,
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de items de venta
CREATE TABLE IF NOT EXISTS sale_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER DEFAULT 1,
    unit_price REAL NOT NULL,
    FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

-- Tabla de caché de recomendaciones
CREATE TABLE IF NOT EXISTS recommendation_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cart_hash TEXT UNIQUE NOT NULL,
    recommendations TEXT NOT NULL,
    hit_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cache_hash ON recommendation_cache(cart_hash);

-- Tabla de logs de API
CREATE TABLE IF NOT EXISTS api_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_type TEXT NOT NULL,
    cart_items INTEGER NOT NULL,
    response_time REAL,
    success BOOLEAN,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Configuración

**Ubicación**: `raspberry_app/config.py`

```python
import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    # Paths
    BASE_DIR: Path = Path(__file__).parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    DB_PATH: Path = DATA_DIR / "pharmacy.db"
    
    # API Configuration
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"
    MAX_TOKENS: int = 1024
    TEMPERATURE: float = 0.3
    
    # Cache Configuration
    CACHE_ENABLED: bool = True
    CACHE_TTL: int = 3600  # 1 hora
    CACHE_MAX_SIZE: int = 100
    
    # Recommendation Settings
    MAX_RECOMMENDATIONS: int = 5
    MIN_RECOMMENDATIONS: int = 3
    DEBOUNCE_DELAY: float = 1.5  # segundos
    
    # UI Configuration
    WINDOW_WIDTH: int = 1024
    WINDOW_HEIGHT: int = 600
    FONT_FAMILY: str = "Arial"
    FONT_SIZE: int = 11
    
    # Barcode Settings
    BARCODE_LENGTH: int = 13  # EAN-13
    SIMULATION_MODE: bool = os.getenv("SIMULATION_MODE", "false").lower() == "true"
    
    # Performance
    MAX_MEMORY_MB: int = 500
    API_TIMEOUT: int = 10  # segundos
    
    def validate(self):
        if not self.ANTHROPIC_API_KEY and not self.SIMULATION_MODE:
            raise ValueError("ANTHROPIC_API_KEY no configurada")
        
        self.DATA_DIR.mkdir(exist_ok=True)
        return True

config = Config()
```

### Prompt System para Claude

**Ubicación**: `raspberry_app/api/prompt_builder.py`

```python
SYSTEM_PROMPT = """Eres un farmacéutico experto especializado en recomendaciones de productos complementarios para farmacias.

Tu objetivo es analizar el carrito de compra actual y sugerir productos adicionales que sean:
1. Complementarios terapéuticamente con los productos ya seleccionados
2. Que mejoren la eficacia del tratamiento o prevengan efectos secundarios
3. Productos de autocuidado relevantes para la condición tratada
4. NO duplicar categorías o principios activos ya presentes en el carrito

CRITERIOS DE RECOMENDACIÓN:
- Si hay analgésicos antiinflamatorios (ibuprofeno, naproxeno): recomendar protectores gástricos
- Si hay antibióticos: recomendar probióticos para restaurar flora intestinal
- Si hay productos para dolor: considerar cremas/geles tópicos complementarios
- Si hay vitaminas específicas: complementar con otras sinérgicas (ej: Vit D con calcio)
- Si hay productos dermatológicos: recomendar productos de higiene específicos
- Si hay productos respiratorios: considerar complementos inmunológicos

FORMATO DE RESPUESTA:
Debes responder ÚNICAMENTE con un JSON válido con la siguiente estructura:
{
  "recommendations": [
    {
      "product_name": "Nombre exacto del producto recomendado",
      "category": "Categoría del producto",
      "reason": "Razón específica y clara de la recomendación (máx 100 caracteres)",
      "priority": "high" | "medium" | "low",
      "estimated_price": "precio estimado en euros"
    }
  ],
  "analysis": "Breve análisis del carrito en 1-2 líneas"
}

RESTRICCIONES:
- Máximo 5 recomendaciones, mínimo 3
- Priorizar productos de uso común en farmacias españolas
- Ser específico con nombres de productos reales
- Razones concisas y orientadas al beneficio del paciente
- NO recomendar productos con receta médica a menos que ya haya productos similares en el carrito
"""
```

### Dataset de Productos

**Ubicación**: `data/sample_products.json`

Se incluirán 100 productos farmacéuticos realistas con la siguiente estructura:

```json
[
  {
    "ean": "8470001234567",
    "name": "Ibuprofeno 600mg 20 comprimidos",
    "price": 4.95,
    "category": "Analgésicos",
    "active_ingredient": "Ibuprofeno",
    "description": "Antiinflamatorio no esteroideo para dolor y fiebre",
    "stock": 50
  },
  {
    "ean": "8470001234568",
    "name": "Paracetamol 1g 20 comprimidos",
    "price": 3.50,
    "category": "Analgésicos",
    "active_ingredient": "Paracetamol",
    "description": "Analgésico y antipirético",
    "stock": 75
  }
  // ... 98 productos más
]
```

**Categorías incluidas**:
- Analgésicos (10 productos)
- Digestivos (8 productos)
- Vitaminas y Suplementos (12 productos)
- Dermatología (10 productos)
- Respiratorio (8 productos)
- Antihistamínicos (6 productos)
- Oftalmología (6 productos)
- Higiene bucal (8 productos)
- Cuidado capilar (8 productos)
- Infantil (10 productos)
- Primeros auxilios (8 productos)
- Deportivos (6 productos)

---

## IMPLEMENTACIÓN FASE POR FASE

### FASE 0: Setup Docker (1 hora)

**Objetivo**: Configurar entorno de desarrollo en Mac con Docker + XQuartz

#### Tareas:
1. ✅ Crear `docker/Dockerfile`
2. ✅ Crear `docker/Dockerfile.dev`
3. ✅ Crear `docker/docker-compose.yml`
4. ✅ Crear `docker/docker-compose.dev.yml`
5. ✅ Crear `.dockerignore`
6. ✅ Crear `scripts/setup_docker.sh`
7. ✅ Crear `scripts/run_docker_dev.sh`
8. ✅ Testing de GUI con XQuartz

#### Validación:
```bash
./scripts/setup_docker.sh
./scripts/run_docker_dev.sh
# Debe aparecer ventana vacía de tkinter
```

---

### FASE 1: Base de Datos y Dataset (2-3 horas)

**Objetivo**: Implementar capa de persistencia con SQLite

#### Archivos a crear:

**1. `raspberry_app/database/schema.sql`**
- Definir esquema completo de tablas
- Crear índices para optimización
- Incluir triggers si necesario

**2. `raspberry_app/database/models.py`**
```python
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class Product:
    id: Optional[int]
    ean: str
    name: str
    price: float
    category: str
    active_ingredient: Optional[str]
    description: Optional[str]
    stock: int = 0
    
    @classmethod
    def from_db_row(cls, row):
        return cls(
            id=row['id'],
            ean=row['ean'],
            name=row['name'],
            price=row['price'],
            category=row['category'],
            active_ingredient=row['active_ingredient'],
            description=row['description'],
            stock=row['stock']
        )
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "category": self.category,
            "active_ingredient": self.active_ingredient,
            "price": self.price,
            "description": self.description
        }
```

**3. `raspberry_app/database/db_manager.py`**
```python
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional

from ..config import config
from .models import Product

class DatabaseManager:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or config.DB_PATH
        self.init_database()
    
    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def init_database(self):
        schema_path = Path(__file__).parent / "schema.sql"
        with self.get_connection() as conn:
            with open(schema_path, 'r', encoding='utf-8') as f:
                conn.executescript(f.read())
    
    def get_product_by_ean(self, ean: str) -> Optional[Product]:
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM products WHERE ean = ?", (ean,))
            row = cursor.fetchone()
            return Product.from_db_row(row) if row else None
    
    def add_product(self, product: Product) -> int:
        with self.get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO products 
                   (ean, name, price, category, active_ingredient, description, stock)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (product.ean, product.name, product.price, product.category,
                 product.active_ingredient, product.description, product.stock)
            )
            return cursor.lastrowid
```

**4. `data/sample_products.json`**
- Crear dataset con 100 productos
- Distribuir entre todas las categorías
- Asegurar datos realistas

**5. `scripts/init_database.py`**
```python
#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from raspberry_app.database.db_manager import DatabaseManager
from raspberry_app.config import config

def main():
    print("Inicializando base de datos...")
    config.DATA_DIR.mkdir(exist_ok=True)
    db = DatabaseManager()
    print(f"✅ Base de datos creada en: {config.DB_PATH}")

if __name__ == "__main__":
    main()
```

**6. `scripts/import_products.py`**
```python
#!/usr/bin/env python3
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from raspberry_app.database.db_manager import DatabaseManager
from raspberry_app.database.models import Product

def main():
    json_path = Path(__file__).parent.parent / "data" / "sample_products.json"
    
    with open(json_path, 'r', encoding='utf-8') as f:
        products_data = json.load(f)
    
    db = DatabaseManager()
    count = 0
    
    for product_data in products_data:
        product = Product(
            id=None,
            ean=product_data['ean'],
            name=product_data['name'],
            price=product_data['price'],
            category=product_data['category'],
            active_ingredient=product_data.get('active_ingredient'),
            description=product_data.get('description'),
            stock=product_data.get('stock', 0)
        )
        
        try:
            db.add_product(product)
            count += 1
            print(f"✓ {product.name}")
        except Exception as e:
            print(f"✗ Error: {e}")
    
    print(f"\n✅ {count} productos importados")

if __name__ == "__main__":
    main()
```

#### Tests:
```python
# tests/test_database.py
def test_create_and_retrieve_product(db_manager):
    product = Product(...)
    product_id = db_manager.add_product(product)
    retrieved = db_manager.get_product_by_ean(product.ean)
    assert retrieved.name == product.name
```

#### Validación:
```bash
./scripts/shell.sh
python scripts/init_database.py
python scripts/import_products.py
sqlite3 data/pharmacy.db "SELECT COUNT(*) FROM products;"
# Debe devolver 100
```

---

### FASE 2: Lector de Código de Barras (2-3 horas)

**Objetivo**: Implementar captura de códigos EAN-13 y simulador

#### Archivos a crear:

**1. `raspberry_app/barcode/reader.py`**
```python
import threading
from typing import Callable, Optional
from queue import Queue
import logging

try:
    from evdev import InputDevice, categorize, ecodes
    EVDEV_AVAILABLE = True
except ImportError:
    EVDEV_AVAILABLE = False

logger = logging.getLogger(__name__)

class BarcodeReader:
    def __init__(self, device_path: Optional[str] = None):
        self.device_path = device_path
        self.device = None
        self.running = False
        self.thread = None
        self.callback: Optional[Callable] = None
        self.buffer = ""
        self.barcode_queue = Queue()
    
    def set_callback(self, callback: Callable[[str], None]):
        self.callback = callback
    
    def start(self):
        if not EVDEV_AVAILABLE:
            logger.error("evdev no disponible")
            return False
        
        if not self.device_path:
            self.device_path = self.find_barcode_device()
        
        if not self.device_path:
            logger.error("No se encontró dispositivo")
            return False
        
        try:
            self.device = InputDevice(self.device_path)
            self.running = True
            self.thread = threading.Thread(target=self._read_loop, daemon=True)
            self.thread.start()
            return True
        except Exception as e:
            logger.error(f"Error: {e}")
            return False
    
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
```

**2. `raspberry_app/barcode/simulator.py`**
```python
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional
import logging

logger = logging.getLogger(__name__)

class BarcodeSimulator:
    def __init__(self, master: tk.Tk):
        self.master = master
        self.callback: Optional[Callable] = None
        self.window = None
    
    def set_callback(self, callback: Callable[[str], None]):
        self.callback = callback
    
    def create_simulator_window(self):
        self.window = tk.Toplevel(self.master)
        self.window.title("Simulador de Lector de Barras")
        self.window.geometry("400x300")
        
        frame = ttk.Frame(self.window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Introduce código EAN-13:", 
                 font=("Arial", 12)).pack(pady=10)
        
        self.barcode_entry = ttk.Entry(frame, font=("Arial", 14), width=20)
        self.barcode_entry.pack(pady=10)
        self.barcode_entry.focus()
        
        ttk.Button(frame, text="Escanear", 
                  command=self._simulate_scan).pack(pady=10)
        
        self.barcode_entry.bind('<Return>', lambda e: self._simulate_scan())
        
        # Códigos de ejemplo
        examples_frame = ttk.LabelFrame(frame, text="Ejemplos", padding="10")
        examples_frame.pack(pady=10, fill=tk.X)
        
        examples = [
            ("8470001234567", "Ibuprofeno 600mg"),
            ("8470001234569", "Omeprazol 20mg"),
            ("8470001234571", "Vitamina C 1000mg"),
        ]
        
        for ean, name in examples:
            btn = ttk.Button(examples_frame, text=f"{ean} ({name})",
                           command=lambda e=ean: self._scan_example(e))
            btn.pack(fill=tk.X, pady=2)
    
    def _scan_example(self, ean: str):
        self.barcode_entry.delete(0, tk.END)
        self.barcode_entry.insert(0, ean)
        self._simulate_scan()
    
    def _simulate_scan(self):
        barcode = self.barcode_entry.get().strip()
        
        if barcode and len(barcode) == 13 and barcode.isdigit():
            logger.info(f"Código simulado: {barcode}")
            if self.callback:
                self.callback(barcode)
            self.barcode_entry.delete(0, tk.END)
            self.barcode_entry.focus()
        else:
            logger.warning("Código inválido")
    
    def show(self):
        if not self.window:
            self.create_simulator_window()
        self.window.deiconify()
```

#### Tests:
```python
# tests/test_barcode_reader.py
def test_simulator_validates_ean13():
    # Test que solo acepta EAN-13 válidos
    pass
```

---

### FASE 3: Cliente API de Claude (2-3 horas)

**Objetivo**: Integración con Anthropic API y prompt engineering

#### Archivos a crear:

**1. `raspberry_app/api/prompt_builder.py`**
```python
from typing import List, Dict
import json

class PromptBuilder:
    SYSTEM_PROMPT = """[Ver especificación completa arriba]"""
    
    @staticmethod
    def build_recommendation_prompt(cart_items: List[Dict]) -> str:
        if not cart_items:
            return ""
        
        cart_summary = {
            "total_items": len(cart_items),
            "categories": list(set(item['category'] for item in cart_items)),
            "active_ingredients": list(set(
                item.get('active_ingredient', 'N/A') 
                for item in cart_items 
                if item.get('active_ingredient')
            )),
            "products": [
                {
                    "name": item['name'],
                    "category": item['category'],
                    "active_ingredient": item.get('active_ingredient', 'N/A'),
                    "price": item['price']
                }
                for item in cart_items
            ]
        }
        
        prompt = f"""Analiza el siguiente carrito de compra y proporciona recomendaciones:

CARRITO ACTUAL:
{json.dumps(cart_summary, indent=2, ensure_ascii=False)}

Proporciona 3-5 recomendaciones priorizadas en formato JSON."""
        
        return prompt
    
    @staticmethod
    def parse_recommendations(response_text: str) -> Dict:
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except:
                    pass
            
            return {
                "recommendations": [],
                "analysis": "Error al parsear respuesta"
            }
```

**2. `raspberry_app/api/cache_manager.py`**
```python
import time
import logging
from typing import Optional, Dict
from collections import OrderedDict
from threading import Lock

from ..config import config

logger = logging.getLogger(__name__)

class CacheManager:
    def __init__(self, max_size: int = None, ttl: int = None):
        self.max_size = max_size or config.CACHE_MAX_SIZE
        self.ttl = ttl or config.CACHE_TTL
        self.cache = OrderedDict()
        self.timestamps = {}
        self.lock = Lock()
    
    def get(self, key: str) -> Optional[Dict]:
        with self.lock:
            if key not in self.cache:
                return None
            
            if time.time() - self.timestamps[key] > self.ttl:
                del self.cache[key]
                del self.timestamps[key]
                return None
            
            self.cache.move_to_end(key)
            return self.cache[key]
    
    def set(self, key: str, value: Dict):
        with self.lock:
            if key in self.cache:
                del self.cache[key]
            elif len(self.cache) >= self.max_size:
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
                del self.timestamps[oldest_key]
            
            self.cache[key] = value
            self.timestamps[key] = time.time()
```

**3. `raspberry_app/api/claude_client.py`**
```python
import time
import logging
from typing import List, Dict, Optional
from anthropic import Anthropic
import hashlib
import json

from ..config import config
from .prompt_builder import PromptBuilder
from .cache_manager import CacheManager

logger = logging.getLogger(__name__)

class ClaudeClient:
    def __init__(self, cache_manager: CacheManager):
        if not config.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY no configurada")
        
        self.client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.cache_manager = cache_manager
        self.prompt_builder = PromptBuilder()
    
    def get_recommendations(self, cart_items: List[Dict]) -> Optional[Dict]:
        if not cart_items:
            return None
        
        cart_hash = self._generate_cart_hash(cart_items)
        
        if config.CACHE_ENABLED:
            cached = self.cache_manager.get(cart_hash)
            if cached:
                logger.info("Recomendaciones desde caché")
                return cached
        
        prompt = self.prompt_builder.build_recommendation_prompt(cart_items)
        
        try:
            start_time = time.time()
            
            response = self.client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=config.MAX_TOKENS,
                temperature=config.TEMPERATURE,
                system=PromptBuilder.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_time = time.time() - start_time
            logger.info(f"Respuesta en {response_time:.2f}s")
            
            response_text = response.content[0].text
            recommendations = self.prompt_builder.parse_recommendations(response_text)
            
            if config.CACHE_ENABLED:
                self.cache_manager.set(cart_hash, recommendations)
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error en API: {e}")
            return None
    
    def _generate_cart_hash(self, cart_items: List[Dict]) -> str:
        cart_repr = json.dumps(
            sorted([
                {
                    'name': item['name'],
                    'category': item['category'],
                    'active_ingredient': item.get('active_ingredient', '')
                }
                for item in cart_items
            ], key=lambda x: x['name']),
            sort_keys=True
        )
        return hashlib.md5(cart_repr.encode()).hexdigest()
```

#### Tests:
```python
# tests/test_api_client.py
def test_cache_hit(mock_claude_client):
    # Verificar que segunda llamada usa caché
    pass

def test_prompt_building():
    # Verificar construcción correcta del prompt
    pass
```

---

### FASE 4: Interfaz Gráfica (3-4 horas)

**Objetivo**: Crear UI responsiva con tkinter

#### Archivo principal:

**`raspberry_app/ui/main_window.py`**
```python
import tkinter as tk
from tkinter import ttk, messagebox
import logging
from typing import List, Dict
import threading

from ..config import config
from ..database.db_manager import DatabaseManager
from ..api.claude_client import ClaudeClient
from ..api.cache_manager import CacheManager
from ..barcode.simulator import BarcodeSimulator

logger = logging.getLogger(__name__)

class MainWindow:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Sistema de Recomendación Farmacéutica")
        self.root.geometry(f"{config.WINDOW_WIDTH}x{config.WINDOW_HEIGHT}")
        
        self.db = DatabaseManager()
        self.cache_manager = CacheManager()
        self.claude_client = ClaudeClient(self.cache_manager)
        
        self.cart: List[Dict] = []
        self.current_recommendations: List[Dict] = []
        self.debounce_timer = None
        
        self.create_widgets()
        
        if config.SIMULATION_MODE:
            self.simulator = BarcodeSimulator(self.root)
            self.simulator.set_callback(self.on_barcode_scanned)
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configurar grid
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=1)
        
        # === CARRITO ===
        cart_frame = ttk.LabelFrame(main_frame, text="Carrito", padding="10")
        cart_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        self.cart_tree = ttk.Treeview(cart_frame, columns=('producto', 'precio'), 
                                      show='tree headings', height=15)
        self.cart_tree.heading('producto', text='Producto')
        self.cart_tree.heading('precio', text='Precio')
        self.cart_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        cart_scroll = ttk.Scrollbar(cart_frame, orient=tk.VERTICAL, 
                                    command=self.cart_tree.yview)
        cart_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.cart_tree.configure(yscrollcommand=cart_scroll.set)
        
        # Total y botones
        cart_bottom = ttk.Frame(cart_frame)
        cart_bottom.pack(fill=tk.X, pady=10)
        
        self.total_label = ttk.Label(cart_bottom, text="Total: €0.00", 
                                     font=(config.FONT_FAMILY, 14, 'bold'))
        self.total_label.pack()
        
        buttons_frame = ttk.Frame(cart_bottom)
        buttons_frame.pack(pady=5)
        
        ttk.Button(buttons_frame, text="Eliminar", 
                  command=self.remove_item).pack(side=tk.LEFT, padx=2)
        ttk.Button(buttons_frame, text="Nueva Compra", 
                  command=self.new_sale).pack(side=tk.LEFT, padx=2)
        ttk.Button(buttons_frame, text="Finalizar", 
                  command=self.complete_sale).pack(side=tk.LEFT, padx=2)
        
        # === RECOMENDACIONES ===
        rec_frame = ttk.LabelFrame(main_frame, text="Recomendaciones", padding="10")
        rec_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        self.status_label = ttk.Label(rec_frame, 
                                      text="Escanea productos para ver recomendaciones",
                                      foreground="gray")
        self.status_label.pack(fill=tk.X, pady=5)
        
        # Canvas con scroll
        canvas_frame = ttk.Frame(rec_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.rec_canvas = tk.Canvas(canvas_frame, bg='white')
        rec_scroll = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL,
                                   command=self.rec_canvas.yview)
        
        self.rec_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        rec_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.rec_canvas.configure(yscrollcommand=rec_scroll.set)
        
        self.rec_inner_frame = ttk.Frame(self.rec_canvas)
        self.rec_canvas.create_window((0, 0), window=self.rec_inner_frame, anchor='nw')
        
        # === TOOLBAR ===
        toolbar = ttk.Frame(main_frame)
        toolbar.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        if config.SIMULATION_MODE:
            ttk.Button(toolbar, text="Abrir Simulador", 
                      command=lambda: self.simulator.show()).pack(side=tk.LEFT, padx=5)
        
        self.loading_label = ttk.Label(toolbar, text="", foreground="blue")
        self.loading_label.pack(side=tk.RIGHT, padx=5)
    
    def on_barcode_scanned(self, barcode: str):
        logger.info(f"Código escaneado: {barcode}")
        product = self.db.get_product_by_ean(barcode)
        
        if product:
            self.add_to_cart(product)
        else:
            messagebox.showwarning("No encontrado", 
                                  f"Producto no encontrado: {barcode}")
    
    def add_to_cart(self, product):
        cart_item = {
            'product_id': product.id,
            'name': product.name,
            'price': product.price,
            'category': product.category,
            'active_ingredient': product.active_ingredient
        }
        
        self.cart.append(cart_item)
        self.update_cart_display()
        self.schedule_recommendation_update()
    
    def schedule_recommendation_update(self):
        if self.debounce_timer:
            self.root.after_cancel(self.debounce_timer)
        
        self.debounce_timer = self.root.after(
            int(config.DEBOUNCE_DELAY * 1000),
            self.update_recommendations
        )
    
    def update_recommendations(self):
        if not self.cart:
            return
        
        self.status_label.config(text="Obteniendo recomendaciones...", foreground="blue")
        self.loading_label.config(text="⏳ Cargando...")
        
        thread = threading.Thread(target=self._fetch_recommendations, daemon=True)
        thread.start()
    
    def _fetch_recommendations(self):
        try:
            recommendations_data = self.claude_client.get_recommendations(self.cart)
            self.root.after(0, self._display_recommendations, recommendations_data)
        except Exception as e:
            logger.error(f"Error: {e}")
```

---

### FASE 5: Integración y Testing (2 horas)

**Objetivo**: Conectar todos los componentes y testing end-to-end

#### `raspberry_app/main.py`

```python
#!/usr/bin/env python3
import tkinter as tk
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from raspberry_app.config import config
from raspberry_app.ui.main_window import MainWindow
from raspberry_app.utils.logger import setup_logging

def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        config.validate()
        logger.info("=== Iniciando Sistema Farmacéutico ===")
        
        root = tk.Tk()
        app = MainWindow(root)
        root.mainloop()
        
    except Exception as e:
        logger.error(f"Error fatal: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
```

---

## SCRIPTS Y CONFIGURACIÓN

### Script de Setup Docker

**`scripts/setup_docker.sh`**

```bash
#!/bin/bash
set -e

echo "=== Setup Sistema Farmacéutico (Docker + Mac) ==="

# Verificar Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker no instalado"
    echo "Instala desde: https://www.docker.com/products/docker-desktop"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "❌ Docker no está corriendo"
    exit 1
fi

echo "✅ Docker OK"

# Crear .env
if [ ! -f .env ]; then
    cp config/.env.example .env
    echo "⚠️  Edita .env y añade ANTHROPIC_API_KEY"
fi

# Crear directorios
mkdir -p data logs config

# Configurar XQuartz
if ! command -v xquartz &> /dev/null; then
    echo "⚠️  XQuartz no instalado"
    echo "Descarga desde: https://www.xquartz.org/"
    exit 1
fi

xhost + 127.0.0.1 > /dev/null 2>&1 || true

# Build
cd docker
docker-compose -f docker-compose.dev.yml build

echo ""
echo "✅ Setup completado!"
echo "Próximos pasos:"
echo "1. Edita .env con tu ANTHROPIC_API_KEY"
echo "2. Abre XQuartz"
echo "3. Ejecuta: ./scripts/run_docker_dev.sh"
```

### Script de Ejecución

**`scripts/run_docker_dev.sh`**

```bash
#!/bin/bash
set -e

# Verificar XQuartz
if ! pgrep -x "XQuartz" > /dev/null; then
    echo "Abriendo XQuartz..."
    open -a XQuartz
    sleep 5
fi

export DISPLAY=host.docker.internal:0
xhost + 127.0.0.1 > /dev/null 2>&1 || true

echo "=== Iniciando aplicación ==="

# Inicializar DB si no existe
if [ ! -f data/pharmacy.db ]; then
    echo "Inicializando base de datos..."
    cd docker
    docker-compose -f docker-compose.dev.yml run --rm pharmacy-app-dev \
        python scripts/init_database.py
    docker-compose -f docker-compose.dev.yml run --rm pharmacy-app-dev \
        python scripts/import_products.py
    cd ..
fi

# Ejecutar app
cd docker
docker-compose -f docker-compose.dev.yml up

trap 'docker-compose -f docker-compose.dev.yml down' EXIT
```

### Configuración de Entorno

**`config/.env.example`**

```bash
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
```

---

## INSTRUCCIONES DE USO

### Setup Inicial (Primera Vez)

```bash
# 1. Clonar repositorio
git clone <repo-url>
cd pharmacy-recommendation-system

# 2. Instalar Docker Desktop y XQuartz
# Docker: https://www.docker.com/products/docker-desktop
# XQuartz: https://www.xquartz.org/

# 3. Configurar XQuartz
# - Abrir XQuartz
# - Preferencias > Seguridad
# - ✅ "Permitir conexiones desde clientes de red"
# - Reiniciar XQuartz
# - Cerrar sesión y volver a iniciar Mac

# 4. Ejecutar setup
chmod +x scripts/*.sh
./scripts/setup_docker.sh

# 5. Configurar API key
nano .env
# Añadir: ANTHROPIC_API_KEY=tu_clave_aqui
```

### Uso Diario

```bash
# 1. Asegurar que XQuartz está corriendo
open -a XQuartz

# 2. Ejecutar aplicación
./scripts/run_docker_dev.sh

# 3. Usar el simulador de códigos de barras
#    (botón "Abrir Simulador" en la app)

# 4. Para detener: Ctrl+C
```

### Testing

```bash
# Todos los tests
./scripts/run_tests.sh

# Tests específicos
cd docker
docker-compose -f docker-compose.dev.yml run --rm pharmacy-app-dev \
    pytest tests/test_api_client.py -v

# Con cobertura
docker-compose -f docker-compose.dev.yml run --rm pharmacy-app-dev \
    pytest --cov=raspberry_app tests/
```

### Debugging

```bash
# Shell interactivo en el contenedor
./scripts/shell.sh

# Ver logs
cd docker
docker-compose -f docker-compose.dev.yml logs -f

# Inspeccionar base de datos
./scripts/shell.sh
sqlite3 data/pharmacy.db
```

---

## MIGRACIÓN A RASPBERRY PI

### Opción 1: Exportar Imagen Docker

```bash
# En Mac
cd docker
docker save pharmacy-app:latest | gzip > pharmacy-app.tar.gz

# Copiar a RPi
scp pharmacy-app.tar.gz pi@raspberrypi.local:~

# En RPi
ssh pi@raspberrypi.local
gunzip -c pharmacy-app.tar.gz | docker load
docker run -it --privileged pharmacy-app:latest
```

### Opción 2: Instalación Nativa

```bash
# Copiar proyecto a RPi
scp -r pharmacy-recommendation-system pi@raspberrypi.local:~

# SSH a RPi
ssh pi@raspberrypi.local
cd pharmacy-recommendation-system

# Ejecutar setup nativo
./scripts/setup_raspberry.sh

# Configurar .env
nano .env
# SIMULATION_MODE=false para usar lector real

# Ejecutar
source venv/bin/activate
python raspberry_app/main.py
```

---

## TROUBLESHOOTING

### Mac: GUI no aparece

```bash
# Verificar XQuartz
pgrep XQuartz

# Si no está corriendo
open -a XQuartz

# Verificar permisos
xhost + 127.0.0.1

# Verificar DISPLAY
echo $DISPLAY  # debe ser: host.docker.internal:0

# Reinicio completo
killall XQuartz
open -a XQuartz
sleep 5
./scripts/run_docker_dev.sh
```

### Docker: Error "Cannot connect to X server"

```bash
# Solución
export DISPLAY=host.docker.internal:0
xhost + 127.0.0.1

# Si persiste, reiniciar Docker Desktop
```

### Raspberry Pi: Lector no detectado

```bash
# Listar dispositivos
ls -l /dev/input/

# Dar permisos
sudo chmod +r /dev/input/event*

# Añadir usuario a grupo input
sudo usermod -a -G input $USER

# Reiniciar sesión
```

### Performance lento

```bash
# En Docker Desktop: Preferences > Resources
# Asignar al menos:
# - 4GB RAM
# - 2 CPUs

# Limpiar Docker
docker system prune -a

# Reducir caché
# En .env: CACHE_MAX_SIZE=50
```

---

## TIMELINE DE DESARROLLO

| Fase | Tiempo | Descripción |
|------|--------|-------------|
| Fase 0 | 1h | Setup Docker + XQuartz |
| Fase 1 | 2-3h | Base de datos + 100 productos |
| Fase 2 | 2-3h | Lector barras + simulador |
| Fase 3 | 2-3h | Cliente Claude API |
| Fase 4 | 3-4h | Interfaz gráfica |
| Fase 5 | 2h | Integración + testing |
| Fase 6 | 1-2h | Documentación |

**Total**: 13-18 horas

---

## CRITERIOS DE ÉXITO

- ✅ Tiempo de respuesta < 2s tras escanear
- ✅ Recomendaciones contextualmente relevantes
- ✅ UI fluida sin bloqueos
- ✅ Consumo memoria < 500MB
- ✅ Caché funcionando (hit rate > 60%)
- ✅ Tests con cobertura > 80%
- ✅ Funciona en Mac y RPi

---

## RECURSOS ADICIONALES

- **Anthropic API Docs**: https://docs.anthropic.com/
- **Docker Compose**: https://docs.docker.com/compose/
- **XQuartz**: https://www.xquartz.org/
- **tkinter**: https://docs.python.org/3/library/tkinter.html
- **SQLite**: https://www.sqlite.org/docs.html

---

## PRÓXIMOS PASOS

1. **Empezar con Fase 0**: Setup Docker
2. **Validar GUI funciona**: Crear ventana tkinter básica
3. **Implementar Fase 1**: Base de datos + productos
4. **Continuar secuencialmente** hasta Fase 5
5. **Testing exhaustivo** en Mac
6. **Deployment** en Raspberry Pi

---

**¿Listo para empezar la implementación?**

El siguiente paso sería crear todos los archivos de la Fase 0 (Docker) y validar que la GUI funciona correctamente en tu Mac.
