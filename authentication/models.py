from django.db import models
from django.contrib.auth.models import User
# Create your models here.
class SupabaseUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    supabase_id = models.CharField(max_length=255, unique=True)
    email_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.email} - {self.supabase_id}"