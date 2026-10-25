from django.contrib import admin
from django.urls import path,include
from core import api
urlpatterns=[path('api/studio/',include('studio.urls')),path('',api.index),path('en/login/',api.index),path('vi/login/',api.index),path('en/register/',api.index),path('vi/register/',api.index),path('admin/',admin.site.urls),path('api/session',api.session),path('api/register',api.sign_up),path('api/login',api.sign_in),path('api/logout',api.sign_out),
path('api/bootstrap',api.bootstrap),path('api/projects',api.create_project),path('api/import',api.import_comments),path('api/youtube',api.youtube),path('api/predict',api.predict),
path('api/comments/<int:comment_id>/first',api.first_pass),path('api/runs',api.create_run),path('api/runs/<int:run_id>/claim',api.claim_review),path('api/tasks/<int:task_id>/submit',api.submit_review),path('api/tasks/<int:task_id>/adjudicate',api.adjudication),
path('api/predict-one',api.predict_one),path('api/training',api.training),path('api/benchmark',api.benchmark),path('api/jobs/<int:job_id>',api.job_status),path('api/export',api.export),path('api/references',api.import_references),path('api/human-metrics',api.human_metrics),path('api/members',api.add_member)]
