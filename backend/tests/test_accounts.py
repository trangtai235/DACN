import json
from django.contrib.auth.models import User
from django.test import Client, TestCase
from core.models import Membership, Project


class AccountTests(TestCase):
    def payload(self, **changes):
        return {'username':'new_student','first_name':'Sinh viên mới','email':'student@example.test',
                'password':'Annotation-Project!47','password_confirm':'Annotation-Project!47',**changes}

    def register(self, **changes):
        return self.client.post('/api/register', json.dumps(self.payload(**changes)),content_type='application/json')

    def test_registration_hashes_password_and_grants_no_existing_access(self):
        owner=User.objects.create_user('owner',password='Owner-Pass!47')
        private=Project.objects.create(name='Private existing project',owner=owner)
        Membership.objects.create(project=private,user=owner,role='manager')
        response=self.register()
        self.assertEqual(response.status_code,201)
        user=User.objects.get(username='new_student')
        self.assertTrue(user.check_password(self.payload()['password']))
        self.assertNotEqual(user.password,self.payload()['password'])
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(self.client.get('/api/bootstrap').json()['projects'],[])
        self.assertEqual(self.client.get('/api/bootstrap',{'project':private.id}).status_code,404)
        created=self.client.post('/api/projects',json.dumps({'name':'My new project'}),content_type='application/json')
        self.assertEqual(created.status_code,200)
        self.assertEqual(Project.objects.get(pk=created.json()['id']).owner,user)

    def test_registration_rejects_password_mismatch_and_weak_password(self):
        self.assertEqual(self.register(password_confirm='Different-Pass!42').status_code,400)
        self.assertEqual(self.register(password='12345678',password_confirm='12345678').status_code,400)
        self.assertEqual(User.objects.count(),0)

    def test_duplicate_username_case_insensitive_and_invalid_email(self):
        User.objects.create_user('New_Student',password='Safe-Password!42')
        self.assertEqual(self.register().status_code,400)
        self.assertEqual(self.register(username='another_student',email='invalid').status_code,400)
        self.assertEqual(User.objects.count(),1)

    def test_registration_requires_csrf_token(self):
        client=Client(enforce_csrf_checks=True)
        self.assertEqual(client.post('/api/register',json.dumps(self.payload()),content_type='application/json').status_code,403)
        page=client.get('/en/login/')
        self.assertEqual(page.status_code,200)
        self.assertIn('csrftoken',client.cookies)
        token=client.cookies['csrftoken'].value
        response=client.post('/api/register',json.dumps(self.payload()),content_type='application/json',HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code,201)

    def test_remember_login_and_logout(self):
        self.register()
        self.client.post('/api/logout')
        self.assertIsNone(self.client.get('/api/session').json()['user'])
        body={'username':'new_student','password':self.payload()['password']}
        self.client.post('/api/login',json.dumps(body),content_type='application/json')
        self.assertTrue(self.client.session.get_expire_at_browser_close())
        self.client.post('/api/logout')
        self.client.post('/api/login',json.dumps({**body,'remember':'on'}),content_type='application/json')
        self.assertFalse(self.client.session.get_expire_at_browser_close())
        self.assertEqual(self.client.session.get_expiry_age(),14*24*60*60)

    def test_localized_entry_paths_use_shared_api_interface(self):
        for path in ['/en/login/','/vi/login/','/en/register/','/vi/register/']:
            response=self.client.get(path)
            self.assertEqual(response.status_code,200)
            self.assertContains(response,'data-mode="api"')
            self.assertRegex(response.content.decode(),r'href="/assets/styles/auth\.css(?:\?v=[a-f0-9]+)?"')
