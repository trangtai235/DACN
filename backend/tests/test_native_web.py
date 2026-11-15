from contextlib import contextmanager, redirect_stdout
import ctypes
from ctypes import wintypes
from io import StringIO
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from unittest import skipUnless
from unittest.mock import Mock, patch
from urllib.error import URLError
from django.conf import settings
from django.test import SimpleTestCase

sys.path.insert(0, str(settings.ROOT_DIR / 'scripts'))
import native_web


class NativeWebTests(SimpleTestCase):
    def test_startup_failure_always_stops_owned_processes(self):
        for failed_stage in ('backend', 'browser'):
            with self.subTest(stage=failed_stage):
                server, browser = Mock(), Mock()
                with patch.object(native_web, 'find_browser', return_value=Path('browser')), \
                     patch.object(native_web, 'prepare_profile'), \
                     patch.object(native_web, '_spawn', side_effect=[server, browser]) as spawn, \
                     patch.object(native_web, 'wait_for_backend') as ready, \
                     patch.object(native_web, 'wait_for_browser') as opened, \
                     patch.object(native_web, 'stop_process_tree') as stop, redirect_stdout(StringIO()):
                    (ready if failed_stage == 'backend' else opened).side_effect = RuntimeError('fixture startup failure')
                    with self.assertRaisesMessage(RuntimeError, 'fixture startup failure'):
                        native_web.run_web_window(['fixture-server'], '.', {}, profile=Path('fixture-profile'))
                self.assertEqual(spawn.call_count, 1 if failed_stage == 'backend' else 2)
                self.assertEqual(stop.call_args_list[-1].args, (server,))
                if failed_stage == 'browser':
                    self.assertEqual(stop.call_args_list[0].args, (browser,))

    def test_profile_cleanup_preserves_login_and_rejects_active_window(self):
        with TemporaryDirectory() as folder:
            profile = Path(folder)
            endpoint = profile / 'DevToolsActivePort'; endpoint.write_text('12345\n/devtools/browser/fixture')
            cookie = profile / 'login-fixture'; cookie.write_text('keep this session')
            with patch.object(native_web, '_json', return_value={'webSocketDebuggerUrl':'ws://127.0.0.1:12345/devtools/browser/fixture'}):
                with self.assertRaisesMessage(RuntimeError, 'cu van dang mo'):
                    native_web.prepare_profile(profile)
            self.assertTrue(endpoint.exists())
            with patch.object(native_web, '_json', side_effect=URLError('fixture closed')):
                native_web.prepare_profile(profile)
            self.assertFalse(endpoint.exists()); self.assertEqual(cookie.read_text(), 'keep this session')

    def test_reload_and_route_change_do_not_stop_server(self):
        server, browser = Mock(), Mock(); server.poll.return_value = browser.poll.return_value = None
        pages = [[{'id':'app','type':'page','url':''}],
                 [{'id':'app','type':'page','url':'http://127.0.0.1:8000/#datasets'}], [], []]
        with patch.object(native_web, '_json', side_effect=pages) as read, \
             patch.object(native_web.time, 'sleep'), \
             patch.object(native_web.time, 'monotonic', side_effect=[1,1,2.2]):
            native_web.watch_window(server, browser, 'http://127.0.0.1:12345', {'app'}, 'http://127.0.0.1:8000')
        self.assertEqual(read.call_count,4)


def process_alive(pid):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE,wintypes.DWORD]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x100000,False,pid)
    if not handle:
        return False
    try:
        return kernel.WaitForSingleObject(handle,0) == 258
    finally:
        kernel.CloseHandle(handle)


@skipUnless(os.name == 'nt' and os.environ.get('ANNOTAFLOW_NATIVE_LIFECYCLE_TESTS') == '1',
            'Set ANNOTAFLOW_NATIVE_LIFECYCLE_TESTS=1 on Windows to exercise an installed Edge/Chrome.')
class NativeWindowIntegrationTests(SimpleTestCase):
    @contextmanager
    def window(self):
        browser = native_web.find_browser()
        with TemporaryDirectory() as folder:
            root = Path(folder); profile = root / 'profile'
            with socket.socket() as probe:
                probe.bind(('127.0.0.1',0)); port = probe.getsockname()[1]
            log_path = root / 'launcher.log'
            with log_path.open('w',encoding='utf-8') as log:
                command = [sys.executable,str(settings.ROOT_DIR / 'backend/tests/native_window_fixture.py'),
                           'launch',str(port),str(profile),str(browser)]
                proc = subprocess.Popen(command,cwd=settings.ROOT_DIR,stdout=log,stderr=subprocess.STDOUT,
                                        creationflags=subprocess.CREATE_NO_WINDOW)
                try:
                    deadline = time.monotonic() + 40
                    while time.monotonic() < deadline:
                        text = log_path.read_text(encoding='utf-8',errors='replace')
                        if 'ANNOTAFLOW_WEB_READY ' in text:
                            break
                        if proc.poll() is not None:
                            self.fail(text)
                        time.sleep(.1)
                    else:
                        self.fail('Launcher timed out: ' + text)
                    endpoint,_ = native_web._endpoint(profile)
                    url = f'http://127.0.0.1:{port}'
                    info = native_web._json(url + '/api/session')
                    launcher_pid = int(next(line.split('=',1)[1] for line in text.splitlines() if line.startswith('FIXTURE_LAUNCHER_PID=')))
                    yield proc,url,endpoint,info,launcher_pid
                finally:
                    native_web.stop_process_tree(proc)
                    # A hard-killed launcher closes its Job Object and all descendants.
                    time.sleep(.2)

    def assert_backend_stopped(self,url,info):
        for _ in range(30):
            if not process_alive(info['pid']) and not process_alive(info['child_pid']):
                break
            time.sleep(.1)
        self.assertFalse(process_alive(info['pid']))
        self.assertFalse(process_alive(info['child_pid']))
        address = native_web.urlsplit(url)
        with socket.socket() as probe:
            self.assertNotEqual(probe.connect_ex((address.hostname,address.port)),0)

    def test_close_web_stops_backend_and_leaves_other_browser_alone(self):
        with TemporaryDirectory() as folder:
            profile = Path(folder)
            browser = native_web._spawn([native_web.find_browser(),f'--user-data-dir={profile}',
                '--remote-debugging-port=0','--no-first-run','--no-default-browser-check','--headless=new','about:blank'],
                settings.ROOT_DIR,os.environ.copy())
            try:
                for _ in range(200):
                    try:
                        other_endpoint,_ = native_web._endpoint(profile)
                        native_web._json(other_endpoint + '/json/list'); break
                    except (IndexError,*native_web.NETWORK_ERRORS):time.sleep(.1)
                else:self.fail('Separate fixture browser did not start')
                with self.window() as (proc,url,endpoint,info,launcher_pid):
                    time.sleep(1)
                    self.assertIsNone(proc.poll())
                    pages = native_web._json(endpoint + '/json/list')
                    self.assertTrue(any(p.get('url','').endswith('#datasets') for p in pages))
                    for page in pages:
                        if native_web.is_app_page(page,url):
                            native_web.LOCAL_HTTP.open(endpoint + '/json/close/' + page['id'],timeout=2).close()
                    self.assertEqual(proc.wait(timeout=15),0)
                    self.assert_backend_stopped(url,info)
                    self.assertIsNotNone(native_web._json(other_endpoint + '/json/version'))
            finally:native_web.stop_process_tree(browser)

    def test_backend_crash_closes_owned_browser(self):
        with self.window() as (proc,url,endpoint,info,launcher_pid):
            native_web.LOCAL_HTTP.open(url + '/shutdown',timeout=2).close()
            self.assertNotEqual(proc.wait(timeout=15),0)
            self.assert_backend_stopped(url,info)
            with self.assertRaises(native_web.NETWORK_ERRORS):native_web._json(endpoint + '/json/list')

    def test_force_close_launcher_reaps_backend_and_its_children(self):
        with self.window() as (proc,url,endpoint,info,launcher_pid):
            subprocess.run(['taskkill','/PID',str(launcher_pid),'/F'],check=True,
                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
            proc.wait(timeout=15)
            self.assert_backend_stopped(url,info)
            with self.assertRaises(native_web.NETWORK_ERRORS):native_web._json(endpoint + '/json/list')
