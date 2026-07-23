FROM ubuntu:26.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    APP_ENV=production \
    DIPLOMAS_DATA_DIR=/app/data

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        libreoffice-core \
        libreoffice-writer \
        fontconfig \
        fonts-crosextra-caladea \
        fonts-crosextra-carlito \
        fonts-dejavu-core \
        fonts-liberation \
    && fc-cache -f \
    && soffice --headless --version \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY app.py /app/app.py
COPY static /app/static
COPY DIPLOMA_VERSION_FINAL_CORREGIDA.docx /app/DIPLOMA_VERSION_FINAL_CORREGIDA.docx

RUN mkdir -p /app/data/uploads /app/data/generated

EXPOSE 8000

CMD ["python3", "app.py"]
