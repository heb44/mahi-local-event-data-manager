from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from ..forms import CheckpointForm, CheckpointStatusForm
from ..models import Checkpoint, Path


@login_required
@require_GET
def checkpoints_list(request: HttpRequest) -> HttpResponse:
    paths = Path.objects.only('name').order_by('name')
    checkpoints = Checkpoint.objects.select_related('path', 'user').order_by('-is_active', 'path', 'created_at')
    context = {'checkpoints': checkpoints, 'paths': paths, 'active_page': 'checkpoints'}
    return render(request, 'core/checkpoints_list.html', context=context)


@login_required
@require_POST
def checkpoint_create(request: HttpRequest) -> HttpResponse:
    origin = request.POST.get('origin', '').strip()
    form = CheckpointForm(request.POST)
    if form.is_valid():
        checkpoint = form.save()
        messages.success(request, 'چک‌پوینت با موفقیت ایجاد شد.')
        if origin == 'detail':
            return redirect('events:path_detail', checkpoint.path.id)
    else:
        messages.error(request, form.errors.as_text())
        if origin == 'detail':
            return redirect('events:path_detail', request.POST.get('path'))
    return redirect('events:checkpoints')


@login_required
@require_POST
def checkpoint_delete(request: HttpRequest, cp_id: int) -> HttpResponse:
    origin = request.POST.get('origin', '').strip()
    checkpoint = get_object_or_404(Checkpoint, id=cp_id)
    try:
        checkpoint.delete()
        messages.success(request, 'چک‌پوینت با موفقیت حذف شد.')
    except Exception as exc:
        messages.error(request, str(exc))

    if origin == 'detail':
        return redirect('events:path_detail', checkpoint.path.id)
    return redirect('events:checkpoints')


@login_required
@require_POST
def checkpoint_edit(request: HttpRequest, cp_id: int) -> HttpResponse:
    origin = request.POST.get('origin', '').strip()
    checkpoint = get_object_or_404(Checkpoint, id=cp_id)
    form = CheckpointForm(request.POST, instance=checkpoint)
    if form.is_valid():
        checkpoint = form.save()
        messages.success(request, 'چک‌پوینت با موفقیت ویرایش شد.')
        if origin == 'detail':
            return redirect('events:path_detail', checkpoint.path.id)
        elif origin == 'checkpoint_detail':
            return redirect('events:checkpoint_detail', checkpoint.id)
    else:
        messages.error(request, form.errors.as_text())
        if origin == 'detail':
            return redirect('events:path_detail', request.POST.get('path') or checkpoint.path.id)
        elif origin == 'checkpoint_detail':
            return redirect('events:checkpoint_detail', checkpoint.id)
    return redirect('events:checkpoints')


@login_required
@require_POST
def toggle_checkpoint_status(request: HttpRequest) -> HttpResponse:
    form = CheckpointStatusForm(request.POST)
    if not form.is_valid():
        messages.error(request, form.errors.as_text()+"ارور فرم:")
        return redirect('events:checkpoints')

    checkpoint = get_object_or_404(Checkpoint, id=form.cleaned_data['id'])
    origin = form.cleaned_data['origin']
    try:
        checkpoint.is_active = form.cleaned_data['active']
        checkpoint.save(update_fields=['is_active'])
        messages.success(request, 'وضعیت چک‌پوینت با موفقیت تغییر کرد.')
    except Exception as exc:
        messages.error(request, str(exc))

    if origin == 'detail':
        return redirect('events:path_detail', checkpoint.path.id)
    elif origin == 'checkpoint_detail':
        return redirect('events:checkpoint_detail', checkpoint.id)
    return redirect('events:checkpoints')


@login_required
@require_GET
def checkpoint_detail(request: HttpRequest, cp_id: int) -> HttpResponse:
    checkpoint = get_object_or_404(
        Checkpoint.objects.select_related('path', 'path__event', 'user'),
        id=cp_id
    )
    schemas = checkpoint.schemas.select_related('event_schema').order_by('event_schema__column_name')
    
    from operations.models import CheckIn
    checkins = CheckIn.objects.filter(checkpoint=checkpoint).select_related('person', 'user').prefetch_related('data', 'data__event_schema').order_by('-timestamp')[:50]
    
    for ci in checkins:
        ci.prefetched_data_list = list(ci.data.all())
        
    context = {
        'checkpoint': checkpoint,
        'schemas': schemas,
        'checkins': checkins,
        'active_page': 'checkpoints',
    }
    return render(request, 'core/checkpoint_detail.html', context=context)

