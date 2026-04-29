#!/bin/sh
set -e

echo "Apply migrations..."
python manage.py migrate --noinput

echo "Collect static..."
python manage.py collectstatic --noinput || true

if [ "$DJANGO_CREATE_SUPERUSER" = "true" ]; then
  echo "Create superuser..."
  python manage.py createsuperuser --noinput || true
fi

echo "Starting gunicorn..."
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000
