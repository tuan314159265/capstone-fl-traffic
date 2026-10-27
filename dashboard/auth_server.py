"""Small cookie-authenticated static dashboard server behind Caddy HTTPS."""
import base64
from collections import defaultdict, deque
import hashlib
import hmac
import html
from http import cookies
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import parse_qs, urlparse

COOKIE = '__Host-traffic_session'
MAX_AGE = 7*86400


def password_matches(config, password):
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(config['salt']), config['iterations'])
    return hmac.compare_digest(digest.hex(), config['password_hash'])


def create_session(config, lifetime, timestamp=None):
    timestamp = int(time.time() if timestamp is None else timestamp)
    body = base64.urlsafe_b64encode(json.dumps({'user':config['username'], 'expires':timestamp+lifetime,
        'nonce':secrets.token_hex(12)},separators=(',',':')).encode()).decode().rstrip('=')
    signature = hmac.new(bytes.fromhex(config['session_key']),body.encode(),hashlib.sha256).hexdigest()
    return body+'.'+signature


def valid_session(config, token, timestamp=None):
    if not token or len(token)>1024:return False
    try:
        body, signature = token.split('.')
        expected = hmac.new(bytes.fromhex(config['session_key']),body.encode(),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature,expected):return False
        data = json.loads(base64.urlsafe_b64decode(body+'='*(-len(body)%4)))
        now = time.time() if timestamp is None else timestamp
        return data['user']==config['username'] and now<data['expires']<=now+MAX_AGE+30
    except (ValueError,KeyError,TypeError):return False


class Server(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address, config, root, snapshot, auth_assets):
        self.config, self.root, self.snapshot, self.auth_assets = config,root,snapshot,auth_assets
        self.failures = defaultdict(deque)
        self.lock = threading.Lock()
        super().__init__(address, Handler)


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # Never log cookies, passwords, headers or form bodies.
        print(f'{self.command} {urlparse(self.path).path} {args[1] if len(args)>1 else ""}',flush=True)

    def respond(self, status, body=b'', content_type='text/html; charset=utf-8', headers=None):
        self.send_response(status)
        self.send_header('Content-Type',content_type)
        self.send_header('Cache-Control','no-store, private')
        self.send_header('Content-Length',str(len(body)))
        for key,value in (headers or {}).items():self.send_header(key,value)
        self.end_headers()
        if self.command!='HEAD':self.wfile.write(body)

    def authenticated(self):
        try:
            parsed=cookies.SimpleCookie(self.headers.get('Cookie',''))
            return valid_session(self.server.config,parsed[COOKIE].value if COOKIE in parsed else None)
        except cookies.CookieError:return False

    def login_page(self, error='', status=200):
        page=(self.server.auth_assets/'login.html').read_text()
        page=page.replace('{{error}}',f'<p class="login-error" role="alert">{html.escape(error)}</p>' if error else '')
        self.respond(status,page.encode())

    def do_HEAD(self):self.do_GET()

    def do_GET(self):
        path=urlparse(self.path).path
        if path=='/login':
            if self.authenticated():self.respond(303,headers={'Location':'/'})
            else:self.login_page()
            return
        if path in {'/auth/login.css','/auth/login.js'}:
            filename=path.rsplit('/',1)[1]
            self.respond(200,(self.server.auth_assets/filename).read_bytes(),
                'text/css' if filename.endswith('.css') else 'text/javascript')
            return
        if path!='/favicon.svg' and not self.authenticated():
            if path.startswith('/api/'):
                self.respond(401,b'{"error":"authentication_required"}','application/json')
            else:self.respond(303,headers={'Location':'/login'})
            return
        if path=='/api/traffic':
            try:self.respond(200,self.server.snapshot.read_bytes(),'application/json')
            except OSError:self.respond(503,b'{"error":"snapshot_unavailable"}','application/json')
            return
        if path.startswith('/api/') or path.startswith('/auth/'):
            self.respond(404,b'Not found','text/plain');return
        candidate=Path(self.translate_path(path)).resolve()
        if not candidate.is_relative_to(self.server.root.resolve()):
            self.respond(404);return
        if candidate.is_dir():candidate=candidate/'index.html'
        if not candidate.is_file():candidate=self.server.root/'index.html'
        self.respond(200,candidate.read_bytes(),self.guess_type(str(candidate)))

    def translate_path(self,path):
        # SimpleHTTPRequestHandler normalizes URL paths; the resolved prefix is
        # checked again before serving. Only the static root is reachable.
        self.directory=str(self.server.root)
        return super().translate_path(path)

    def do_POST(self):
        path=urlparse(self.path).path
        if self.headers.get('Origin')!=self.server.config['origin']:
            self.respond(403,b'Invalid origin','text/plain');return
        if path=='/auth/logout':
            self.respond(303,headers={'Location':'/login','Set-Cookie':f'{COOKIE}=; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=0'})
            return
        if path!='/auth/login':self.respond(404);return
        try:length=int(self.headers.get('Content-Length','0'))
        except ValueError:self.respond(400);return
        if not 0<length<=4096:self.respond(413);return
        try:form=parse_qs(self.rfile.read(length).decode(),max_num_fields=8)
        except (UnicodeError,ValueError):self.respond(400);return
        ip=self.headers.get('X-Forwarded-For',self.client_address[0]).split(',')[0].strip()
        now=time.time()
        with self.server.lock:
            if len(self.server.failures)>1024:
                self.server.failures.clear()
            failures=self.server.failures[ip]
            while failures and failures[0]<now-900:failures.popleft()
            if len(failures)>=8:
                self.login_page('Bạn đã thử quá nhiều lần. Vui lòng thử lại sau 15 phút.',429);return
            # Reserve an attempt before the expensive password derivation.
            failures.append(now)
        username=form.get('username',[''])[0]
        password=form.get('password',[''])[0]
        correct_password=password_matches(self.server.config,password)
        if not hmac.compare_digest(username.encode(),self.server.config['username'].encode()) or not correct_password:
            self.login_page('Tên đăng nhập hoặc mật khẩu chưa đúng.',401);return
        with self.server.lock:self.server.failures.pop(ip,None)
        lifetime=MAX_AGE if form.get('remember')==['on'] else 8*3600
        token=create_session(self.server.config,lifetime)
        self.respond(303,headers={'Location':'/','Set-Cookie':f'{COOKIE}={token}; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age={lifetime}'})


if __name__=='__main__':
    config=json.loads(Path(os.environ.get('WEB_AUTH_CONFIG','/config/auth.json')).read_text())
    Server(('0.0.0.0',8080),config,Path('/srv'),Path('/snapshot/traffic-snapshot.json'),Path('/app/auth')).serve_forever()
