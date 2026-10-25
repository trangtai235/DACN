from django.db import models
from django.conf import settings
class UserProfile(models.Model):
    user=models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='studio_profile')
    language=models.CharField(max_length=2,default='vi')
    email_verified=models.BooleanField(default=False)
    youtube_key=models.TextField(blank=True)
