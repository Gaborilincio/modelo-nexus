FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

# Primero las dependencias, para aprovechar la caché de capas cuando solo cambia el código.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Solo lo que la API necesita en producción. NO se copia datos/crudos (datos personales)
# ni los conjuntos de entrenamiento (entrenamiento.pkl, validacion.pkl, ranking_*.pkl).
COPY app ./app
COPY datos/modelos ./datos/modelos
COPY datos/procesados/metadatos.pkl datos/procesados/*_limpio.csv ./datos/procesados/

RUN useradd --system --no-create-home api && chown -R api /srv
USER api

EXPOSE 8000

# La API carga el modelo y los datos al iniciar: se da margen antes de empezar a comprobar.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=4)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]