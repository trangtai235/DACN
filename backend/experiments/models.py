from django.db import models
from django.conf import settings
from core.models import Project,Comment,LABELS
class ModelRun(models.Model):
    algorithm=models.CharField(max_length=50,default='logistic_regression')
    test_path=models.CharField(max_length=500,blank=True)
    project=models.ForeignKey(Project,on_delete=models.CASCADE,related_name='model_runs')
    name=models.CharField(max_length=160)
    state=models.CharField(max_length=20,default='ready')
    artifact_path=models.CharField(max_length=500)
    report=models.TextField(default='{}')
    created_at=models.DateTimeField(auto_now_add=True)
class BenchmarkRun(models.Model):
    project=models.ForeignKey(Project,on_delete=models.CASCADE,related_name='benchmark_runs')
    provider=models.CharField(max_length=80)
    model_name=models.CharField(max_length=160)
    dataset_hash=models.CharField(max_length=64)
    report=models.TextField(default='{}')
    predictions=models.TextField(default='[]')
    created_at=models.DateTimeField(auto_now_add=True)
class ReferenceLabel(models.Model):
    comment=models.OneToOneField(Comment,on_delete=models.CASCADE)
    label=models.CharField(max_length=16,choices=LABELS)
    provenance=models.CharField(max_length=240)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
