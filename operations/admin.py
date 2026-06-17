from django.contrib import admin
from .models import CheckIn, CheckInData

class CheckInDataInline(admin.TabularInline):
    model = CheckInData
    extra = 0
    readonly_fields = ('created_at',)
    can_delete = False
    
    # نمایش مقدار واقعی به جای فیلدهای جداگانه (اختیاری برای خوانایی)
    def get_value_display(self, obj):
        return obj.get_value()
    get_value_display.short_description = "Value"

@admin.register(CheckIn)
class CheckInAdmin(admin.ModelAdmin):
    list_display = ('person', 'checkpoint_name', 'user', 'timestamp', 'is_valid', 'is_approved', 'pending')
    list_filter = (
        'is_valid', 'is_approved', 'pending',
        'checkpoint__path__event', # فیلتر بر اساس ایونت
        'timestamp'
    )
    search_fields = ('person__name', 'person__last_name', 'user__username', 'description')
    date_hierarchy = 'timestamp' # نوار پیمایش تاریخ در بالای صفحه
    raw_id_fields = ('person', 'user', 'checkpoint') # حیاتی برای سرعت
    inlines = [CheckInDataInline]

    def checkpoint_name(self, obj):
        return f"{obj.checkpoint.name} ({obj.checkpoint.path.event.name})"
    checkpoint_name.short_description = "Checkpoint"

@admin.register(CheckInData)
class CheckInDataAdmin(admin.ModelAdmin):
    """
    معمولاً داده‌ها را از طریق CheckIn می‌بینیم، اما این برای جستجوی مستقیم در داده‌هاست.
    """
    list_display = ('check_in', 'event_schema', 'get_value_preview', 'created_at')
    list_filter = ('event_schema__data_type', 'event_schema__event')
    search_fields = ('text_value', 'check_in__person__last_name')
    raw_id_fields = ('check_in', 'event_schema')

    def get_value_preview(self, obj):
        val = obj.get_value()
        return str(val)[:50] + "..." if len(str(val)) > 50 else val
    get_value_preview.short_description = "Value"