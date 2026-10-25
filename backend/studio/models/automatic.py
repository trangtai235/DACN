from django.conf import settings
from django.db import models
from core.models import Project, Job


class AutoLabelRun(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='auto_label_runs')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    labels = models.JSONField(default=list)
    items = models.JSONField(default=list)
    model_config = models.JSONField(default=dict)
    connection_config = models.JSONField(default=dict)
    local_job = models.ForeignKey(Job, null=True, on_delete=models.SET_NULL, related_name='+')
    llm_job = models.ForeignKey(Job, null=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)


class AutoLabelResult(models.Model):
    run = models.ForeignKey(AutoLabelRun, on_delete=models.CASCADE, related_name='results')
    branch = models.CharField(max_length=8, choices=[('local', 'ML Local'), ('llm', 'LLM API')])
    item_index = models.PositiveIntegerField()
    label = models.CharField(max_length=64)
    spans = models.JSONField(default=list)
    latency_ms = models.FloatField(default=0)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    estimated_cost_usd = models.FloatField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['run', 'branch', 'item_index'], name='unique_auto_label_result')]
