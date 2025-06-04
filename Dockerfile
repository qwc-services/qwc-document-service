FROM alpine:3.21

ENV SERVICE_UID=33
ENV SERVICE_GID=33
# http://uwsgi-docs.readthedocs.io/en/latest/Options.html#buffer-size
ENV UWSGI_PROCESSES=1
ENV UWSGI_THREADS=4
ENV PGSERVICEFILE="/srv/pg_service.conf"

STOPSIGNAL SIGINT

WORKDIR /srv/qwc_service
ADD pyproject.toml uv.lock ./
ADD libs.txt /srv/qwc_service/libs.txt

COPY --from=ghcr.io/astral-sh/uv:alpine3.20 /usr/local/bin/uv /usr/local/bin/uvx /bin/

RUN \
    apk add --no-cache --update shadow python3 py3-pip py3-gunicorn && \
    apk add --no-cache --update --virtual runtime-deps postgresql-libs openjdk21-jdk openjdk21-jre ttf-dejavu && \
    apk add --no-cache --update --virtual build-deps postgresql-dev g++ python3-dev && \
    uv sync --frozen && \
    uv cache clean && \
    mkdir /srv/qwc_service/libs && \
    mkdir /srv/qwc_service/fonts && \
    while IFS= read -r url; do if [ -n "$url" ]; then wget -P /srv/qwc_service/libs "$url"; fi; done < /srv/qwc_service/libs.txt && \
    apk del build-deps

ADD src /srv/qwc_service/
ADD entrypoint.sh /entrypoint.sh

ENV LD_LIBRARY_PATH=/usr/lib/jvm/java-21-openjdk/lib/server
ENV SERVICE_MOUNTPOINT=/api/v1/document

ENTRYPOINT ["sh", "/entrypoint.sh"]
