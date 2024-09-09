FROM sourcepole/qwc-uwsgi-base:alpine-v2023.10.26

ADD requirements.txt /srv/qwc_service/requirements.txt
ADD libs.txt /srv/qwc_service/libs.txt

RUN \
    apk add --no-cache --update --virtual runtime-deps postgresql-libs openjdk17-jdk openjdk17-jre ttf-dejavu && \
    apk add --no-cache --update --virtual build-deps postgresql-dev g++ python3-dev && \
    pip3 install --no-cache-dir -r /srv/qwc_service/requirements.txt && \
    mkdir /srv/qwc_service/libs && \
    mkdir /srv/qwc_service/fonts && \
    while IFS= read -r url; do if [ -n "$url" ]; then wget -P /srv/qwc_service/libs "$url"; fi; done < /srv/qwc_service/libs.txt && \
    apk del build-deps

ADD src /srv/qwc_service/

ENV LD_LIBRARY_PATH=/usr/lib/jvm/java-17-openjdk/lib/server
ENV SERVICE_MOUNTPOINT=/api/v1/document
