import json
from itertools import groupby
from operator import attrgetter
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, F, OuterRef, Prefetch, Q, Subquery
from django.db.models.functions import Coalesce
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from ..forms import EventForm, EventStatusForm
from ..models import Checkpoint, Event, Path, PersonEventMetadata


@login_required
@require_GET
def events_list(request: HttpRequest) -> HttpResponse:
    events = Event.objects.order_by('-is_active', '-created_at').annotate(
        path_count=Coalesce(
            Subquery(Path.objects.filter(event=OuterRef('pk')).values('event').annotate(c=Count('id')).values('c')),
            0,
        ),
        participant_count=Coalesce(
            Subquery(
                PersonEventMetadata.objects.filter(
                    event=OuterRef('pk'),
                    deleted__isnull=True,
                    person__deleted__isnull=True,
                ).values('event').annotate(c=Count('id')).values('c')
            ),
            0,
        ),
    )
    context = {
        'active_page': 'events',
        'events': events,
    }
    return render(request, 'core/event/events_list.html', context=context)


@login_required
@require_POST
def event_create(request: HttpRequest) -> JsonResponse:
    form = EventForm(request.POST)
    if form.is_valid():
        event = form.save()
        messages.success(request, 'رویداد با موفقیت ایجاد شد.')
        return JsonResponse({'success': True, 'redirect': reverse('events:detail', args=[event.id])})
    return JsonResponse({'success': False, 'errors': form.errors}, status=400)


@login_required
@require_POST
def event_edit(request: HttpRequest, event_id: int) -> HttpResponse:
    event = get_object_or_404(Event, id=event_id)
    form = EventForm(request.POST, instance=event)
    if form.is_valid():
        form.save()
        messages.success(request, 'رویداد با موفقیت ویرایش شد.')
    else:
        messages.error(request, form.errors.as_text())
    return redirect('events:detail', event_id=event.id)


@login_required
@require_POST
def event_delete(request: HttpRequest, event_id: int) -> JsonResponse:
    try:
        event = get_object_or_404(Event, id=event_id)
        event.delete()
        return JsonResponse({'success': True, 'redirect': reverse('events:list')})
    except Exception as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=400)


@login_required
@require_GET
def event_detail(request: HttpRequest, event_id: int, mode: str = 'view') -> HttpResponse:
    event = get_object_or_404(
        Event.objects.prefetch_related(
            Prefetch(
                'paths',
                queryset=Path.objects.prefetch_related(
                    Prefetch('checkpoints', queryset=Checkpoint.objects.order_by('order'))
                ),
            )
        ),
        id=event_id,
    )

    participants_count = event.pems.filter(person__deleted__isnull=True).count()
    all_paths = event.paths.all()
    total_paths_count = all_paths.count()
    active_paths_count = all_paths.filter(is_active=True).count()
    paths_percentage = round((active_paths_count / total_paths_count) * 100) if total_paths_count > 0 else 0

    checkpoint_filter = Q(path__event_id=event.id)
    total_checkpoints_count = Checkpoint.objects.filter(checkpoint_filter).count()
    active_checkpoints_count = Checkpoint.objects.filter(
        checkpoint_filter,
        path__is_active=True,
        is_active=True,
    ).count()
    checkpoints_percentage = (
        round((active_checkpoints_count / total_checkpoints_count) * 100) if total_checkpoints_count > 0 else 0
    )

    active_paths_data: list[dict[str, Any]] = []
    inactive_paths_data: list[dict[str, Any]] = []
    for path in all_paths.order_by('name'):
        checkpoints = path.checkpoints.order_by('order')
        checkpoints_grouped = [list(group) for _, group in groupby(checkpoints, key=attrgetter('order'))]
        path_data = {'path': path, 'checkpoints': checkpoints_grouped}
        if path.is_active:
            active_paths_data.append(path_data)
        else:
            inactive_paths_data.append(path_data)

    from operations.models import CheckIn
    checkins = CheckIn.objects.filter(checkpoint__path__event=event)
    total_checkins_count = checkins.count()
    approved_checkins_count = checkins.filter(is_approved=True).count()
    not_approved_checkins_count = checkins.filter(is_approved=False).count()
    approved_checkins_percentage = round((approved_checkins_count / total_checkins_count) * 100) if total_checkins_count > 0 else 0
    recent_checkins = checkins.select_related('person', 'checkpoint', 'user').order_by('-timestamp')[:10]

    context = {
        'active_page': 'events',
        'event': event,
        'active_paths': active_paths_data,
        'inactive_paths': inactive_paths_data,
        'participants_count': participants_count,
        'total_paths_count': total_paths_count,
        'active_paths_count': active_paths_count,
        'paths_percentage': paths_percentage,
        'total_checkpoints_count': total_checkpoints_count,
        'active_checkpoints_count': active_checkpoints_count,
        'checkpoints_percentage': checkpoints_percentage,
        'mode': mode,
        'recent_checkins': recent_checkins,
        'total_checkins_count': total_checkins_count,
        'approved_checkins_count': approved_checkins_count,
        'not_approved_checkins_count': not_approved_checkins_count,
        'approved_checkins_percentage': approved_checkins_percentage,
    }
    return render(request, 'core/event/event_detail.html', context)


@login_required
@require_POST
def toggle_event_status(request: HttpRequest) -> JsonResponse:
    try:
        data = json.loads(request.body)
        form = EventStatusForm(data)
        if not form.is_valid():
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)

        event = get_object_or_404(Event, id=form.cleaned_data['event_id'])
        action = form.cleaned_data['action']
        if action == 'pause':
            event.is_active = False
            event.last_stop_time = timezone.now()
            event.save(update_fields=['is_active', 'last_stop_time'])
        else:
            event.is_active = True
            event.last_start_time = timezone.now()
            event.save(update_fields=['is_active', 'last_start_time'])

        new_event = Event.objects.filter(is_active=True).first()
        if not new_event:
            new_event = Event.objects.order_by(F('last_stop_time').desc(nulls_last=True)).first()

        return JsonResponse(
            {
                'success': True,
                'event': {
                    'id': new_event.id if new_event else None,
                    'name': new_event.name if new_event else 'No active event',
                    'is_active': new_event.is_active if new_event else False,
                    'last_start_time': (
                        timezone.localtime(new_event.last_start_time).strftime('%Y-%m-%d %H:%M')
                        if new_event and new_event.last_start_time
                        else ''
                    ),
                    'last_stop_time': (
                        timezone.localtime(new_event.last_stop_time).strftime('%Y-%m-%d %H:%M')
                        if new_event and new_event.last_stop_time
                        else ''
                    ),
                },
            }
        )
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=400)
