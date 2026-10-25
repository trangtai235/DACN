import hashlib,json
from django.conf import settings
from django.db import models
LABELS=[('NON_TOXIC','Không độc hại'),('TOXIC','Độc hại')]
class Project(models.Model):
    name=models.CharField(max_length=180)
    description=models.TextField(blank=True)
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    is_demo=models.BooleanField(default=False)
    def __str__(self):return self.name
class Membership(models.Model):
    project=models.ForeignKey(Project,on_delete=models.CASCADE,related_name='memberships')
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    role=models.CharField(max_length=20,default='annotator',choices=[('manager','Quản lý'),('annotator','Gán nhãn')])
    class Meta:constraints=[models.UniqueConstraint(fields=['project','user'],name='unique_project_member')]
class Source(models.Model):
    url=models.URLField(max_length=500,blank=True)
    metadata=models.JSONField(default=dict)
    checkpoint=models.JSONField(default=dict)
    fetch_state=models.CharField(max_length=20,default='idle')
    project=models.ForeignKey(Project,on_delete=models.CASCADE,related_name='sources')
    name=models.CharField(max_length=200)
    kind=models.CharField(max_length=20,default='manual')
    external_id=models.CharField(max_length=120,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
class Comment(models.Model):
    original_text=models.TextField(blank=True)
    author=models.CharField(max_length=200,blank=True)
    parent_external_id=models.CharField(max_length=120,blank=True)
    published_at=models.DateTimeField(null=True,blank=True)
    unusable=models.BooleanField(default=False)
    project=models.ForeignKey(Project,on_delete=models.CASCADE,related_name='comments')
    source=models.ForeignKey(Source,on_delete=models.PROTECT,related_name='comments')
    text=models.TextField()
    digest=models.CharField(max_length=64)
    external_id=models.CharField(max_length=120,blank=True)
    context=models.TextField(blank=True)
    ai_label=models.CharField(max_length=64,null=True,blank=True)
    ai_provider=models.CharField(max_length=80,blank=True)
    first_label=models.CharField(max_length=64,null=True,blank=True)
    first_actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,null=True,blank=True)
    first_note=models.TextField(blank=True)
    first_seconds=models.FloatField(default=0)
    first_frozen_at=models.DateTimeField(null=True,blank=True)
    origin_group=models.CharField(max_length=1,blank=True)
    revision=models.PositiveIntegerField(default=0)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:constraints=[models.UniqueConstraint(fields=['project','digest'],name='unique_project_comment_digest')]
    def save(self,*a,**kw):
        if not self.original_text:self.original_text=self.text
        if not self.digest:self.digest=hashlib.sha256(self.text.strip().encode()).hexdigest()
        super().save(*a,**kw)
class Prediction(models.Model):
    spans=models.JSONField(default=list)
    config_snapshot=models.JSONField(default=dict)
    comment=models.ForeignKey(Comment,on_delete=models.CASCADE,related_name='predictions')
    provider=models.CharField(max_length=80)
    model_version=models.CharField(max_length=160)
    label=models.CharField(max_length=64)
    latency_ms=models.FloatField(default=0)
    input_tokens=models.PositiveIntegerField(default=0)
    output_tokens=models.PositiveIntegerField(default=0)
    estimated_cost_usd=models.FloatField(default=0)
    created_at=models.DateTimeField(auto_now_add=True)
class Job(models.Model):
    cancel_requested=models.BooleanField(default=False)
    checkpoint=models.JSONField(default=dict)
    project=models.ForeignKey(Project,on_delete=models.CASCADE)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    kind=models.CharField(max_length=30)
    status=models.CharField(max_length=20,default='queued')
    progress=models.PositiveSmallIntegerField(default=0)
    message=models.CharField(max_length=500,blank=True)
    payload=models.TextField(default='{}')
    result=models.TextField(default='{}')
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
class AuditEvent(models.Model):
    project=models.ForeignKey(Project,on_delete=models.CASCADE,related_name='events')
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,null=True)
    action=models.CharField(max_length=80)
    detail=models.TextField(default='{}')
    created_at=models.DateTimeField(auto_now_add=True)
def audit(project,actor,action,**detail):
    return AuditEvent.objects.create(project=project,actor=actor,action=action,detail=json.dumps(detail,ensure_ascii=False))
