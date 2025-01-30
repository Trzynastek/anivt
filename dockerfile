FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-roboto && \
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
    waitress

WORKDIR /anivt/

COPY public/ /anivt/public/
COPY config.json /anivt/config.json
COPY server.py /anivt/server.py

RUN mkdir -p /anivt/public/mp4 && \
    mkdir /anivt/mkv && \
    mkdir /anivt/subtitles

EXPOSE 7980

CMD ["python", "server.py"]