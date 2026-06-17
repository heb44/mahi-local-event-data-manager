import json

import pandas as pd
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from .forms import PersonBulkActionForm, PersonForm, PersonImportForm
from .models import Person
from .services import PersonImportService, PersonFilterService


@login_required
@require_GET
def persons_list(request: HttpRequest) -> HttpResponse:
    base_qs = Person.objects.annotate(events_num=Count('events'))
    context = PersonFilterService.filter_sort_paginate(request, base_qs, page_size=10)

    for person in context['page_obj']:
        person.metadata_json = json.dumps(person.metadata, ensure_ascii=False)

    context['active_page'] = 'persons'
    return render(request, 'core/persons_list.html', context)


@login_required
@require_POST
def person_bulk_action(request: HttpRequest) -> HttpResponse:
    form = PersonBulkActionForm(request.POST)
    if not form.is_valid():
        messages.error(request, form.errors.as_text())
        return redirect('people:list')

    if form.cleaned_data['action'] == 'delete':
        deleted_count, _ = form.cleaned_data['person_ids'].delete()
        messages.success(request, f'{deleted_count} شخص با موفقیت حذف شد.')
    return redirect('people:list')


@login_required
def person_delete(request: HttpRequest, person_id: int) -> JsonResponse:
    if request.method == 'POST':
        try:
            get_object_or_404(Person, id=person_id).delete()
            messages.success(request, f'شخص با شناسه «{person_id}» با موفقیت حذف شد.')
            return JsonResponse({'success': True, 'status': 200})
        except Exception as exc:
            messages.error(request, str(exc))
            return JsonResponse({'success': False, 'status': 500})
    return JsonResponse({'success': False, 'error': 'درخواست نامعتبر است.'}, status=405)


@login_required
@require_POST
def person_create(request: HttpRequest) -> HttpResponse:
    form = PersonForm(request.POST)
    if form.is_valid():
        person = form.save()
        messages.success(request, f'شخص با شناسه «{person.id}» با موفقیت ایجاد شد.')
    else:
        messages.error(request, form.errors.as_text())
    return redirect('people:list')


@login_required
@require_POST
def person_edit(request: HttpRequest, person_id: int) -> HttpResponse:
    person = get_object_or_404(Person, id=person_id)
    form = PersonForm(request.POST, instance=person)
    if form.is_valid():
        person = form.save()
        messages.success(request, f'شخص با شناسه «{person.id}» با موفقیت ویرایش شد.')
    else:
        messages.error(request, form.errors.as_text())
    return redirect('people:list')


@login_required
def import_persons_general(request: HttpRequest) -> HttpResponse:
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
        'active_page': 'persons',
        'person_fields': person_fields,
        'field_verbose': field_verbose,
        'max_file_size': max_file_size,
        'max_rows': max_rows,
        'form_data': request.POST if request.method == 'POST' else {},
    }

    if request.method == 'POST':
        form = PersonImportForm(request.POST, request.FILES, max_file_size=max_file_size)
        if not form.is_valid():
            messages.error(request, form.errors.as_text())
            context['errors'] = [error['message'] for errors in form.errors.get_json_data().values() for error in errors]
            return render(request, 'core/import_persons_general.html', context)

        excel_file = form.cleaned_data['excel_file']
        column_mapping = {field: form.cleaned_data.get(f'{field}_column') for field in person_fields}
        matching_fields = form.cleaned_data['matching_fields']
        errors: list[str] = []
        new_persons = 0
        updated_persons = 0

        try:
            df = pd.read_excel(excel_file)
            if len(df) > max_rows:
                messages.error(request, f'تعداد ردیف‌های فایل از حد مجاز بیشتر است. حداکثر {max_rows} ردیف مجاز است.')
                context['errors'] = [f'تعداد ردیف‌های فایل از حد مجاز بیشتر است. حداکثر {max_rows} ردیف مجاز است.']
                return render(request, 'core/import_persons_general.html', context)

            for field, column in column_mapping.items():
                if column and column not in df.columns:
                    errors.append(f"Column '{column}' for field '{field_verbose.get(field, field)}' not found in file.")

            if errors:
                context['errors'] = errors
                return render(request, 'core/import_persons_general.html', context)

            result = PersonImportService.import_dataframe(df, column_mapping, matching_fields)
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
            return render(request, 'core/import_persons_general.html', context)

        return render(request, 'core/import_persons_general.html', context)

    return render(request, 'core/import_persons_general.html', context)
