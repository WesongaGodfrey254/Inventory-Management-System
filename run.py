import os

from app import create_app
from app.schema import upgrade_schema

app = create_app()

# Create/upgrade the tables on first run. In production the same routine runs
# once per deployment via `flask --app wsgi init-db` (see README).
with app.app_context():
    upgrade_schema()

if __name__ == "__main__":
    # Development server only. Production deployments use gunicorn (wsgi:app).
    debug = os.environ.get("FLASK_DEBUG", "0").strip().lower() in ("1", "true", "yes", "on")
    app.run(debug=debug)
