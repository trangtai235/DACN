from django.db import models
from django.conf import settings
from core.models import Comment
from .projects import ProjectLabel
class Annotation(models.Model):
    seconds=models.FloatField(default=0)
    comment=models.ForeignKey(Comment,on_delete=models.CASCADE,related_name='annotations')
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    label=models.ForeignKey(ProjectLabel,null=True,blank=True,on_delete=models.PROTECT)
    spans=models.JSONField(default=list)
    note=models.TextField(blank=True)
    status=models.CharField(max_length=16,default='submitted')
    assisted=models.BooleanField(default=False)
    revision=models.PositiveIntegerField(default=1)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:constraints=[models.UniqueConstraint(fields=['comment','user'],name='studio_one_annotation_per_user')]
class AnnotationEvent(models.Model):
    comment=models.ForeignKey(Comment,on_delete=models.CASCADE)
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    before=models.JSONField(default=dict)
    after=models.JSONField(default=dict)
    action=models.CharField(max_length=24)
    created_at=models.DateTimeField(auto_now_add=True)
class GoldAnnotation(models.Model):
    comment=models.OneToOneField(Comment,on_delete=models.CASCADE,related_name='gold_annotation')
    label=models.ForeignKey(ProjectLabel,null=True,blank=True,on_delete=models.PROTECT)
    spans=models.JSONField(default=list)
    note=models.TextField()
    adjudicator=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    updated_at=models.DateTimeField(auto_now=True)

class AIExposure(models.Model):
    comment=models.ForeignKey(Comment,on_delete=models.CASCADE)
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    first_exposed_at=models.DateTimeField(auto_now_add=True)
    class Meta:constraints=[models.UniqueConstraint(fields=['comment','user'],name='studio_unique_ai_exposure')]
