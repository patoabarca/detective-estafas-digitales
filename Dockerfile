# Dockerfile para ejecución segura y aislada de Detective de Estafas Digitales
# Diseñado bajo el principio de menor privilegio y sistema de archivos de solo lectura.

FROM python:3.13-slim

# Metadatos del contenedor
LABEL maintainer="Diplomatura en Inteligencia Artificial"
LABEL description="Contenedor de ejecución aislada para Detective de Estafas Digitales"
LABEL security.network="none"

# Variables de entorno para ejecución segura y sin buffers
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Crear usuario sin privilegios y estructura de carpetas
RUN useradd -m -u 10001 -s /usr/sbin/nologin auditor && \
    mkdir -p /app/config /app/scripts /app/examples && \
    chown -R auditor:auditor /app

WORKDIR /app

# Copiar únicamente los componentes estrictamente necesarios
COPY --chown=auditor:auditor config/ /app/config/
COPY --chown=auditor:auditor scripts/ /app/scripts/
COPY --chown=auditor:auditor examples/ /app/examples/

# Cambiar a usuario no root
USER auditor

# Punto de entrada seguro: ejecuta worker.py esperando entrada por STDIN de forma predeterminada
ENTRYPOINT ["python", "scripts/worker.py"]
CMD ["--stdin"]
