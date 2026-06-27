import json
from collections import defaultdict
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, F, Prefetch
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from accounts.models import User, UserSettings
from events.models import Checkpoint, Event, EventSchema, Path, PersonEventMetadata
from people.models import Person
from people.services import PersonFilterService

from .forms import CheckInBulkActionForm, CheckInPerformForm, CheckInSearchForm
from .models import CheckIn, CheckInData
from .services import CheckInWorkflowService, filter_sort_paginate_checkins, prefetch_checkin_data_for_persons


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    active_event = Event.objects.filter(is_active=True).first()
    if not active_event:
        active_event = Event.objects.order_by(F('last_stop_time').desc(nulls_last=True)).first()

    user_settings, _ = UserSettings.objects.get_or_create(user=request.user)
    limit = user_settings.dashboard_event_count
    latest_checkins = CheckIn.objects.select_related('person', 'checkpoint').order_by('-timestamp')[:limit]

    stats = {
        'connected_users': User.objects.filter(is_active=True).count(),
        'person_count': Person.objects.count(),
        'event_count': Event.objects.count(),
        'path_count': Path.objects.count(),
        'active_event': Event.objects.filter(is_active=True).count() or 2,
    }

    if active_event:
        active_paths = Path.objects.filter(
            event=active_event,
            is_active=True
        ).prefetch_related(
            Prefetch('checkpoints', queryset=Checkpoint.objects.filter(is_active=True).order_by('order'))
        ).annotate(checkpoint_count=Count('checkpoints'))
    else:
        active_paths = Path.objects.none()

    map_paths = []
    for path in active_paths:
        path_data = {'name': path.name, 'points': []}
        for cp in path.checkpoints.all():
            if cp.latitude and cp.longitude:
                path_data['points'].append({
                    'lat': float(cp.latitude),
                    'lng': float(cp.longitude),
                    'popup': f'{cp.name} ({path.name})',
                    'color': cp.color or '#4F46E5',
                    'order': cp.order
                })
        if path_data['points']:
            map_paths.append(path_data)

    context = {
        'active_page': 'dashboard',
        'active_event': active_event,
        'latest_checkins': latest_checkins,
        'event_display_duration_ms': user_settings.dashboard_event_display_duration * 1000,
        'stats': stats,
        'active_paths': active_paths,
        'map_paths': map_paths,
    }
    return render(request, 'core/dashboard.html', context)


@login_required
@require_GET
def checkins_list(request: HttpRequest) -> HttpResponse:
    base_qs = CheckIn.objects.select_related(
        'person',
        'checkpoint',
        'checkpoint__path',
        'checkpoint__path__event',
        'user',
    ).prefetch_related(
        Prefetch(
            'data',
            queryset=CheckInData.objects.select_related('event_schema').order_by('event_schema__column_name'),
            to_attr='prefetched_data_list',
        )
    )

    context = filter_sort_paginate_checkins(request, base_qs, page_size=20)
    context['active_page'] = 'checkins'
    context['all_events'] = Event.objects.order_by('name')
    context['all_checkpoints'] = Checkpoint.objects.select_related('path__event').order_by('path__event__name', 'name')
    context['all_users'] = User.objects.filter(is_active=True).order_by('username')
    return render(request, 'core/checkin/checkins_list.html', context)


@login_required
def checkin(request: HttpRequest) -> HttpResponse:
    event = Event.objects.filter(is_active=True).first()
    if not event:
        return render(request, 'core/checkin/checkin_inactive.html', {'active_page': 'checkin'})

    user = request.user
    base_qs = Person.objects.filter(events=event).prefetch_related(
        Prefetch(
            'pems',
            queryset=PersonEventMetadata.objects.filter(event=event),
            to_attr='event_pems',
        )
    )

    context = PersonFilterService.filter_sort_paginate(request, base_qs, page_size=4)
    extra_columns = EventSchema.objects.with_user_permissions(event, user)
    persons_on_page_with_data = prefetch_checkin_data_for_persons(
        persons_qs=context['page_obj'].object_list,
        event=event,
        user=user,
        extra_columns=extra_columns,
    )
    context['page_obj'].object_list = persons_on_page_with_data

    for person in context['page_obj']:
        person.metadata_json = json.dumps(person.metadata, ensure_ascii=False)
        for item in person.event_pems:
            item.data_json = json.dumps(item.data, ensure_ascii=False) if item.data else '{}'

    user_settings, _ = UserSettings.objects.get_or_create(user=user)
    context.update(
        {
            'active_page': 'checkin',
            'event': event,
            'user_settings': user_settings,
            'check_points': Checkpoint.objects.select_related('path').filter(
                user=user,
                is_active=True,
                path__is_active=True,
                path__event=event,
            ),
            'extra_columns': extra_columns,
        }
    )
    return render(request, 'core/checkin/checkin.html', context)


@login_required
@require_POST
def checkin_search(request: HttpRequest) -> HttpResponse:
    messages_list: list[tuple[str, str]] = []
    form = CheckInSearchForm(request.POST)
    if not form.is_valid():
        messages_list.append(('error', form.errors.as_text()))
        return render(request, 'core/checkin/checkin_result.html', {'msgs': messages_list})

    try:
        result = CheckInWorkflowService.search(
            person_id=form.cleaned_data['id'],
            checkpoint_id=form.cleaned_data['cp_id'],
            user=request.user,
        )
    except (Checkpoint.DoesNotExist, Person.DoesNotExist, ValueError, TypeError):
        return render(
            request,
            'core/checkin/checkin_result.html',
            {'msgs': [('error', 'شخص یا چک‌پوینت نامعتبر است.')]},
        )

    if not result['ok']:
        return render(request, 'core/checkin/checkin_result.html', {'msgs': result['msgs']})
    return render(request, 'core/checkin/checkin_result.html', result['context'])


@login_required
@require_POST
def checkin_perform(request: HttpRequest) -> HttpResponse:
    messages_list: list[tuple[str, str]] = []
    base_form = CheckInPerformForm(request.POST)
    if not base_form.is_valid():
        messages_list.extend(('error', error) for error in base_form.non_field_errors())
        for field_name, field_errors in base_form.errors.items():
            if field_name == '__all__':
                continue
            messages_list.extend(('error', error) for error in field_errors)
        return render(request, 'core/checkin/checkin_result.html', {'msgs': messages_list})

    check_in = get_object_or_404(
        CheckIn.objects.select_related('checkpoint__path__event', 'person'),
        id=base_form.cleaned_data['ci'],
        user=request.user,
        pending=True,
    )

    person = check_in.person
    event = check_in.checkpoint.path.event
    form = CheckInPerformForm(request.POST, event=event, user=request.user)

    if event.deleted is not None or not event.is_active:
        return render(request, 'core/checkin/checkin_result.html', {'msgs': [('error', 'رویداد فعال یا معتبر نیست.')]})

    if person.deleted is not None:
        return render(request, 'core/checkin/checkin_result.html', {'msgs': [('error', 'شخص حذف شده است.')]})

    if not form.is_valid():
        messages_list.extend(('error', error) for error in form.non_field_errors())
        for field_name, field_errors in form.errors.items():
            if field_name == '__all__':
                continue
            messages_list.extend(('error', error) for error in field_errors)
        latest_checkins = CheckIn.objects.filter(checkpoint=check_in.checkpoint, user=request.user, pending=False).select_related(
            'person'
        ).order_by('-timestamp')[:3]
        return render(
            request,
            'core/checkin/checkin_result.html',
            {'msgs': messages_list, 'latest_checkins': latest_checkins},
        )

    result = CheckInWorkflowService.perform(ci=check_in, user=request.user, form=form)
    latest_checkins = result.get('latest_checkins') or CheckIn.objects.filter(
        checkpoint=check_in.checkpoint,
        user=request.user,
        pending=False,
    ).select_related('person').order_by('-timestamp')[:3]
    context = {'msgs': result['msgs'], 'latest_checkins': latest_checkins}
    return render(request, 'core/checkin/checkin_result.html', context=context)


@login_required
@require_POST
def checkin_delete(request: HttpRequest, checkin_id: int) -> JsonResponse:
    try:
        checkin = get_object_or_404(CheckIn, id=checkin_id)
        checkin.delete()
        messages.success(request, f'چک‌این {checkin_id} با موفقیت حذف شد.')
        return JsonResponse({'success': True, 'message': 'حذف شد.'})
    except Exception as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=500)


@login_required
@require_POST
def checkin_bulk_action(request: HttpRequest) -> HttpResponse:
    form = CheckInBulkActionForm(request.POST)
    if not form.is_valid():
        messages.error(request, form.errors.as_text())
        return redirect('operations:checkins')

    if form.cleaned_data['action'] == 'delete':
        try:
            checkins_to_delete = form.cleaned_data['selected_ids']
            checkin_ids = list(checkins_to_delete.values_list('id', flat=True))
            if checkin_ids:
                checkins_to_delete.delete()
                messages.success(request, f'{len(checkin_ids)} چک‌این با موفقیت حذف شدند.')
            else:
                messages.warning(request, 'هیچ چک‌این معتبری برای حذف یافت نشد.')
        except Exception as exc:
            messages.error(request, f'Error: {exc}')

    return redirect('operations:checkins')


@login_required
def person_checkin_history(request: HttpRequest, person_id: int) -> HttpResponse:
    person = get_object_or_404(Person, pk=person_id)
    view_mode = request.GET.get('view', 'graph')
    context: dict[str, Any] = {
        'person': person,
        'view': view_mode,
    }

    if view_mode == 'graph':
        checkins_qs = CheckIn.objects.filter(person=person).select_related('checkpoint__path__event', 'user').order_by(
            'checkpoint__path__event_id',
            'timestamp',
        )

        grouped_checkins: dict[Any, list[CheckIn]] = defaultdict(list)
        for checkin in checkins_qs:
            grouped_checkins[checkin.checkpoint.path.event].append(checkin)

        event_checkins_data = []
        for event, checkins in grouped_checkins.items():
            if checkins:
                event_checkins_data.append(
                    {
                        'event': event,
                        'checkins': checkins,
                        'first_checkin_time': checkins[0].timestamp,
                        'last_checkin_time': checkins[-1].timestamp,
                    }
                )

        context['event_checkins'] = event_checkins_data
    else:
        base_queryset = CheckIn.objects.filter(person=person).select_related('checkpoint__path__event', 'user', 'person')
        table_data = filter_sort_paginate_checkins(request, base_queryset)
        context.update(table_data)
        context['all_events'] = Event.objects.order_by('name')
        context['all_checkpoints'] = Checkpoint.objects.select_related('path__event').order_by('path__event__name', 'order')

    return render(request, 'core/checkin/checkin_history.html', context)
