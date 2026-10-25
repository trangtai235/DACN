from django.contrib import admin
from .models import ModelRun,BenchmarkRun,ReferenceLabel
for model in [ModelRun,BenchmarkRun,ReferenceLabel]:admin.site.register(model)
