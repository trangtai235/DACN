"""Versioned sentence decisions. Predictions never become human gold implicitly."""
from django.conf import settings
from django.db import models
from core.models import Project, Comment, Prediction
from .automatic import AutoLabelRun
from .annotations import Annotation


class LabelSchema(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='label_schemas')
    version = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    snapshot = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['project', 'version'], name='unique_schema_version')]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError('Schema đã chụp là bất biến; tạo phiên bản mới.')
        return super().save(*args, **kwargs)


class PredictionPair(models.Model):
    run = models.ForeignKey(AutoLabelRun, on_delete=models.CASCADE, related_name='pairs')
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='prediction_pairs')
    text = models.TextField()
    context = models.TextField(blank=True)
    text_hash = models.CharField(max_length=64)
    local_prediction = models.ForeignKey(Prediction, null=True, on_delete=models.RESTRICT, related_name='+')
    api_prediction = models.ForeignKey(Prediction, null=True, on_delete=models.RESTRICT, related_name='+')
    branches = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['run', 'comment'], name='unique_pair_comment')]


class PairDecision(models.Model):
    clock = models.JSONField(default=dict)
    pair = models.ForeignKey(PredictionPair, on_delete=models.CASCADE, related_name='decisions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    annotation = models.ForeignKey(Annotation, null=True, on_delete=models.SET_NULL)
    schema = models.ForeignKey(LabelSchema, on_delete=models.RESTRICT)
    preliminary_label = models.CharField(max_length=64, blank=True)
    label = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=24, default='preliminary')
    note = models.TextField(blank=True)
    revision = models.PositiveIntegerField(default=0)
    exposed_at = models.DateTimeField(null=True)
    viewed_predictions = models.JSONField(default=list)
    history = models.JSONField(default=list)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['pair', 'user'], name='unique_pair_user_decision')]


class FeedbackApproval(models.Model):
    """Manager explicitly permits one frozen human decision for support/training."""
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE)
    schema = models.ForeignKey(LabelSchema, on_delete=models.RESTRICT)
    decision = models.OneToOneField(PairDecision, on_delete=models.RESTRICT)
    decision_revision = models.PositiveIntegerField(default=0)
    label = models.CharField(max_length=64)
    text = models.TextField()
    text_hash = models.CharField(max_length=64)
    source_id_snapshot = models.PositiveBigIntegerField()
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    approved_at = models.DateTimeField(auto_now_add=True)
    revoked = models.BooleanField(default=False)


class DataPartition(models.Model):
    comment = models.OneToOneField(Comment, on_delete=models.CASCADE, related_name='data_partition')
    role = models.CharField(max_length=16, default='support')


class FeedbackDataset(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='feedback_datasets')
    schema = models.ForeignKey(LabelSchema, on_delete=models.RESTRICT)
    seed = models.PositiveIntegerField(default=42)
    sha256 = models.CharField(max_length=64)
    snapshot = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
