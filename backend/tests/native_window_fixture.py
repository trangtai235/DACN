"""Subprocess fixture: a local HTTP backend with a child, no database or AI calls."""
import json
import os
from pathlib import Path
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))


def serve(port):
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(180)'],
                             **({'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}))

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.path == '/api/session':
                body = json.dumps({'pid': os.getpid(), 'child_pid': child.pid}).encode()
                kind = 'application/json'
            else:
                body = b'''<!doctype html><title>AnnotaFlow launcher fixture</title><p>Fixture only</p>
<script>const n=Number(sessionStorage.reloads||0);sessionStorage.reloads=n+1;
if(n===0)setTimeout(()=>location.reload(),200);
else setTimeout(()=>history.replaceState(null,'','/#datasets'),200);</script>'''
                kind = 'text/html'
            self.send_response(200); self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
            if self.path == '/shutdown':
                Thread(target=self.server.shutdown, daemon=True).start()

    try:
        with ThreadingHTTPServer(('127.0.0.1', port), Handler) as server:
            server.serve_forever(poll_interval=.1)
    finally:
        child.terminate(); child.wait(timeout=5)


if __name__ == '__main__':
    if sys.argv[1] == 'serve':
        serve(int(sys.argv[2]))
    else:
        from server_lifecycle import bind_server_lifetime
        from native_web import run_web_window
        bind_server_lifetime()
        print('FIXTURE_LAUNCHER_PID=' + str(os.getpid()), flush=True)
        port, profile, browser = sys.argv[2:5]
        try:
            run_web_window([sys.executable, __file__, 'serve', port], ROOT, os.environ.copy(),
                           url='http://127.0.0.1:' + port, profile=Path(profile),
                           browser_path=browser, headless=True, startup_timeout=10, browser_timeout=25)
        except RuntimeError as error:
            print(str(error), file=sys.stderr, flush=True)
            sys.exit(1)
