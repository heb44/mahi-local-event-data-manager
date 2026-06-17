from collections import defaultdict
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.http import HttpRequest, JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from ..forms import EventSchemaForm, EventSchemaPermissionsForm, EventSchemaStatusForm
from ..models import Checkpoint, CheckpointSchema, Event, EventSchema


@login_required
@require_GET
def event_schema(request: HttpRequest, event_id: int) -> HttpResponse:
    event = get_object_or_404(Event, id=event_id)
    queryset = EventSchema.objects.filter(event_id=event_id).order_by('-is_active', 'column_name')
    checkpoints = Checkpoint.objects.filter(path__event=event)

    checkpoint_schemas_prefetch = Prefetch(
        'cp_schemas',
        queryset=CheckpointSchema.objects.select_related('checkpoint__user'),
        to_attr='related_checkpoint_schemas',
    )

    queryset = queryset.prefetch_related(checkpoint_schemas_prefetch)
    event_schemas = []
    for schema_instance in queryset:
        access_dict: dict[str, set[Any]] = defaultdict(set)
        for schema in schema_instance.related_checkpoint_schemas:
            checkpoint = schema.checkpoint
            if schema.can_view:
                access_dict['view'].add(checkpoint)
            if schema.can_edit:
                access_dict['edit'].add(checkpoint)
            if schema.can_fill:
                access_dict['fill'].add(checkpoint)
        schema_instance.access_list = {
            'view': [
                {'id': checkpoint.id, 'name': checkpoint.name, 'user_name': checkpoint.user.username if checkpoint.user else None}
                for checkpoint in access_dict['view']
            ],
            'edit': [
                {'id': checkpoint.id, 'name': checkpoint.name, 'user_name': checkpoint.user.username if checkpoint.user else None}
                for checkpoint in access_dict['edit']
            ],
            'fill': [
                {'id': checkpoint.id, 'name': checkpoint.name, 'user_name': checkpoint.user.username if checkpoint.user else None}
                for checkpoint in access_dict['fill']
            ],
        }
        event_schemas.append(schema_instance)

    context = {
        'active_page': 'schema' if event.is_active else 'events',
        'event': event,
        'event_schemas': event_schemas,
        'checkpoints': checkpoints,
    }
    return render(request, 'core/event/event_schema.html', context=context)


@login_required
@require_POST
def event_schema_create(request: HttpRequest, event_id: int) -> HttpResponse:
    event = get_object_or_404(Event, id=event_id)
    form_data = request.POST.copy()
    form_data['event'] = event.id
    form = EventSchemaForm(form_data)
    permissions_form = EventSchemaPermissionsForm(request.POST, event=event)
    if not form.is_valid() or not permissions_form.is_valid():
        messages.error(request, form.errors.as_text() or permissions_form.errors.as_text())
        return redirect('events:schema', event_id)

    event_schema_instance = form.save()
    permissions_form.save(event_schema_instance)
    messages.success(request, 'فیلد ساختار با موفقیت ایجاد شد.')
    return redirect('events:schema', event_id)


@login_required
@require_http_methods(['GET', 'POST'])
def event_schema_edit(request: HttpRequest, event_id: int, schema_id: int) -> HttpResponse | JsonResponse:
    event = get_object_or_404(Event, id=event_id)
    event_schema_instance = get_object_or_404(EventSchema, id=schema_id, event=event)

    if request.method == 'GET':
        checkpoints = Checkpoint.objects.filter(path__event=event)
        permissions = CheckpointSchema.objects.filter(event_schema=event_schema_instance)
        response_data = {
            'column_name': event_schema_instance.column_name,
            'data_type': event_schema_instance.data_type,
            'is_required': event_schema_instance.is_required,
            'default_value': event_schema_instance.default_value or '',
            'is_active': event_schema_instance.is_active,
            'metadata_source': event_schema_instance.metadata_source or '',
            'metadata_key': event_schema_instance.metadata_key or '',
            'permissions': [
                {
                    'checkpoint_id': permission.checkpoint.id,
                    'checkpoint_name': permission.checkpoint.name,
                    'can_view': permission.can_view,
                    'can_edit': permission.can_edit,
                    'can_fill': permission.can_fill,
                }
                for permission in permissions
            ],
            'checkpoints': [{'id': checkpoint.id, 'name': checkpoint.name} for checkpoint in checkpoints],
        }
        return JsonResponse(response_data)

    form_data = request.POST.copy()
    form_data['event'] = event.id
    form = EventSchemaForm(form_data, instance=event_schema_instance)
    permissions_form = EventSchemaPermissionsForm(request.POST, event=event)
    if not form.is_valid() or not permissions_form.is_valid():
        messages.error(request, form.errors.as_text() or permissions_form.errors.as_text())
        return redirect('events:schema', event_id)

    event_schema_instance = form.save()
    permissions_form.save(event_schema_instance)
    messages.success(request, 'فیلد ساختار با موفقیت ویرایش شد.')
    return redirect('events:schema', event_id)


@login_required
@require_POST
def event_schema_delete(request: HttpRequest, event_id: int, schema_id: int) -> JsonResponse:
    event = get_object_or_404(Event, id=event_id)
    event_schema_instance = get_object_or_404(EventSchema, id=schema_id, event=event)
    event_schema_instance.delete()
    messages.success(request, f'فیلد ساختار «{event_schema_instance.column_name}» با موفقیت حذف شد.')
    return JsonResponse({'status': 'success', 'message': 'فیلد ساختار با موفقیت حذف شد.'})


@login_required
@require_POST
def toggle_event_schema_status(request: HttpRequest, event_id: int) -> HttpResponse:
    form = EventSchemaStatusForm(request.POST)
    if not form.is_valid():
        messages.error(request, form.errors.as_text())
        return redirect('events:schema', event_id)

    try:
        event_schema_instance = get_object_or_404(EventSchema, id=form.cleaned_data['id'])
        event_schema_instance.is_active = form.cleaned_data['active']
        event_schema_instance.save(update_fields=['is_active'])
        messages.success(request, 'وضعیت فیلد ساختار با موفقیت تغییر کرد.')
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect('events:schema', event_id)
