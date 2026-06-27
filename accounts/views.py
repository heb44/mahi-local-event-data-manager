from itertools import groupby
from operator import attrgetter
from typing import Any

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import Group, Permission
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import (
    CheckInSettingsForm,
    GeneralSettingsForm,
    RoleForm,
    RolePermissionsForm,
    UserAssignRoleForm,
    UserChangePasswordForm,
    UserCreateForm,
    UserUpdateForm,
)
from .models import User, UserSettings
from .services import UserService


@login_required
def users_list(request: HttpRequest) -> HttpResponse:
    search_query = request.GET.get('q', '').strip()
    users_query = User.objects.all().order_by('username')

    if search_query:
        users_query = users_query.filter(
            Q(username__icontains=search_query)
            | Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
        )

    logged_in_user_ids = UserService.get_logged_in_user_ids()
    users_list_with_status = []
    for user in users_query:
        user.is_logged_in = user.pk in logged_in_user_ids
        users_list_with_status.append(user)

    all_roles = Group.objects.all()
    paginator = Paginator(users_list_with_status, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'all_roles': all_roles,
        'page_obj': page_obj,
        'paginator': paginator,
        'active_page': 'users',
        'search_query': search_query,
    }
    return render(request, 'users/users_list.html', context=context)


def login_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect('operations:dashboard')

    next_page = request.POST.get('next') or request.GET.get('next') or 'operations:dashboard'
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'خوش آمدید، {user.username}.')
            return redirect(next_page)
    else:
        form = AuthenticationForm()

    return render(request, 'users/login.html', {'form': form, 'next': next_page})


@require_POST
@login_required
def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    return redirect('accounts:login')


@require_POST
@login_required
@permission_required('auth.add_user', raise_exception=True)
def user_create(request: HttpRequest) -> HttpResponse:
    form = UserCreateForm(request.POST)
    if form.is_valid():
        user = form.save()
        messages.success(request, f'کاربر «{user.username}» با موفقیت ایجاد شد.')
    else:
        messages.error(request, form.errors.as_text())
    return redirect('accounts:users')


@require_POST
@login_required
@permission_required('auth.change_user', raise_exception=True)
def user_edit(request: HttpRequest, user_id: int) -> HttpResponse:
    user = get_object_or_404(User, id=user_id)
    form = UserUpdateForm(request.POST, instance=user)
    if form.is_valid():
        user = form.save()
        messages.success(request, f'کاربر «{user.username}» با موفقیت ویرایش شد.')
    else:
        messages.error(request, form.errors.as_text())
    return redirect('accounts:users')


@require_POST
@login_required
@permission_required('auth.change_user', raise_exception=True)
def toggle_user_status(request: HttpRequest, user_id: int) -> HttpResponse:
    user_to_toggle = get_object_or_404(User, id=user_id)
    success, error_msg = UserService.toggle_user_status(user_to_toggle, request.user)
    if error_msg:
        messages.error(request, error_msg)
    else:
        status = 'فعال' if user_to_toggle.is_active else 'غیرفعال'
        messages.success(request, f'وضعیت کاربر «{user_to_toggle.username}» به «{status}» تغییر کرد.')
    return redirect('accounts:users')


@require_POST
@login_required
@permission_required('auth.change_user', raise_exception=True)
def user_change_password(request: HttpRequest) -> HttpResponse:
    user_id = request.POST.get('user_id')
    if not user_id:
        messages.error(request, 'شناسه کاربر ارسال نشده است.')
        return redirect('accounts:users')

    user = get_object_or_404(User, id=user_id)
    form = UserChangePasswordForm(request.POST, user=user)
    if form.is_valid():
        form.save()
        messages.success(request, f'رمز عبور کاربر «{user.username}» با موفقیت تغییر کرد.')
    else:
        messages.error(request, form.errors.as_text())
    return redirect('accounts:users')


@require_POST
@permission_required('auth.change_user')
def user_assign_role_view(request: HttpRequest, user_id: int) -> HttpResponse:
    target_user = get_object_or_404(User, pk=user_id)
    form = UserAssignRoleForm(request.POST)
    if not form.is_valid():
        messages.error(request, form.errors.as_text())
        return redirect('accounts:users')

    error_msg = UserService.assign_roles(
        target_user,
        list(form.cleaned_data['roles'].values_list('id', flat=True)),
        request.user,
    )
    if error_msg:
        messages.error(request, error_msg)
    else:
        messages.success(request, f'نقش‌های کاربر «{target_user.username}» با موفقیت به‌روزرسانی شد.')
    return redirect('accounts:users')


@login_required
def user_autocomplete(request: HttpRequest) -> JsonResponse:
    results: list[dict[str, Any]] = []
    if request.method == 'GET':
        term = request.GET.get('term', '').strip()
        if len(term) < 2:
            return JsonResponse([], safe=False)

        users = User.objects.filter(username__icontains=term) | User.objects.filter(first_name__icontains=term)
        results = [
            {
                'id': user.id,
                'label': f'{user.first_name} {user.last_name} ({user.username})',
                'value': user.username,
            }
            for user in users[:10]
        ]
    return JsonResponse(results, safe=False)


@permission_required('auth.view_group')
def role_list_view(request: HttpRequest) -> HttpResponse:
    roles = Group.objects.annotate(permission_count=Count('permissions')).all()
    context = {
        'roles': roles,
        'active_section': 'roles',
    }
    return render(request, 'core/settings/roles_list.html', context)


@permission_required('auth.add_group')
def role_create_view(request: HttpRequest) -> HttpResponse:
    form = RoleForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        new_role = form.save()
        messages.success(request, f'نقش «{new_role.name}» با موفقیت ایجاد شد.')
        return redirect('accounts:role_list')

    context = {
        'active_section': 'roles',
        'form_title': 'Create New Role',
        'error': form.errors.get('name', [None])[0],
        'old_name': form.data.get('name', ''),
    }
    return render(request, 'core/settings/role_form.html', context)


@permission_required('auth.change_group')
def role_update_view(request: HttpRequest, pk: int) -> HttpResponse:
    role = get_object_or_404(Group, pk=pk)
    form = RoleForm(request.POST or None, instance=role)
    if request.method == 'POST' and form.is_valid():
        role = form.save()
        messages.success(request, f'نقش «{role.name}» با موفقیت ویرایش شد.')
        return redirect('accounts:role_list')

    context = {
        'object': role,
        'active_section': 'roles',
        'form_title': f'Edit Role: {Group.objects.get(pk=pk).name}',
        'error': form.errors.get('name', [None])[0],
    }
    return render(request, 'core/settings/role_form.html', context)


@permission_required('auth.delete_group')
def role_delete_view(request: HttpRequest, pk: int) -> HttpResponse:
    role = get_object_or_404(Group, pk=pk)
    if request.method == 'POST':
        role_name = role.name
        role.delete()
        messages.success(request, f'نقش «{role_name}» با موفقیت حذف شد.')
        return redirect('accounts:role_list')

    context = {
        'object': role,
        'active_section': 'roles',
    }
    return render(request, 'core/settings/role_confirm_delete.html', context)


@permission_required('auth.change_group')
def role_permissions_update_view(request: HttpRequest, pk: int) -> HttpResponse:
    group = get_object_or_404(Group, pk=pk)
    allowed_permissions_query = Permission.objects.exclude(
        content_type__app_label__in=settings.EXCLUDE_PERMISSION_APPS
    ).exclude(codename__in=settings.EXCLUDE_PERMISSION_CODENAMES)
    form = RolePermissionsForm(request.POST or None, allowed_permissions=allowed_permissions_query)

    if request.method == 'POST':
        if form.is_valid():
            group.permissions.set(form.cleaned_data['permissions'])
            messages.success(request, f'مجوزهای نقش «{group.name}» با موفقیت به‌روزرسانی شد.')
            return redirect('accounts:role_list')
        messages.error(request, form.errors.as_text())

    all_permissions = allowed_permissions_query.select_related('content_type').order_by(
        'content_type__app_label',
        'codename',
    )
    grouped_permissions = {
        app_label: list(permissions)
        for app_label, permissions in groupby(all_permissions, key=attrgetter('content_type.app_label'))
    }

    context = {
        'group': group,
        'grouped_permissions': grouped_permissions,
        'group_permission_ids': set(group.permissions.values_list('id', flat=True)),
        'active_section': 'roles',
    }
    return render(request, 'core/settings/role_permissions_form.html', context)


@login_required
def settings_general(request: HttpRequest) -> HttpResponse:
    user_settings, _ = UserSettings.objects.get_or_create(user=request.user)
    form = GeneralSettingsForm(
        request.POST or None,
        initial={
            'digits_type': 'fa' if user_settings.use_persian_digits else 'en',
            'event_display_duration': user_settings.dashboard_event_display_duration,
            'event_count': user_settings.dashboard_event_count,
        }
    )
    if request.method == 'POST':
        if form.is_valid():
            user_settings.use_persian_digits = form.cleaned_data['digits_type'] == 'fa'
            user_settings.dashboard_event_display_duration = form.cleaned_data['event_display_duration']
            user_settings.dashboard_event_count = form.cleaned_data['event_count']
            user_settings.save(update_fields=[
                'use_persian_digits',
                'dashboard_event_display_duration',
                'dashboard_event_count',
            ])
            messages.success(request, 'تنظیمات با موفقیت ذخیره شد.')
        else:
            messages.error(request, form.errors.as_text())

    context = {
        'active_section': 'general',
        'active_page': 'settings',
        'use_persian_digits': user_settings.use_persian_digits,
        'dashboard_event_display_duration': user_settings.dashboard_event_display_duration,
        'dashboard_event_count': user_settings.dashboard_event_count,
    }
    return render(request, 'core/settings/general.html', context=context)


@login_required
def settings_checkin(request: HttpRequest) -> HttpResponse:
    user_settings, _ = UserSettings.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = CheckInSettingsForm(request.POST, instance=user_settings)
        if form.is_valid():
            settings_instance = form.save(commit=False)
            settings_instance.user = request.user
            settings_instance.save()
            messages.success(request, 'تنظیمات با موفقیت ذخیره شد.')
        else:
            messages.error(request, form.errors.as_text())
        return redirect('accounts:settings_checkin')

    context = {
        'active_section': 'checkin',
        'active_page': 'settings',
        'user_settings': user_settings,
    }
    return render(request, 'core/settings/checkin.html', context=context)
