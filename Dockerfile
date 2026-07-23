FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    APP_ENV=production \
    DIPLOMAS_DATA_DIR=/app/data

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libreoffice-core \
        libreoffice-writer \
        fonts-dejavu-core \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY app.py /app/app.py
COPY static /app/static
COPY DIPLOMA_VERSION_FINAL_CORREGIDA.docx /app/DIPLOMA_VERSION_FINAL_CORREGIDA.docx

RUN mkdir -p /app/data/uploads /app/data/generated

EXPOSE 8000

CMD ["python", "app.py"]
