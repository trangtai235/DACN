from django.contrib import admin
from .models import Project,Membership,Source,Comment,Prediction,Job,AuditEvent
for model in [Project,Membership,Source,Comment,Prediction,Job,AuditEvent]:admin.site.register(model)
