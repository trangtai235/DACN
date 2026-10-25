from django.db import models
from django.conf import settings
from core.models import Project,Comment,LABELS
class ReviewRun(models.Model):
    project=models.ForeignKey(Project,on_delete=models.CASCADE,related_name='review_runs')
    policy=models.CharField(max_length=20,default='adaptive')
    budget_seconds=models.PositiveIntegerField(default=1800)
    used_seconds=models.FloatField(default=0)
    seed=models.PositiveIntegerField(default=42)
    population=models.TextField(default='[]')
    state=models.CharField(max_length=20,default='active')
    created_at=models.DateTimeField(auto_now_add=True)
class ReviewTask(models.Model):
    run=models.ForeignKey(ReviewRun,on_delete=models.CASCADE,related_name='tasks')
    comment=models.ForeignKey(Comment,on_delete=models.PROTECT)
    reviewer=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='review_tasks')
    blind_label=models.CharField(max_length=16,choices=LABELS,null=True)
    final_label=models.CharField(max_length=16,choices=LABELS,null=True)
    note=models.TextField(blank=True)
    state=models.CharField(max_length=30,default='claimed')
    reason=models.CharField(max_length=160)
    review_seconds=models.FloatField(default=0)
    adjudication_seconds=models.FloatField(default=0)
    adjudicator=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,null=True,related_name='adjudications')
    created_at=models.DateTimeField(auto_now_add=True)
    adjudication_started_at=models.DateTimeField(null=True)
    completed_at=models.DateTimeField(null=True)
    class Meta:constraints=[models.UniqueConstraint(fields=['run','comment'],name='unique_run_comment_task')]
