from django.db import models
from django.conf import settings
from core.models import Project
class DatasetVersion(models.Model):
    project=models.ForeignKey(Project,on_delete=models.CASCADE,related_name='dataset_versions')
    name=models.CharField(max_length=160)
    snapshot=models.JSONField()
    metrics=models.JSONField(default=dict)
    sha256=models.CharField(max_length=64)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    restored_from=models.ForeignKey('self',null=True,blank=True,on_delete=models.PROTECT)
class ExportArtifact(models.Model):
    project=models.ForeignKey(Project,on_delete=models.CASCADE)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    format=models.CharField(max_length=40)
    scope=models.CharField(max_length=20)
    sha256=models.CharField(max_length=64)
    row_count=models.PositiveIntegerField()
    file_path=models.CharField(max_length=500)
    created_at=models.DateTimeField(auto_now_add=True)
