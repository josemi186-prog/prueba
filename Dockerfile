FROM python:3.12-slim-bookworm

ARG LIBREOFFICE_VERSION=26.2.3

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    APP_ENV=production \
    DIPLOMAS_DATA_DIR=/app/data

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        fonts-dejavu-core \
        fonts-liberation \
        libxinerama1 \
        libxrender1 \
        libxt6 \
    && curl -fsSL \
        "https://download.documentfoundation.org/libreoffice/stable/${LIBREOFFICE_VERSION}/deb/x86_64/LibreOffice_${LIBREOFFICE_VERSION}_Linux_x86-64_deb.tar.gz" \
        -o /tmp/libreoffice.tar.gz \
    && mkdir -p /tmp/libreoffice \
    && tar -xzf /tmp/libreoffice.tar.gz -C /tmp/libreoffice --strip-components=1 \
    && apt-get install -y --no-install-recommends /tmp/libreoffice/DEBS/*.deb \
    && ln -sf "$(find /opt -type f -path '*/program/soffice' -print -quit)" /usr/local/bin/soffice \
    && soffice --headless --version \
    && rm -rf /tmp/libreoffice /tmp/libreoffice.tar.gz \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY app.py /app/app.py
COPY static /app/static
COPY DIPLOMA_VERSION_FINAL_CORREGIDA.docx /app/DIPLOMA_VERSION_FINAL_CORREGIDA.docx

RUN mkdir -p /app/data/uploads /app/data/generated

EXPOSE 8000

CMD ["python", "app.py"]
