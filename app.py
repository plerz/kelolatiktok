import os, secrets, sqlite3
from datetime import datetime
from urllib.parse import urlencode
import requests
from flask import Flask, render_template, redirect, request, session, url_for, flash, send_from_directory

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32))
DB = os.environ.get('DATABASE_PATH', 'kelolatiktok.db')
CLIENT_KEY = os.environ.get('TIKTOK_CLIENT_KEY','')
CLIENT_SECRET = os.environ.get('TIKTOK_CLIENT_SECRET','')
REDIRECT_URI = os.environ.get('TIKTOK_REDIRECT_URI','https://tiktok.islammoderat.my.id/auth/tiktok/callback')
SCOPES = os.environ.get('TIKTOK_SCOPES','user.info.basic,video.publish')

AUTH_URL='https://www.tiktok.com/v2/auth/authorize/'
TOKEN_URL='https://open.tiktokapis.com/v2/oauth/token/'
USER_URL='https://open.tiktokapis.com/v2/user/info/'
CREATOR_URL='https://open.tiktokapis.com/v2/post/publish/creator_info/query/'

def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init_db():
    c=db(); c.execute('''CREATE TABLE IF NOT EXISTS accounts(
      open_id TEXT PRIMARY KEY, display_name TEXT, avatar_url TEXT, access_token TEXT,
      refresh_token TEXT, scope TEXT, expires_in INTEGER, connected_at TEXT)'''); c.commit(); c.close()

@app.before_request
def _init(): init_db()

@app.get('/')
def dashboard():
    c=db(); accounts=c.execute('SELECT open_id,display_name,avatar_url,scope,connected_at FROM accounts ORDER BY connected_at DESC').fetchall(); c.close()
    return render_template('dashboard.html', accounts=accounts)

@app.get('/auth/tiktok/login')
def tiktok_login():
    if not CLIENT_KEY or not CLIENT_SECRET:
        flash('TikTok Sandbox credentials belum dipasang di Environment Variables.', 'error'); return redirect(url_for('dashboard'))
    state=secrets.token_urlsafe(32); session['oauth_state']=state
    params={'client_key':CLIENT_KEY,'response_type':'code','scope':SCOPES,'redirect_uri':REDIRECT_URI,'state':state,'disable_auto_auth':'1'}
    return redirect(AUTH_URL+'?'+urlencode(params))

@app.get('/auth/tiktok/callback')
def tiktok_callback():
    if request.args.get('error'):
        flash('TikTok authorization gagal: '+request.args.get('error_description',request.args['error']), 'error'); return redirect(url_for('dashboard'))
    if not request.args.get('state') or request.args.get('state') != session.pop('oauth_state',None):
        flash('OAuth state tidak cocok. Silakan Connect TikTok lagi.', 'error'); return redirect(url_for('dashboard'))
    code=request.args.get('code')
    r=requests.post(TOKEN_URL, data={'client_key':CLIENT_KEY,'client_secret':CLIENT_SECRET,'code':code,'grant_type':'authorization_code','redirect_uri':REDIRECT_URI}, timeout=30)
    data=r.json()
    if not r.ok or 'access_token' not in data:
        flash('Token exchange gagal: '+str(data), 'error'); return redirect(url_for('dashboard'))
    token=data['access_token']; open_id=data.get('open_id','')
    u=requests.get(USER_URL, params={'fields':'open_id,display_name,avatar_url'}, headers={'Authorization':f'Bearer {token}'}, timeout=30).json()
    user=u.get('data',{}).get('user',{})
    c=db(); c.execute('''INSERT OR REPLACE INTO accounts(open_id,display_name,avatar_url,access_token,refresh_token,scope,expires_in,connected_at) VALUES(?,?,?,?,?,?,?,?)''',
      (open_id,user.get('display_name','TikTok account'),user.get('avatar_url',''),token,data.get('refresh_token',''),data.get('scope',''),data.get('expires_in',0),datetime.utcnow().isoformat()))
    c.commit(); c.close(); flash('TikTok account berhasil terhubung.', 'success'); return redirect(url_for('dashboard'))

@app.get('/create-post/<open_id>')
def create_post(open_id):
    c=db(); a=c.execute('SELECT * FROM accounts WHERE open_id=?',(open_id,)).fetchone(); c.close()
    if not a: return redirect(url_for('dashboard'))
    r=requests.post(CREATOR_URL, headers={'Authorization':f"Bearer {a['access_token']}",'Content-Type':'application/json; charset=UTF-8'}, timeout=30)
    info=r.json(); return render_template('create_post.html', account=a, creator=info.get('data',{}), api_error=info.get('error',{}))

@app.get('/tiktok8X1qCm95yvCX8YUCrVKwJVg1gjLQxAqB.txt')
def tiktok_url_verification():
    return send_from_directory(
        app.root_path,
        'tiktok8X1qCm95yvCX8YUCrVKwJVg1gjLQxAqB.txt',
        mimetype='text/plain'
    )

@app.get('/health')
def health(): return {'status':'ok'}

if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.environ.get('PORT',5000)),debug=True)
