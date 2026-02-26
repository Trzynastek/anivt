FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN echo "deb http://deb.debian.org/debian bookworm main non-free-firmware non-free" > /etc/apt/sources.list.d/debian-nonfree.list

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-roboto \
    intel-media-va-driver-non-free \
    libmfx1 \
    libva-drm2 \
    vainfo && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    "flask[async]" \
    flask-cors \
    feedparser \
    asyncio \
    python-ffmpeg \
    libtorrent \
    requests \
    unidecode \
    bencodepy \
    waitress \
    ruamel.yaml \
    "pyjwt[crypto]" \
    colorama \
    rapidfuzz

WORKDIR /anivt/

COPY web/ /anivt/web/
COPY modules/ /anivt/modules/
COPY server.py /anivt/server.py

EXPOSE 7980

CMD ["python", "server.py"]