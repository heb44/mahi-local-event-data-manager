from django.contrib import admin
from .models import GlobalSettings

@admin.register(GlobalSettings)
class GlobalSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False