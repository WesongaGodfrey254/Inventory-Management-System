"""WSGI entry point used by production servers (gunicorn, uWSGI, etc.).

Run locally with the development server via ``python run.py``; in production
start the app with::

    gunicorn wsgi:app
"""

from app import create_app

app = create_app()
