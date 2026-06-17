from django.contrib import admin
from safedelete.admin import SafeDeleteAdmin

from .models import Checkpoint, CheckpointSchema, Event, EventSchema, Path, PersonEventMetadata


class CheckpointInline(admin.TabularInline):
    model = Checkpoint
    extra = 0
    show_change_link = True
    fields = ('name', 'order', 'is_active', 'is_mandatory')


class CheckpointSchemaInline(admin.TabularInline):
    model = CheckpointSchema
    extra = 0
    raw_id_fields = ('checkpoint',)


@admin.register(Event)
class EventAdmin(SafeDeleteAdmin):
    list_display = ('name', 'is_active', 'created_at', 'deleted')
    list_filter = ('is_active', 'deleted')
    search_fields = ('name', 'description')
    actions = ['activate_event', 'deactivate_event']

    @admin.action(description='فعال‌سازی رویداد')
    def activate_event(self, request, queryset):
        for event in queryset:
            event.is_active = True
            event.save()

    @admin.action(description='غیرفعال‌سازی رویداد')
    def deactivate_event(self, request, queryset):
        queryset.update(is_active=False)


@admin.register(Path)
class PathAdmin(SafeDeleteAdmin):
    list_display = ('name', 'event', 'is_active', 'enforce_checkpoint_order', 'deleted')
    list_filter = ('event', 'is_active', 'deleted')
    search_fields = ('name', 'event__name')
    inlines = [CheckpointInline]


@admin.register(Checkpoint)
class CheckpointAdmin(SafeDeleteAdmin):
    list_display = ('name', 'path', 'order', 'user', 'is_active', 'deleted')
    list_filter = ('path__event', 'is_active', 'is_mandatory', 'deleted')
    search_fields = ('name', 'path__name', 'user__username')
    raw_id_fields = ('user',)


@admin.register(EventSchema)
class EventSchemaAdmin(SafeDeleteAdmin):
    list_display = ('column_name', 'event', 'data_type', 'is_required', 'is_active', 'deleted')
    list_filter = ('event', 'data_type', 'is_active', 'deleted')
    inlines = [CheckpointSchemaInline]


@admin.register(PersonEventMetadata)
class PersonEventMetadataAdmin(SafeDeleteAdmin):
    list_display = ('person', 'event', 'updated_at', 'deleted')
    list_filter = ('event', 'deleted')
    search_fields = ('person__name', 'person__last_name', 'data')
    raw_id_fields = ('person', 'event')
