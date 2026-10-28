# KelolaTikTok — sandbox only

This repository is for the **KelolaTikTok Render sandbox service**, NOT DashboardFYEPE production.

- Domain: https://tiktok.islammoderat.my.id
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app`
- `PUBLIC_BASE_URL=https://tiktok.islammoderat.my.id`
- `TIKTOK_REDIRECT_URI=https://tiktok.islammoderat.my.id/auth/tiktok/callback`
- `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`: credentials for the sandbox TikTok Developer app only
- `FLASK_SECRET_KEY`: stable, sandbox-specific secret
- `DATABASE_URL`: PostgreSQL **sandbox** database, NEVER the production URL
- `SANDBOX_DATABASE_FINGERPRINT`: set to `hostname/database_name` matching sandbox DATABASE_URL (without password). This is an explicit guard against accidental DB reuse; verify the hostname and database are NOT the production database.
- `PHOTO_UPLOAD_DIR`: sandbox-specific directory (default `/tmp/kelolatiktok_photos`)
- `TIKTOK_SCOPES`: approved sandbox scopes

**IMPORTANT:** Configure sandbox environment variables BEFORE deploying. The application intentionally refuses to start if isolation configuration is incomplete. If `SANDBOX_DATABASE_FINGERPRINT` is missing, it will fail closed. Do not copy production credentials, database URL, or secret key. Never commit `.env` secrets.

The production `app.py`, feature modules, and templates have been synced from the supplied DashboardFYEPE archive; sandbox-only files `import_comments.py`, `README_MEDIA_FIX.md`, and sandbox TikTok verification file are preserved. The database is not migrated or copied from production.

Validate first: `python -m compileall -q .`; deploy only to KelolaTikTok sandbox Render service. Test login, vouchers, media, and OAuth with sandbox accounts.
