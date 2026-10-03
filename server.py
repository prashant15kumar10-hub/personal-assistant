#!/usr/bin/env python3
# Production-oriented server wrapper for the Personal Assistant.
import json, os, time, secrets, hashlib, hmac, logging
from collections import defaultdict, deque
from http.cookies import SimpleCookie
from http.server import ThreadingHTTPServer
from logging.handlers import RotatingFileHandler
import app

BASE=os.path.dirname(os.path.abspath(__file__))
PORT=int(os.environ.get('PORT','8000'))
SESSION_TTL=60*60*12
RATE_WINDOW=60
RATE_LIMIT=int(os.environ.get('RATE_LIMIT','90'))
SESSIONS={}
REQUESTS=defaultdict(deque)
METRICS={'requests':0,'errors':0,'rate_limited':0,'started_at':time.time()}

os.makedirs(os.path.join(BASE,'logs'),exist_ok=True)
logger=logging.getLogger('personal-assistant'); logger.setLevel(logging.INFO)
handler=RotatingFileHandler(os.path.join(BASE,'logs','app.log'),maxBytes=1_000_000,backupCount=3)
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
logger.addHandler(handler); logger.addHandler(logging.StreamHandler())

LOGIN_HTML='''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sign in · Personal Assistant</title><style>
*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;background:linear-gradient(135deg,#171f34,#443aa0 60%,#12817f);font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Arial;color:#172033}.card{width:min(430px,calc(100% - 32px));background:#fff;border-radius:18px;padding:32px;box-shadow:0 28px 70px #0c102650}.logo{width:48px;height:48px;display:grid;place-items:center;border-radius:13px;background:linear-gradient(135deg,#7668eb,#2ab4aa);color:#fff;font-weight:800;margin-bottom:24px}h1{margin:0 0 6px;font-size:27px}p{margin:0 0 24px;color:#667085}.tabs{display:grid;grid-template-columns:1fr 1fr;background:#f1f3f8;padding:4px;border-radius:10px;margin-bottom:18px}.tabs button{border:0;background:transparent;padding:10px;border-radius:7px;font-weight:700;color:#667085}.tabs button.active{background:#fff;color:#5547cc;box-shadow:0 2px 8px #17203312}form{display:grid;gap:12px}label{font-size:13px;font-weight:700}input{width:100%;height:46px;border:1px solid #d7dce5;border-radius:9px;padding:0 12px;font:inherit}button.submit{height:46px;border:0;border-radius:9px;background:#6658d9;color:#fff;font-weight:800;font-size:15px;cursor:pointer}.error{min-height:24px;color:#c73c3c;font-size:13px}.hidden{display:none}.note{margin-top:16px;font-size:12px;color:#7d8493}</style></head><body><main class="card"><div class="logo">PA</div><h1>Welcome back</h1><p>Sign in to your private student workspace.</p><div class="tabs"><button id="loginTab" class="active" onclick="show('login')">Sign in</button><button id="registerTab" onclick="show('register')">Create account</button></div><form id="authForm"><label id="nameField" class="hidden">Name<input id="name" placeholder="Your name"></label><label>Email<input id="email" type="email" required placeholder="you@example.com"></label><label>Password<input id="password" type="password" minlength="8" required placeholder="Minimum 8 characters"></label><div class="error" id="error"></div><button class="submit" id="submit">Sign in</button></form><div class="note">The first account becomes the workspace administrator. Passwords are stored using PBKDF2 hashing.</div></main><script>
let mode='login';function show(m){mode=m;document.getElementById('nameField').classList.toggle('hidden',m==='login');document.getElementById('loginTab').classList.toggle('active',m==='login');document.getElementById('registerTab').classList.toggle('active',m==='register');document.getElementById('submit').textContent=m==='login'?'Sign in':'Create account';document.getElementById('error').textContent=''}document.getElementById('authForm').onsubmit=async e=>{e.preventDefault();let body={email:document.getElementById('email').value,password:document.getElementById('password').value,name:document.getElementById('name').value};let r=await fetch('/api/'+mode,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),d=await r.json();if(r.ok)location.href='/';else document.getElementById('error').textContent=d.error||'Request failed'};</script></body></html>'''

def auth_db():
    c=app.db(); c.executescript('''
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,email TEXT UNIQUE NOT NULL,name TEXT NOT NULL,password_hash TEXT NOT NULL,salt TEXT NOT NULL,role TEXT NOT NULL DEFAULT 'student',created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE INDEX IF NOT EXISTS idx_tasks_deadline ON tasks(deadline);
    CREATE INDEX IF NOT EXISTS idx_routines_day_time ON routines(day,start_time);
    '''); c.commit(); c.close()

def hash_password(password,salt=None):
    salt=salt or secrets.token_hex(16); digest=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),210_000).hex(); return salt,digest

def cookie_session(headers):
    raw=headers.get('Cookie',''); c=SimpleCookie(); c.load(raw); token=c.get('pa_session')
    if not token:return None
    data=SESSIONS.get(token.value)
    if not data or data['expires']<time.time(): SESSIONS.pop(token.value,None); return None
    return data

def rate_ok(ip):
    now=time.time(); q=REQUESTS[ip]
    while q and q[0]<now-RATE_WINDOW:q.popleft()
    if len(q)>=RATE_LIMIT:return False
    q.append(now); return True

class ProductionHandler(app.Handler):
    def end_headers(self):
        self.send_header('X-Content-Type-Options','nosniff'); self.send_header('X-Frame-Options','DENY')
        self.send_header('Referrer-Policy','strict-origin-when-cross-origin')
        self.send_header('Permissions-Policy','camera=(), geolocation=(), microphone=(self)')
        self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'")
        super().end_headers()
    def send_html(self,html,status=200):
        b=html.encode(); self.send_response(status); self.send_header('Content-Type','text/html; charset=utf-8'); self.send_header('Cache-Control','no-store'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        METRICS['requests']+=1; path=self.path.split('?')[0]
        if path=='/health': return self.send_json({'status':'ok','uptime_seconds':int(time.time()-METRICS['started_at'])})
        if path=='/metrics':
            if not cookie_session(self.headers): return self.send_json({'error':'Authentication required'},401)
            return self.send_json(METRICS)
        if path=='/login': return self.send_html(LOGIN_HTML)
        if path=='/api/me':
            u=cookie_session(self.headers); return self.send_json({'user':u and {'name':u['name'],'email':u['email'],'role':u['role']}})
        if not cookie_session(self.headers):
            if path.startswith('/api/'): return self.send_json({'error':'Authentication required'},401)
            return self.send_html(LOGIN_HTML,401)
        return super().do_GET()
    def do_POST(self):
        METRICS['requests']+=1; ip=self.client_address[0]; path=self.path.split('?')[0]
        if not rate_ok(ip): METRICS['rate_limited']+=1; return self.send_json({'error':'Too many requests. Try again shortly.'},429)
        try:
            if path in ('/api/register','/api/login'):
                data=self.body(); email=data.get('email','').strip().lower(); password=data.get('password',''); name=data.get('name','').strip()
                if '@' not in email or len(password)<8:return self.send_json({'error':'Enter a valid email and a password of at least 8 characters.'},400)
                c=app.db()
                if path=='/api/register':
                    if not name:return self.send_json({'error':'Name is required.'},400)
                    role='admin' if c.execute('SELECT COUNT(*) FROM users').fetchone()[0]==0 else 'student'; salt,digest=hash_password(password)
                    try:c.execute('INSERT INTO users(email,name,password_hash,salt,role) VALUES(?,?,?,?,?)',(email,name,digest,salt,role));c.commit()
                    except Exception:c.close();return self.send_json({'error':'An account with this email already exists.'},409)
                row=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone(); c.close()
                if not row:return self.send_json({'error':'Invalid email or password.'},401)
                _,digest=hash_password(password,row['salt'])
                if not hmac.compare_digest(digest,row['password_hash']):return self.send_json({'error':'Invalid email or password.'},401)
                token=secrets.token_urlsafe(32); SESSIONS[token]={'id':row['id'],'name':row['name'],'email':row['email'],'role':row['role'],'expires':time.time()+SESSION_TTL}
                payload=json.dumps({'ok':True,'role':row['role']}).encode(); self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Set-Cookie',f'pa_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={SESSION_TTL}'); self.send_header('Content-Length',str(len(payload))); self.end_headers(); return self.wfile.write(payload)
            if path=='/api/logout':
                u=cookie_session(self.headers); c=SimpleCookie(); c.load(self.headers.get('Cookie','')); t=c.get('pa_session');
                if t:SESSIONS.pop(t.value,None)
                return self.send_json({'ok':True})
            user=cookie_session(self.headers)
            if not user:return self.send_json({'error':'Authentication required'},401)
            if path=='/api/delete' and user['role']!='admin':return self.send_json({'error':'Administrator permission required.'},403)
            return super().do_POST()
        except Exception as exc:
            METRICS['errors']+=1; logger.exception('request_failed path=%s error=%s',path,exc); return self.send_json({'error':'Internal server error'},500)
    def log_message(self,fmt,*args): logger.info('ip=%s %s',self.client_address[0],fmt%args)

if __name__=='__main__':
    app.init_db(); auth_db(); logger.info('server_start port=%s',PORT)
    print(f'Personal Assistant Production running at http://127.0.0.1:{PORT}')
    ThreadingHTTPServer(('0.0.0.0',PORT),ProductionHandler).serve_forever()
