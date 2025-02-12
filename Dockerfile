FROM sourcepole/qwc-uwsgi-base:alpine-v2025.01.24

WORKDIR /srv/qwc_service
ADD pyproject.toml uv.lock ./
ADD libs.txt /srv/qwc_service/libs.txt

RUN \
    apk add --no-cache --update --virtual runtime-deps postgresql-libs openjdk21-jdk openjdk21-jre ttf-dejavu && \
    apk add --no-cache --update --virtual build-deps postgresql-dev g++ python3-dev && \
    uv sync --frozen && \
    uv cache clean && \
    mkdir /srv/qwc_service/libs && \
    mkdir /srv/qwc_service/fonts && \
    while IFS= read -r url; do if [ -n "$url" ]; then wget -P /srv/qwc_service/libs "$url"; fi; done < /srv/qwc_service/libs.txt && \
    apk del build-deps

ADD src /srv/qwc_service/

ENV LD_LIBRARY_PATH=/usr/lib/jvm/java-21-openjdk/lib/server
ENV SERVICE_MOUNTPOINT=/api/v1/document
# Respawn service after each request
ENV UWSGI_EXTRA="--master --processes 1 --threads 1 --max-requests 1"
