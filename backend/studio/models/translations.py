from django.db import models
from core.models import Comment


class CommentTranslation(models.Model):
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='translations')
    text_hash = models.CharField(max_length=64)
    target_language = models.CharField(max_length=8, default='vi')
    status = models.CharField(max_length=16, default='running')
    request_token = models.CharField(max_length=36)
    provider = models.JSONField(default=dict)
    translated_text = models.TextField(blank=True)
    error = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['comment', 'text_hash', 'target_language'], name='unique_comment_translation')]
