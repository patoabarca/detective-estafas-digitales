# Dockerfile para ejecución segura y aislada de Detective de Estafas Digitales
# Soporta tanto el motor CLI (scripts/worker.py) como la mini aplicación web (Streamlit + OCR + PDF).

FROM python:3.13-slim

# Metadatos del contenedor
LABEL maintainer="Diplomatura en Inteligencia Artificial"
LABEL description="Contenedor de ejecución aislada para Detective de Estafas Digitales (CLI + Web + OCR + PDF)"
LABEL security.network="none"

# Variables de entorno para ejecución segura, sin buffers y configuración de Streamlit
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Instalar Tesseract OCR y paquete de idioma español para análisis local de capturas
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-spa \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# Crear usuario sin privilegios y estructura de carpetas (incluyendo /app/output para exportar informes al host)
RUN useradd -m -u 10001 -s /usr/sbin/nologin auditor && \
    mkdir -p /app/config /app/scripts /app/web /app/examples /app/tests /app/.agents /app/output && \
    chown -R auditor:auditor /app

WORKDIR /app

# Instalar dependencias Python primero para aprovechar la caché de capas de Docker
COPY --chown=auditor:auditor requirements.txt requirements-web.txt /app/
RUN pip install --no-cache-dir -r requirements-web.txt

# Copiar los componentes de la aplicación
COPY --chown=auditor:auditor config/ /app/config/
COPY --chown=auditor:auditor scripts/ /app/scripts/
COPY --chown=auditor:auditor web/ /app/web/
COPY --chown=auditor:auditor examples/ /app/examples/
COPY --chown=auditor:auditor tests/ /app/tests/
COPY --chown=auditor:auditor .agents/ /app/.agents/
COPY --chown=auditor:auditor app.py /app/app.py

# Cambiar a usuario no root
USER auditor

EXPOSE 8501

# Punto de entrada por defecto: ejecuta el motor CLI esperando entrada por STDIN.
# También permite ejecutar la web (sobreescribiendo con `--entrypoint streamlit` o `python -m streamlit run app.py`)
# o exportar informes a /app/output montando un volumen desde el anfitrión.
ENTRYPOINT ["python", "scripts/worker.py"]
CMD ["--stdin"]
