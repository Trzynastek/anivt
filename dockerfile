FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    ffmpeg \
    fonts-roboto

RUN pip install \
    "flask[async]" \
    flask-cors \
    feedparser \
    asyncio \
    python-ffmpeg \
    libtorrent \
    requests \
    unidecode \
    bencodepy

WORKDIR /anivt/

COPY public/ /anivt/public/
COPY config.json /anivt/config.json
COPY server.py /anivt/server.py

RUN rm -rf  /anivt/public/mp4/*
RUN mkdir -p /anivt/public/mp4
RUN mkdir /anivt/mkv
RUN mkdir /anivt/subtitles

EXPOSE 7980

CMD ["python", "server.py"]