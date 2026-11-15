"""Optional real-browser smoke test against Django, using explicit synthetic fixtures."""
import json
import os
import subprocess
import time
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import skipUnless
from unittest.mock import patch
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client, override_settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from core.models import Project,Source,Comment
from integrations.models import ProviderConnection
from studio.services.projects import ensure


@skipUnless(os.environ.get('ANNOTAFLOW_PLAYWRIGHT_MODULE'), 'Set ANNOTAFLOW_PLAYWRIGHT_MODULE to an installed Playwright package path.')
@override_settings(DEBUG=True, ALLOWED_HOSTS=['localhost','127.0.0.1','testserver'], SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class CollaborationBrowserTests(StaticLiveServerTestCase):
    def test_paired_decisions_and_budget_in_browser(self):
        def mock_translation(*args):
            time.sleep(.5)
            return 'Bản dịch thử nghiệm 😀 <script>không thực thi</script>'
        with TemporaryDirectory() as folder, override_settings(PRIVATE_DATA=Path(folder)), patch('core.services.jobs.dispatch'),patch('studio.api.translations.translate',side_effect=mock_translation) as translation:
            sessions={}
            for role in ('owner','reviewer','judge'):
                user=User.objects.create_user(username='browser-'+role)
                client=Client();client.force_login(user);sessions[role]=client.cookies['sessionid'].value
            call_command('seed_collaboration_demo',owner='browser-owner',reviewer='browser-reviewer',judge='browser-judge',stdout=StringIO())
            project=Project.objects.get(owner__username='browser-owner')
            provider=ProviderConnection.objects.create(project=project,name='Mock translation',kind='openai_compatible',base_url='https://api.openai.com/v1',model='fixture')
            prefs=ensure(project);prefs.active_connection=provider;prefs.save()
            source=Source.objects.create(project=project,name='Manual human fixture')
            Comment.objects.create(project=project,source=source,text='Mẫu gán thủ công trong kiểm thử Human-in-the-loop')
            env={**os.environ,'ANNOTAFLOW_BROWSER_SESSIONS':json.dumps(sessions)}
            result=subprocess.run(['node',str(settings.ROOT_DIR/'scripts/browser_collaboration.mjs'),self.live_server_url],
                                  env=env,capture_output=True,text=True,encoding='utf-8',timeout=120)
            self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
            self.assertIn('BROWSER_SMOKE_OK',result.stdout)
            self.assertEqual(translation.call_count,1)
