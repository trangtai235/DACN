from django.db import models
from core.models import Project
class ProviderConnection(models.Model):
    project=models.ForeignKey(Project,on_delete=models.CASCADE,related_name='connections')
    name=models.CharField(max_length=120)
    kind=models.CharField(max_length=24,choices=[('gemini','Gemini'),('openai_compatible','OpenAI compatible'),('ollama','Ollama')])
    base_url=models.URLField(max_length=500)
    model=models.CharField(max_length=180)
    encrypted_key=models.TextField(blank=True)
    input_price=models.FloatField(default=0)
    output_price=models.FloatField(default=0)
    enabled=models.BooleanField(default=True)
    model_ids=models.JSONField(default=list)
    builtin_key=models.CharField(max_length=40,blank=True,default='')
    check_status=models.CharField(max_length=12,default='unknown')
    check_code=models.CharField(max_length=40,blank=True)
    check_message=models.CharField(max_length=300,blank=True)
    checked_at=models.DateTimeField(null=True,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['project','builtin_key'],condition=~models.Q(builtin_key=''),name='unique_builtin_provider')]
