# Cómo arranca en Railway. $PORT lo asigna Railway en cada despliegue.
# En local NO se usa esto: gunicorn no corre en Windows, ahí se usa
# `python backend/wsgi.py`, que levanta el servidor de desarrollo.
web: gunicorn --chdir backend wsgi:app --bind 0.0.0.0:$PORT --workers 2 --timeout 60 --access-logfile -
