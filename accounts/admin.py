from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, UserSettings, GlobalPermissions

class UserSettingsInline(admin.StackedInline):
    model = UserSettings
    can_delete = False
    verbose_name_plural = 'تنظیمات شخصی کاربر'

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = (UserSettingsInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_active', 'is_staff')
    list_filter = ('is_active', 'is_staff', 'groups')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('username',)

@admin.register(GlobalPermissions)
class GlobalPermissionsAdmin(admin.ModelAdmin):
    pass