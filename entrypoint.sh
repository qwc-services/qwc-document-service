#!/bin/sh

cat > /tmp/gunicorn.conf.py <<EOF
user = ${SERVICE_UID:-None}
group = ${SERVICE_GID:-None}
EOF

HOME=/tmp gunicorn \
    --chdir /srv/qwc_service \
    --bind :9090 \
    --workers $UWSGI_PROCESSES \
    --threads $UWSGI_THREADS \
    --worker-class gthread \
    --pythonpath /srv/qwc_service/.venv/lib/python*/site-packages \
    --access-logfile - \
    -c /tmp/gunicorn.conf.py \
    server:app
