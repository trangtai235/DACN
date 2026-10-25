from django.db import models
from django.conf import settings
from core.models import Project
class ProjectSettings(models.Model):
    project=models.OneToOneField(Project,on_delete=models.CASCADE,related_name='preferences')
    guidelines=models.TextField(default='Gán nhãn theo ý nghĩa toàn câu. Phân biệt phê bình nội dung với công kích cá nhân. Không kết luận từ một từ khóa.')
    locked=models.BooleanField(default=False)
    archived=models.BooleanField(default=False)
    redundancy=models.PositiveSmallIntegerField(default=2)
    independent=models.BooleanField(default=True)
    active_model=models.ForeignKey('experiments.ModelRun',null=True,blank=True,on_delete=models.SET_NULL)
    active_connection=models.ForeignKey('integrations.ProviderConnection',null=True,blank=True,on_delete=models.SET_NULL)
class ProjectLabel(models.Model):
    project=models.ForeignKey(Project,on_delete=models.CASCADE,related_name='label_definitions')
    key=models.SlugField(max_length=64)
    name=models.CharField(max_length=120)
    description=models.TextField(blank=True)
    color=models.CharField(max_length=7,default='#4f78a5')
    enabled=models.BooleanField(default=True)
    order=models.PositiveSmallIntegerField(default=0)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['project','key'],name='studio_unique_project_label')]
        ordering=['order','id']
class ProjectInvitation(models.Model):
    project=models.ForeignKey(Project,on_delete=models.CASCADE,related_name='invitations')
    email=models.EmailField()
    token_hash=models.CharField(max_length=64,unique=True)
    role=models.CharField(max_length=20,default='annotator')
    invited_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='+')
    expires_at=models.DateTimeField()
    revoked=models.BooleanField(default=False)
    accepted_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL,related_name='+')
    accepted_at=models.DateTimeField(null=True)
    created_at=models.DateTimeField(auto_now_add=True)
