import json
from itertools import groupby
from operator import attrgetter

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Prefetch
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from ..forms import PathForm, PathStatusForm
from ..models import Checkpoint, Event, Path


@login_required
@require_GET
def paths_list(request: HttpRequest) -> HttpResponse:
    paths = Path.objects.select_related('event').annotate(cp_count=Count('checkpoints')).order_by(
        'event',
        '-is_active',
        'created_at',
    )
    paths_grouped = [list(group) for _, group in groupby(paths, key=attrgetter('event'))]
    events = Event.objects.only('name').order_by('name')
    context = {
        'paths_grouped': paths_grouped,
        'active_page': 'paths',
        'events': events,
    }
    return render(request, 'core/path/paths_list.html', context=context)


@login_required
@require_GET
def path_detail(request: HttpRequest, path_id: int) -> HttpResponse:
    path = get_object_or_404(
        Path.objects.select_related('event').prefetch_related(
            Prefetch('checkpoints', queryset=Checkpoint.objects.order_by('-is_active', 'order')),
            'checkpoints__user',
        ),
        id=path_id,
    )
    active_checkpoints = sorted([checkpoint for checkpoint in path.checkpoints.all() if checkpoint.is_active], key=lambda checkpoint: checkpoint.order)
    active_checkpoints_grouped = [list(group) for _, group in groupby(active_checkpoints, key=attrgetter('order'))]

    context = {
        'active_page': 'paths',
        'active_checkpoints': active_checkpoints_grouped,
        'path': path,
        'paths': Path.objects.only('name').order_by('name'),
        'events': Event.objects.only('name').order_by('name'),
    }
    return render(request, 'core/path/path_detail.html', context)


@login_required
@require_POST
def path_create(request: HttpRequest) -> HttpResponse:
    form = PathForm(request.POST)
    related_event = None
    if form.is_valid():
        path = form.save()
        related_event = path.event
        messages.success(request, 'مسیر با موفقیت ایجاد شد.')
        if related_event:
            return redirect('events:detail', event_id=related_event.id)
        return redirect('events:path_detail', path.id)

    event_id = request.POST.get('event', '').strip()
    if event_id:
        related_event = get_object_or_404(Event, id=event_id)
    messages.error(request, form.errors.as_text())
    if related_event:
        return redirect('events:detail', event_id=related_event.id)
    return redirect('events:paths')


@login_required
@require_POST
def path_edit(request: HttpRequest, path_id: int) -> HttpResponse:
    path = get_object_or_404(Path, id=path_id)
    form = PathForm(request.POST, instance=path)
    if form.is_valid():
        form.save()
        messages.success(request, 'مسیر با موفقیت ویرایش شد.')
    else:
        messages.error(request, form.errors.as_text())
    return redirect('events:path_detail', path_id)


@login_required
@require_POST
def path_delete(request: HttpRequest, path_id: int) -> JsonResponse:
    try:
        path = get_object_or_404(Path, id=path_id)
        path.delete()
        messages.success(request, f'مسیر «{path.name}» با موفقیت حذف شد.')
        return JsonResponse({'success': True, 'status': 200})
    except Exception as exc:
        messages.error(request, str(exc))
        return JsonResponse({'success': False, 'status': 500})


@login_required
@require_POST
def toggle_path_status(request: HttpRequest) -> JsonResponse:
    try:
        data = json.loads(request.body)
        form = PathStatusForm(data)
        if not form.is_valid():
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)

        path = get_object_or_404(Path, id=form.cleaned_data['path_id'])
        path.is_active = form.cleaned_data['action'] == 'play'
        path.save(update_fields=['is_active'])
        return JsonResponse({'success': True, 'path': {'id': path.id, 'name': path.name, 'is_active': path.is_active}})
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=400)
