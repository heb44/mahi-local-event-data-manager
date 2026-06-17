from django.db import models

class GlobalSettings(models.Model):

    max_upload_size_mb = models.IntegerField(default=10, verbose_name="حداکثر حجم آپلود (مگابایت)")

    def save(self, *args, **kwargs):
        self.pk = 1  
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    class Meta:
        verbose_name = "تنظیمات سیستم"
        verbose_name_plural = "تنظیمات سیستم"

