#!/bin/sh
set -e

# Wait for the database to be ready (useful since Postgres container
# may take a moment to accept connections even after it "starts")
echo "Waiting for database..."
while ! python -c "
import socket, os
host = os.environ.get('DB_HOST', 'db')
port = int(os.environ.get('DB_PORT', 5432))
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    s.connect((host, port))
    s.close()
except Exception:
    exit(1)
"; do
  sleep 0.5
done
echo "Database is up."


#sleep infinity

######THIS SECTION IS DISABLED DURING DEVELOPMENT######
# Run migrations automatically on container start
python manage.py migrate --noinput

# Collect static files (safe to run every time; skip in dev if you want faster startup)
if [ "$DJANGO_COLLECTSTATIC" = "1" ]; then
  python manage.py collectstatic --noinput
fi

# Hand off to whatever CMD was passed (runserver in dev, gunicorn in prod)
exec "$@"