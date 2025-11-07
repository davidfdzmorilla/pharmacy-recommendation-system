FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

# Instalar dependencias del sistema (similares a Raspberry Pi OS)
RUN apt-get update && apt-get install -y \
    python3-tk \
    libevdev-dev \
    linux-libc-dev \
    build-essential \
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
