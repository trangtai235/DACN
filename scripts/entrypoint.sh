#!/bin/sh
set -eu
python manage.py wait_for_db
if [ "${1:-web}" = "worker" ]; then
  exec celery -A config worker --loglevel=info --concurrency=2
fi
python manage.py migrate --noinput
python manage.py seed_demo
python manage.py collectstatic --noinput
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 120 --access-logfile -
