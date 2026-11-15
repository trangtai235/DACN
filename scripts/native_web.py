"""Run the local backend for the lifetime of its own Edge/Chrome app window.

The browser profile is private to this app. DevTools is bound to loopback on an
ephemeral port; normal browser profiles and their tabs are never inspected.
"""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import build_opener, ProxyHandler

ROOT = Path(__file__).resolve().parent.parent
LOCAL_HTTP = build_opener(ProxyHandler({}))
NETWORK_ERRORS = (OSError, ValueError, URLError)


def find_browser(explicit=None):
    override = explicit or os.environ.get('ANNOTAFLOW_NATIVE_BROWSER')
    if override:
        binary = Path(override)
        if not binary.is_file():
            raise RuntimeError('Khong tim thay Edge/Chrome tai ANNOTAFLOW_NATIVE_BROWSER.')
        return binary
    # Search all Chrome locations before Edge, including a 64-bit Chrome when
    # Edge happens to be installed in Program Files (x86).
    for relative, commands in (
        ('Google/Chrome/Application/chrome.exe', ('chrome', 'google-chrome', 'chromium', 'chromium-browser')),
        ('Microsoft/Edge/Application/msedge.exe', ('msedge',)),
    ):
        candidates = [Path(base) / relative for base in (
            os.environ.get('ProgramFiles(x86)'), os.environ.get('ProgramFiles'), os.environ.get('LOCALAPPDATA')) if base]
        for name in commands:
            found = shutil.which(name)
            if found:
                candidates.append(Path(found))
        for binary in candidates:
            if binary.is_file():
                return binary
    raise RuntimeError('Can cai Microsoft Edge hoac Google Chrome de mo cua so AnnotaFlow.')


def _json(url):
    with LOCAL_HTTP.open(url, timeout=1) as response:
        return json.loads(response.read(1024 * 1024))


def is_app_page(target, url):
    if target.get('type') != 'page':
        return False
    candidate, expected = urlsplit(target.get('url', '')), urlsplit(url)
    return (candidate.scheme == expected.scheme and candidate.port == expected.port
            and candidate.hostname in ('127.0.0.1', 'localhost')
            and expected.hostname in ('127.0.0.1', 'localhost'))


def _endpoint(profile):
    lines = (profile / 'DevToolsActivePort').read_text(encoding='utf-8').splitlines()
    port = int(lines[0])
    if not 1 <= port <= 65535:
        raise ValueError('Invalid browser port')
    return f'http://127.0.0.1:{port}', lines[1]


def prepare_profile(profile):
    profile.mkdir(parents=True, exist_ok=True)
    try:
        endpoint, browser_path = _endpoint(profile)
        version = _json(endpoint + '/json/version')
        if urlsplit(version.get('webSocketDebuggerUrl', '')).path == browser_path:
            raise RuntimeError('Cua so AnnotaFlow cu van dang mo. Dong cua so do truoc khi chay lai BAT.')
    except (IndexError, *NETWORK_ERRORS):
        pass
    # Remove only this stale endpoint file; keep cookies, storage and login state.
    (profile / 'DevToolsActivePort').unlink(missing_ok=True)


def _spawn(command, cwd, env):
    options = {'cwd': str(cwd), 'env': env, 'stdin': subprocess.DEVNULL}
    if os.name == 'nt':
        options['creationflags'] = subprocess.CREATE_NO_WINDOW
    else:
        options['start_new_session'] = True
    return subprocess.Popen([str(arg) for arg in command], **options)


def stop_process_tree(process, grace=0):
    if process is None:
        return
    if grace:
        try:
            process.wait(timeout=grace)
            return
        except subprocess.TimeoutExpired:
            pass
    if process.poll() is None:
        if os.name == 'nt':
            # The venv python.exe can have a real python.exe child. Stop this
            # specific owned tree, never all python/browser processes by name.
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=subprocess.CREATE_NO_WINDOW, timeout=10, check=False)
        else:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    try:
        process.wait(timeout=4)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=4)


def wait_for_backend(server, url, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise RuntimeError('Backend dung truoc khi san sang. Xem loi trong cua so BAT.')
        try:
            with LOCAL_HTTP.open(url.rstrip('/') + '/api/session', timeout=1) as response:
                if response.status == 200 and server.poll() is None:
                    return
        except NETWORK_ERRORS:
            pass
        time.sleep(.15)
    raise RuntimeError('Backend chua san sang sau thoi gian cho. Kiem tra log va PostgreSQL.')


def wait_for_browser(server, browser, profile, url, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise RuntimeError('Backend da dung khi dang mo cua so web.')
        try:
            endpoint, _ = _endpoint(profile)
            pages = _json(endpoint + '/json/list')
            app_ids = {p['id'] for p in pages if is_app_page(p, url)}
            if app_ids:
                return endpoint, app_ids
        except (IndexError, *NETWORK_ERRORS):
            pass
        time.sleep(.15)
    raise RuntimeError('Khong mo duoc cua so AnnotaFlow. Kiem tra Edge/Chrome va chay lai BAT.')


def watch_window(server, browser, endpoint, app_ids, url):
    missing_since = unreachable_since = None
    while True:
        if server.poll() is not None:
            raise RuntimeError('Backend da dung bat thuong. Xem log trong cua so BAT.')
        try:
            pages = _json(endpoint + '/json/list')
            unreachable_since = None
            app_ids.update(p['id'] for p in pages if is_app_page(p, url))
            # Track page IDs as well as URLs, so reloads, redirects, and SPA
            # navigation do not look like closing the window.
            if any(p.get('id') in app_ids for p in pages):
                missing_since = None
            else:
                missing_since = missing_since or time.monotonic()
                if time.monotonic() - missing_since >= 1:
                    return
        except NETWORK_ERRORS:
            unreachable_since = unreachable_since or time.monotonic()
            if browser.poll() is not None or time.monotonic() - unreachable_since >= 3:
                return
        time.sleep(.2)


def run_web_window(server_command, cwd, env, *, url='http://127.0.0.1:8000',
                   browser_path=None, profile=None, headless=False,
                   startup_timeout=60, browser_timeout=25):
    """Caller binds server_lifecycle before spawning so terminal-close cleans up too."""
    address = urlsplit(url)
    if address.scheme != 'http' or address.hostname not in ('127.0.0.1', 'localhost'):
        raise ValueError('Native app chi duoc mo backend localhost.')
    binary = find_browser(browser_path)
    profile = Path(profile) if profile else ROOT / 'backend/private_data/native-browser' / binary.stem
    prepare_profile(profile)
    server = browser = None
    endpoint = None
    try:
        server = _spawn(server_command, cwd, env)
        wait_for_backend(server, url, startup_timeout)
        command = [binary, f'--user-data-dir={profile.resolve()}', '--remote-debugging-port=0',
                   '--remote-debugging-address=127.0.0.1', '--no-first-run',
                   '--no-default-browser-check', '--disable-background-mode', f'--app={url}']
        if headless:
            command.extend(('--headless=new', url))
        browser = _spawn(command, cwd, env)
        endpoint, app_ids = wait_for_browser(server, browser, profile, url, browser_timeout)
        print('ANNOTAFLOW_WEB_READY ' + url, flush=True)
        print('Dong cua so web AnnotaFlow de dung backend. Ctrl+C trong BAT cung dung app.', flush=True)
        watch_window(server, browser, endpoint, app_ids, url)
    finally:
        try:
            if endpoint:
                try:
                    for page in _json(endpoint + '/json/list'):
                        if page.get('type') == 'page' and is_app_page(page, url):
                            LOCAL_HTTP.open(endpoint + '/json/close/' + page['id'], timeout=1).close()
                except NETWORK_ERRORS:
                    pass
            stop_process_tree(browser, grace=1)
        finally:
            stop_process_tree(server)
        print('Da dung web va backend AnnotaFlow.', flush=True)
