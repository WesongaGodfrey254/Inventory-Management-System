Inventory & Sales Management (Flask)

1. Create virtualenv & install
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt

2. Choose a database
   PostgreSQL is used for deployment. Set DATABASE_URL in .env:

     DATABASE_URL=postgresql://mysales_user:your-password@localhost:5432/mysales

   The app also accepts the legacy `postgres://` scheme used by some hosts and
   rewrites it automatically. If DATABASE_URL is not set, the app falls back to
   the local SQLite file instance/inventory.db for development.

   To create a local PostgreSQL database:

     createdb mysales
     createuser mysales_user --pwprompt
     psql -c "GRANT ALL PRIVILEGES ON DATABASE mysales TO mysales_user;"

3. Initialize the schema
   Local development (also creates tables automatically):

     python run.py

   Deployment (run once per release, before starting the web workers):

     flask --app wsgi init-db

   (Optional) If you prefer Flask-Migrate migrations instead:
   export FLASK_APP=run.py
   rm -rf migrations
   flask db init
   flask db migrate -m "Initial migrate"
   flask db upgrade

   (If using Windows set FLASK_APP differently: set FLASK_APP=run.py)

4. Create an admin user (simple method)
   from app import create_app, db
   app = create_app()
   with app.app_context():
       from app.models import User
       u = User(username="admin", shop_name="My Shop", is_admin=True)
       u.set_password("password")
       db.session.add(u)
       db.session.commit()

   You can also register through http://127.0.0.1:5000/register.
   The shop name entered during registration is shown on the dashboard and is
   used on every customer receipt.

5. Run
   Development:
     python run.py
     Open http://127.0.0.1:5000/ and login with the account created.

   Production (gunicorn):
     gunicorn wsgi:app
     Platforms that read a Procfile can use the bundled one as-is.

   A start command alone is not enough on a fresh database: run
   `flask --app wsgi init-db` as the release/build step so the tables and the
   latest columns exist. The command is safe to run on every deploy.

6. Shop name on notifications
   Every receipt email is branded with the shop that recorded the sale:
   the subject, From display name, body and footer all use the shop name.
   Logged-in users can change it under "Shop settings" in the navigation bar.
   Accounts without a shop name fall back to the username, so set the shop
   name before sending receipts.

7. Email receipts (optional)
   Sale receipts are emailed to the customer's address when SMTP is configured.
   Create your local environment file and fill in your SMTP details:

   cp .env.example .env
   nano .env

   The app loads .env automatically through python-dotenv. Example values:

   MAIL_SERVER=smtp.gmail.com
   MAIL_PORT=587
   MAIL_USE_TLS=true
   MAIL_USE_SSL=false
   MAIL_USERNAME=your-address@gmail.com
   MAIL_PASSWORD=your-app-password
   MAIL_DEFAULT_SENDER=your-address@gmail.com

   For Gmail, use an App Password, not your normal account password.
   If MAIL_SERVER is empty, the sale is still saved and the skipped
   notification is written to the application log.

   Settings are read once at startup: after editing .env, restart the app.
   On startup the console prints "Receipt emails enabled..." or a warning
   that receipts are disabled. Failed sends are retried up to 3 times and
   the exact reason is shown on screen. Details are also written to
   instance/app.log. If a receipt fails to send, use the "Resend receipt"
   button on the Sales page once SMTP is working.

   When a receipt was accepted by the mail server but the customer says it did
   not arrive, ask them to check their spam folder and confirm the address.
   A "receipt emailed" log line means Gmail accepted the message; delivery
   after that point is handled by the recipient's mail provider.

8. Deployed on Vercel
   Production URL: https://inventory-management-system-wesongagodfrey254.vercel.app

   Repository: https://github.com/WesongaGodfrey254/Inventory-Management-System

   The project is linked to GitHub: every push to `main` triggers a new
   production deployment. Vercel's zero-config Flask runtime uses `wsgi.py`.
   Preview deployments stay behind Vercel Authentication; only the production
   domain is public.

   Production environment variables (set in the Vercel dashboard, never
   committed):
   - DATABASE_URL: Neon PostgreSQL (provisioned through the Vercel marketplace)
   - SECRET_KEY, ADMIN_PASSWORD, MAIL_PASSWORD: stored as Vercel *Secrets*
   - ADMIN_USERNAME, ADMIN_SHOP_NAME, MAIL_* and LOG_TO_FILE: stored as Config
   - LOG_TO_FILE=0 because the serverless filesystem is read-only

   After changing the schema or the admin credentials, run the bootstrap once
   against the unpooled database URL:

     DATABASE_URL=... ADMIN_USERNAME=admin ADMIN_PASSWORD=... \
       ADMIN_SHOP_NAME="My Shop" flask --app wsgi init-db

   The command is idempotent and refreshes the admin password.

Notes:
- The dashboard shows all-time sales count, all-time sales value and product count.
  These totals refresh automatically every 3 seconds and are scoped to the logged-in shop.
- Each registered account has its own shop inventory: products, sales, customers,
  dashboard totals and reports are only visible to that account.
- Production uses PostgreSQL through psycopg 3. Keep the database URL in the
  host's environment variables, never in source control.
- Security: global CSRF protection, secure/HttpOnly/SameSite session cookies,
  HSTS, CSP and other hardened headers, plus `/healthz` for uptime checks.
- Add role-based checks, tests and more reports as next steps.
