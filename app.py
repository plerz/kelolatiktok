import os, secrets, sqlite3, mimetypes, json
from datetime import datetime
from urllib.parse import urlencode
import requests
from flask import Flask, render_template, redirect, request, session, url_for, flash, send_from_directory

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
USE_POSTGRES = DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("postgres://")
DB = os.environ.get("DATABASE_PATH", "kelolatiktok.db")
if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras

CLIENT_KEY = os.environ.get("TIKTOK_CLIENT_KEY", "")
CLIENT_SECRET = os.environ.get("TIKTOK_CLIENT_SECRET", "")
REDIRECT_URI = os.environ.get(
    "TIKTOK_REDIRECT_URI",
    "https://tiktok.islammoderat.my.id/auth/tiktok/callback"
)
SCOPES = os.environ.get("TIKTOK_SCOPES", "user.info.basic,video.publish")

AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
USER_URL = "https://open.tiktokapis.com/v2/user/info/"
CREATOR_URL = "https://open.tiktokapis.com/v2/post/publish/creator_info/query/"
DIRECT_POST_INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
POST_STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"

# One-chunk implementation. TikTok allows chunks up to 64 MB.
MAX_UPLOAD_BYTES = 64 * 1024 * 1024
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES + (2 * 1024 * 1024)

VERIFY_FILENAME = "tiktok8X1qCm95yvCX8YUCrVKwJVg1gjLQxAqB.txt"

class PGCompat:
    def __init__(self, conn):
        self.conn, self.cur = conn, None
    def execute(self, sql, params=()):
        self.cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        self.cur.execute(sql.replace("?", "%s"), params)
        return self
    def fetchone(self): return self.cur.fetchone()
    def fetchall(self): return self.cur.fetchall()
    def commit(self): self.conn.commit()
    def close(self):
        if self.cur: self.cur.close()
        self.conn.close()

def db():
    if USE_POSTGRES:
        return PGCompat(psycopg2.connect(DATABASE_URL))
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = db()
    c.execute("""CREATE TABLE IF NOT EXISTS accounts(
        open_id TEXT PRIMARY KEY,
        display_name TEXT,
        avatar_url TEXT,
        access_token TEXT,
        refresh_token TEXT,
        scope TEXT,
        expires_in INTEGER,
        connected_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS publish_jobs(
        publish_id TEXT PRIMARY KEY,
        open_id TEXT NOT NULL,
        caption TEXT,
        privacy_level TEXT,
        status TEXT,
        created_at TEXT,
        last_response TEXT
    )""")
    c.commit()
    c.close()

@app.before_request
def _init():
    init_db()

def get_account(open_id):
    c = db()
    a = c.execute("SELECT * FROM accounts WHERE open_id=?", (open_id,)).fetchone()
    c.close()
    return a

def api_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=UTF-8"
    }

def get_creator_info(account):
    try:
        r = requests.post(
            CREATOR_URL,
            headers=api_headers(account["access_token"]),
            timeout=30
        )
        data = r.json()
        return r, data
    except Exception as e:
        return None, {"data": {}, "error": {"code": "network_error", "message": str(e)}}

@app.get("/")
def dashboard():
    c = db()
    accounts = c.execute(
        "SELECT open_id,display_name,avatar_url,scope,connected_at FROM accounts ORDER BY connected_at DESC"
    ).fetchall()
    c.close()
    return render_template("dashboard.html", accounts=accounts)

@app.get("/auth/tiktok/login")
def tiktok_login():
    if not CLIENT_KEY or not CLIENT_SECRET:
        flash("TikTok credentials belum dipasang di Render Environment Variables.", "error")
        return redirect(url_for("dashboard"))
    state = secrets.token_urlsafe(32)
    session["oauth_state"] = state
    params = {
        "client_key": CLIENT_KEY,
        "response_type": "code",
        "scope": SCOPES,
        "redirect_uri": REDIRECT_URI,
        "state": state,
        "disable_auto_auth": "1"
    }
    return redirect(AUTH_URL + "?" + urlencode(params))

@app.get("/auth/tiktok/callback")
def tiktok_callback():
    if request.args.get("error"):
        flash("TikTok authorization gagal: " + request.args.get("error_description", request.args["error"]), "error")
        return redirect(url_for("dashboard"))

    if request.args.get("state") != session.pop("oauth_state", None):
        flash("OAuth state tidak cocok. Hubungkan akun lagi.", "error")
        return redirect(url_for("dashboard"))

    code = request.args.get("code", "")
    try:
        r = requests.post(TOKEN_URL, data={
            "client_key": CLIENT_KEY,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI
        }, timeout=30)
        data = r.json()
    except Exception as e:
        flash("Token exchange gagal: " + str(e), "error")
        return redirect(url_for("dashboard"))

    if not r.ok or "access_token" not in data:
        flash("Token exchange gagal: " + str(data), "error")
        return redirect(url_for("dashboard"))

    token = data["access_token"]
    open_id = data.get("open_id", "")
    try:
        ur = requests.get(
            USER_URL,
            params={"fields": "open_id,display_name,avatar_url"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30
        )
        user = ur.json().get("data", {}).get("user", {})
    except Exception as e:
        flash("Gagal membaca profil TikTok: " + str(e), "error")
        return redirect(url_for("dashboard"))

    c = db()
    account_values = (open_id, user.get("display_name", "TikTok account"),
        user.get("avatar_url", ""), token, data.get("refresh_token", ""),
        data.get("scope", ""), data.get("expires_in", 0), datetime.utcnow().isoformat())
    if USE_POSTGRES:
        c.execute("""INSERT INTO accounts(
            open_id,display_name,avatar_url,access_token,refresh_token,scope,expires_in,connected_at
        ) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT (open_id) DO UPDATE SET
            display_name=EXCLUDED.display_name, avatar_url=EXCLUDED.avatar_url,
            access_token=EXCLUDED.access_token, refresh_token=EXCLUDED.refresh_token,
            scope=EXCLUDED.scope, expires_in=EXCLUDED.expires_in,
            connected_at=EXCLUDED.connected_at""", account_values)
    else:
        c.execute("""INSERT OR REPLACE INTO accounts(
            open_id,display_name,avatar_url,access_token,refresh_token,scope,expires_in,connected_at
        ) VALUES(?,?,?,?,?,?,?,?)""", account_values)
    c.commit()
    c.close()
    flash("TikTok account berhasil terhubung.", "success")
    return redirect(url_for("dashboard"))

@app.route("/create-post/<open_id>", methods=["GET", "POST"])
def create_post(open_id):
    account = get_account(open_id)
    if not account:
        flash("Akun TikTok tidak ditemukan.", "error")
        return redirect(url_for("dashboard"))

    r, info = get_creator_info(account)
    creator = info.get("data", {})
    api_error = info.get("error", {})

    if r is None or not r.ok or api_error.get("code") not in ("ok", "", None):
        return render_template(
            "create_post.html",
            account=account, creator=creator, api_error=api_error,
            max_upload_mb=64
        )

    if request.method == "GET":
        return render_template(
            "create_post.html",
            account=account, creator=creator, api_error=api_error,
            max_upload_mb=64
        )

    video = request.files.get("video")
    caption = request.form.get("caption", "").strip()
    privacy = request.form.get("privacy_level", "").strip()
    consent = request.form.get("consent") == "yes"

    if not consent:
        flash("Centang persetujuan sebelum mengirim video ke TikTok.", "error")
        return redirect(url_for("create_post", open_id=open_id))

    options = creator.get("privacy_level_options", [])
    if not privacy or privacy not in options:
        flash("Pilih privacy yang tersedia untuk akun ini.", "error")
        return redirect(url_for("create_post", open_id=open_id))

    if not video or not video.filename:
        flash("Pilih file video.", "error")
        return redirect(url_for("create_post", open_id=open_id))

    ext = os.path.splitext(video.filename.lower())[1]
    if ext not in {".mp4", ".mov", ".webm"}:
        flash("Format harus MP4, MOV, atau WEBM.", "error")
        return redirect(url_for("create_post", open_id=open_id))

    video_bytes = video.read()
    size = len(video_bytes)
    if size == 0:
        flash("File video kosong.", "error")
        return redirect(url_for("create_post", open_id=open_id))
    if size > MAX_UPLOAD_BYTES:
        flash("V2 ini membatasi upload maksimum 64 MB.", "error")
        return redirect(url_for("create_post", open_id=open_id))

    # User controls. If TikTok says an interaction is unavailable,
    # force it disabled regardless of submitted form values.
    allow_comment = request.form.get("allow_comment") == "yes"
    allow_duet = request.form.get("allow_duet") == "yes"
    allow_stitch = request.form.get("allow_stitch") == "yes"

    disable_comment = True if creator.get("comment_disabled") else not allow_comment
    disable_duet = True if creator.get("duet_disabled") else not allow_duet
    disable_stitch = True if creator.get("stitch_disabled") else not allow_stitch

    payload = {
        "post_info": {
            "title": caption,
            "privacy_level": privacy,
            "disable_comment": disable_comment,
            "disable_duet": disable_duet,
            "disable_stitch": disable_stitch
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": size,
            "chunk_size": size,
            "total_chunk_count": 1
        }
    }

    try:
        ir = requests.post(
            DIRECT_POST_INIT_URL,
            headers=api_headers(account["access_token"]),
            json=payload,
            timeout=60
        )
        init = ir.json()
    except Exception as e:
        flash("Direct Post init gagal: " + str(e), "error")
        return redirect(url_for("create_post", open_id=open_id))

    err = init.get("error", {})
    data = init.get("data", {})
    if not ir.ok or err.get("code") not in ("ok", "", None) or not data.get("upload_url"):
        flash("TikTok menolak Direct Post: " + json.dumps(init, ensure_ascii=False), "error")
        return redirect(url_for("create_post", open_id=open_id))

    upload_url = data["upload_url"]
    publish_id = data.get("publish_id", "")
    mime = mimetypes.guess_type(video.filename)[0] or "video/mp4"
    if mime not in {"video/mp4", "video/quicktime", "video/webm"}:
        mime = "video/mp4"

    try:
        up = requests.put(
            upload_url,
            headers={
                "Content-Type": mime,
                "Content-Length": str(size),
                "Content-Range": f"bytes 0-{size-1}/{size}"
            },
            data=video_bytes,
            timeout=240
        )
    except Exception as e:
        flash("Upload ke server TikTok gagal: " + str(e), "error")
        return redirect(url_for("create_post", open_id=open_id))

    if not up.ok:
        flash(f"Upload TikTok gagal HTTP {up.status_code}: {up.text[:500]}", "error")
        return redirect(url_for("create_post", open_id=open_id))

    c = db()
    job_values = (publish_id, open_id, caption, privacy, "PROCESSING",
        datetime.utcnow().isoformat(), json.dumps(init, ensure_ascii=False))
    if USE_POSTGRES:
        c.execute("""INSERT INTO publish_jobs(
            publish_id,open_id,caption,privacy_level,status,created_at,last_response
        ) VALUES(?,?,?,?,?,?,?) ON CONFLICT (publish_id) DO UPDATE SET
            open_id=EXCLUDED.open_id, caption=EXCLUDED.caption,
            privacy_level=EXCLUDED.privacy_level, status=EXCLUDED.status,
            created_at=EXCLUDED.created_at, last_response=EXCLUDED.last_response""", job_values)
    else:
        c.execute("""INSERT OR REPLACE INTO publish_jobs(
            publish_id,open_id,caption,privacy_level,status,created_at,last_response
        ) VALUES(?,?,?,?,?,?,?)""", job_values)
    c.commit()
    c.close()

    flash("Video sudah dikirim ke TikTok dan sedang diproses.", "success")
    return redirect(url_for("publish_status", open_id=open_id, publish_id=publish_id))

@app.get("/publish-status/<open_id>/<path:publish_id>")
def publish_status(open_id, publish_id):
    account = get_account(open_id)
    if not account:
        flash("Akun TikTok tidak ditemukan.", "error")
        return redirect(url_for("dashboard"))

    try:
        r = requests.post(
            POST_STATUS_URL,
            headers=api_headers(account["access_token"]),
            json={"publish_id": publish_id},
            timeout=30
        )
        result = r.json()
    except Exception as e:
        result = {"data": {}, "error": {"code": "network_error", "message": str(e)}}

    status = result.get("data", {}).get("status", "UNKNOWN")
    c = db()
    c.execute(
        "UPDATE publish_jobs SET status=?,last_response=? WHERE publish_id=?",
        (status, json.dumps(result, ensure_ascii=False), publish_id)
    )
    c.commit()
    c.close()
    return render_template(
        "publish_status.html",
        account=account, publish_id=publish_id,
        status=status, result=result
    )

@app.get(f"/{VERIFY_FILENAME}")
def verify_file():
    return send_from_directory(app.root_path, VERIFY_FILENAME, mimetype="text/plain")

@app.get("/health")
def health():
    return {"status": "ok", "version": "KelolaTiktok V2 Persistent",
            "database": "postgresql" if USE_POSTGRES else "sqlite"}

@app.errorhandler(413)
def too_large(_):
    return "File terlalu besar. Maksimum 64 MB untuk KelolaTiktok V2.", 413

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
