import json
from typing import Any

import pandas as pd
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from people.models import Person
from people.services import PersonImportService, PersonFilterService

from ..forms import ParticipantBulkActionForm, ParticipantForm, ParticipantImportForm
from ..models import Event, EventSchema, PersonEventMetadata


def add_person_to_event(event: Event, person: Person, data: dict[str, Any] | None = None) -> PersonEventMetadata:
    defaults: dict[str, Any] = {}
    if data is not None:
        defaults['data'] = data
    pem, _ = PersonEventMetadata.objects.update_or_create(
        person=person,
        event=event,
        defaults=defaults,
    )
    return pem


@login_required
@require_GET
def participants_list(request: HttpRequest, event_id: int) -> HttpResponse:
    event = get_object_or_404(Event, id=event_id)
    base_qs = Person.objects.filter(pems__event=event, pems__deleted__isnull=True).distinct().prefetch_related(
        Prefetch(
            'pems',
            queryset=PersonEventMetadata.objects.filter(event=event),
            to_attr='event_pems',
        )
    )

    context = PersonFilterService.filter_sort_paginate(request, base_qs, page_size=10)
    extra_columns = EventSchema.objects.with_user_permissions(event, request.user)

    for person in context['page_obj']:
        person.metadata_json = json.dumps(person.metadata, ensure_ascii=False)
        for item in person.event_pems:
            item.data_json = json.dumps(item.data, ensure_ascii=False) if item.data else '{}'

    context['active_page'] = 'participants' if event.is_active else 'events'
    context['event'] = event
    context['extra_columns'] = extra_columns
    return render(request, 'core/event/participants_list.html', context)


@login_required
@require_POST
def participant_bulk_action(request: HttpRequest, event_id: int) -> HttpResponse:
    event = get_object_or_404(Event, id=event_id)
    form = ParticipantBulkActionForm(request.POST)
    if not form.is_valid():
        messages.error(request, form.errors.as_text())
        return redirect('events:participants', event_id=event_id)

    participants = form.cleaned_data['participant_ids']
    if form.cleaned_data['action'] == 'delete':
        removed_count, _ = PersonEventMetadata.objects.filter(event=event, person__in=participants).delete()
        messages.success(request, f'{removed_count} شرکت‌کننده با موفقیت حذف شد.')
    elif form.cleaned_data['action'] == 'add':
        added_count = participants.count()
        for participant in participants:
            PersonEventMetadata.objects.update_or_create(person=participant, event=event, defaults={})
        messages.success(request, f'{added_count} شرکت‌کننده با موفقیت اضافه شد.')

    return redirect('events:participants', event_id=event_id)


@login_required
@require_POST
def participant_delete(request: HttpRequest, event_id: int, participant_id: int) -> JsonResponse:
    try:
        event = get_object_or_404(Event, id=event_id)
        participant = get_object_or_404(Person, id=participant_id)
        PersonEventMetadata.objects.filter(event=event, person=participant).delete()
        messages.success(request, 'شرکت‌کننده با موفقیت حذف شد.')
        return JsonResponse({'success': True, 'status': 200})
    except Exception as exc:
        messages.error(request, f'خطا در حذف شرکت‌کننده: {exc}')
        return JsonResponse({'success': False, 'status': 500, 'error': str(exc)})


@login_required
@require_GET
def participant_add(request: HttpRequest, event_id: int) -> HttpResponse:
    event = get_object_or_404(Event, id=event_id)
    base_qs = Person.objects.exclude(pems__event=event)
    context = PersonFilterService.filter_sort_paginate(request, base_qs, page_size=10)
    context['active_page'] = 'events'
    context['event'] = event
    return render(request, 'core/event/add_participant.html', context)


@login_required
@require_POST
def participant_create(request: HttpRequest, event_id: int) -> HttpResponse:
    event = get_object_or_404(Event, id=event_id)
    form = ParticipantForm(request.POST)
    if form.is_valid():
        person = form.save()
        add_person_to_event(event, person, form.cleaned_data['pem'])
        messages.success(request, 'شرکت‌کننده با موفقیت ایجاد و به رویداد اضافه شد.')
    else:
        messages.error(request, form.errors.as_text())
    return redirect('events:participants', event_id=event_id)


@login_required
@require_POST
def participant_edit(request: HttpRequest, event_id: int, participant_id: int) -> HttpResponse:
    event = get_object_or_404(Event, id=event_id)
    participant = get_object_or_404(Person, id=participant_id)
    form = ParticipantForm(request.POST, instance=participant)
    if not form.is_valid():
        messages.error(request, form.errors.as_text())
        return redirect('events:participants', event_id=event.id)

    participant = form.save()
    add_person_to_event(event, participant, form.cleaned_data['pem'])
    messages.success(request, 'اطلاعات شرکت‌کننده با موفقیت ویرایش شد.')
    return redirect('events:participants', event_id=event.id)


@login_required
@require_http_methods(['GET', 'POST'])
def import_persons_to_event(request: HttpRequest, event_id: int) -> HttpResponse:
    event = get_object_or_404(Event, id=event_id)
    person_fields = ['name', 'last_name', 'phone_number', 'birth_date']
    field_verbose = {
        'name': 'Name',
        'last_name': 'Last Name',
        'phone_number': 'Phone Number',
        'birth_date': 'Birth Date',
    }
    max_file_size = getattr(settings, 'MAX_UPLOAD_SIZE', 5 * 1024 * 1024)
    max_rows = getattr(settings, 'MAX_EXCEL_ROWS', 1000)

    context = {
        'event': event,
        'person_fields': person_fields,
        'field_verbose': field_verbose,
        'max_file_size': max_file_size,
        'max_rows': max_rows,
        'form_data': request.POST if request.method == 'POST' else {},
    }

    if request.method == 'POST':
        form = ParticipantImportForm(request.POST, request.FILES, max_file_size=max_file_size)
        if not form.is_valid():
            messages.error(request, form.errors.as_text())
            context['errors'] = [error['message'] for errors in form.errors.get_json_data().values() for error in errors]
            return render(request, 'core/event/import_persons.html', context)

        excel_file = form.cleaned_data['excel_file']
        column_mapping = {field: form.cleaned_data.get(f'{field}_column') for field in person_fields}
        matching_fields = form.cleaned_data['matching_fields']
        metadata_storage = form.cleaned_data['metadata_storage']
        errors: list[str] = []
        new_persons = 0
        updated_persons = 0

        try:
            df = pd.read_excel(excel_file)
            if len(df) > max_rows:
                messages.error(request, f'تعداد ردیف‌های فایل از حد مجاز بیشتر است. حداکثر {max_rows} ردیف مجاز است.')
                context['errors'] = [f'تعداد ردیف‌های فایل از حد مجاز بیشتر است. حداکثر {max_rows} ردیف مجاز است.']
                return render(request, 'core/event/import_persons.html', context)

            for field, column in column_mapping.items():
                if column and column not in df.columns:
                    errors.append(f"Column '{column}' for field '{field_verbose.get(field, field)}' not found.")

            if errors:
                context['errors'] = errors
                return render(request, 'core/event/import_persons.html', context)

            def metadata_handler(person: Person, metadata: dict[str, str]) -> None:
                if metadata_storage == 'person' and metadata:
                    person.metadata.update(metadata)
                    person.save()
                    add_person_to_event(event, person)
                elif metadata_storage == 'person_event' and metadata:
                    person.save()
                    add_person_to_event(event, person, metadata)
                else:
                    person.save()
                    add_person_to_event(event, person)

            result = PersonImportService.import_dataframe(
                df,
                column_mapping,
                matching_fields,
                metadata_handler=metadata_handler,
            )
            errors = result['errors']
            new_persons = result['new_persons']
            updated_persons = result['updated_persons']

            if errors:
                messages.warning(
                    request,
                    f'وارد کردن اطلاعات با خطاهای جزئی انجام شد. {new_persons} شخص جدید ایجاد شد و {updated_persons} شخص به‌روزرسانی شد.',
                )
                context['errors'] = errors
            else:
                messages.success(
                    request,
                    f'وارد کردن اطلاعات با موفقیت انجام شد. {new_persons} شخص جدید ایجاد شد و {updated_persons} شخص به‌روزرسانی شد.',
                )
        except Exception:
            messages.error(request, 'در پردازش فایل خطا رخ داد. لطفاً از معتبر بودن فایل اطمینان حاصل کنید.')
            context['errors'] = ['در پردازش فایل خطا رخ داد.']
            return render(request, 'core/event/import_persons.html', context)

        return render(request, 'core/event/import_persons.html', context)

    return render(request, 'core/event/import_persons.html', context)


@login_required
@require_GET
def participants_redirect(request: HttpRequest) -> HttpResponse:
    event = Event.objects.filter(is_active=True).first()
    if not event:
        return render(request, 'core/event/participants_inactive.html', {'active_page': 'participants'})
    return redirect('events:participants', event_id=event.id)


@login_required
@require_GET
def schema_redirect(request: HttpRequest) -> HttpResponse:
    event = Event.objects.filter(is_active=True).first()
    if not event:
        return render(request, 'core/event/schema_inactive.html', {'active_page': 'schema'})
    return redirect('events:schema', event_id=event.id)
