from django.contrib import admin
from safedelete.admin import SafeDeleteAdmin

from .models import Person

@admin.register(Person)
class PersonAdmin(SafeDeleteAdmin):
    list_display = ('id', 'name', 'last_name', 'phone_number', 'birth_date', 'deleted')
    list_filter = ('deleted', 'events')
    search_fields = ('name', 'last_name', 'phone_number', 'metadata')
    readonly_fields = ('history_records',)

    actions = ['soft_delete_persons']

    def history_records(self, obj):
        return "تاریخچه تغییرات در دیتابیس ذخیره شده است."

    @admin.action(description='حذف نرم (Soft Delete) موارد انتخاب شده')
    def soft_delete_persons(self, request, queryset):
        queryset.delete()
