from django.db import models
from django.contrib.auth.models import AbstractUser, Permission
from django.conf import settings

class User(AbstractUser):
    pass

class GlobalPermissions(Permission):
    class Meta:
        proxy = True
        permissions = [
            ("can_view_dashboard", "Can view the main dashboard"),
            ("can_export_user_data", "Can export user data"),
        ]

class UserSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='settings')
    
    ci_auto_submit = models.BooleanField(default=False)
    ci_auto_submit_delay = models.PositiveIntegerField(default=0)
    ci_auto_submit_char_num = models.PositiveIntegerField(default=0)
    
    use_persian_digits = models.BooleanField(default=False)
    enable_barcode_scanner = models.BooleanField(default=True)
    enable_audio_feedback = models.BooleanField(default=True)
    
    def __str__(self):
        return f"Settings for {self.user.username}"