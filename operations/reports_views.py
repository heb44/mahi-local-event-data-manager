from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, F, ExpressionWrapper, DurationField, Avg, Max
from django.db.models.functions import TruncHour, TruncDate
from django.db.models.fields.json import KeyTextTransform
from django.utils import timezone
from datetime import timedelta
import json

from .models import CheckIn, CheckInData
from events.models import Event, Path, Checkpoint, EventSchema, PersonEventMetadata
from people.models import Person
from accounts.models import User
from django.views.decorators.http import require_GET

@login_required
def reports_progression(request):
    event_id = request.GET.get('event_id')
    path_id = request.GET.get('path_id')
    
    events = Event.objects.all().order_by('-created_at')
    
    if not event_id:
        active_event = Event.objects.filter(is_active=True).first()
        event_id = active_event.id if active_event else (events.first().id if events.exists() else None)
        
    paths = Path.objects.filter(event_id=event_id).order_by('name') if event_id else []
    
    if not path_id and paths:
        path_id = paths.first().id
        
    checkpoints = Checkpoint.objects.filter(path_id=path_id).order_by('order') if path_id else []
    
    funnel_data = []
    bottleneck_data = []
    
    if path_id:
        # Funnel
        total_started = CheckIn.objects.filter(
            checkpoint__path_id=path_id, 
            is_valid=True
        ).values('person').distinct().count()
        
        for cp in checkpoints:
            count = CheckIn.objects.filter(checkpoint=cp, is_valid=True).values('person').distinct().count()
            percentage = round((count / total_started * 100) if total_started > 0 else 0, 1)
            funnel_data.append({
                'name': cp.name,
                'count': count,
                'percentage': percentage
            })
            
        # Bottleneck alerts (Simplified for sqlite compatibility without complex window date math)
        # Find people who checked into C_n and C_n-1, calculate avg time.
        # For a robust report, we just pull the checkins for the path and calculate in Python
        checkins = list(CheckIn.objects.filter(
            checkpoint__path_id=path_id, is_valid=True
        ).order_by('person_id', 'timestamp').values('person_id', 'checkpoint_id', 'checkpoint__name', 'timestamp'))
        
        person_history = {}
        for ci in checkins:
            pid = ci['person_id']
            if pid not in person_history:
                person_history[pid] = []
            person_history[pid].append(ci)
            
        transitions = {} # (from_cp, to_cp) -> list of durations
        
        for pid, history in person_history.items():
            for i in range(1, len(history)):
                prev = history[i-1]
                curr = history[i]
                duration = (curr['timestamp'] - prev['timestamp']).total_seconds() / 60.0
                key = f"{prev['checkpoint__name']} -> {curr['checkpoint__name']}"
                if key not in transitions:
                    transitions[key] = []
                transitions[key].append(duration)
                
        for key, durations in transitions.items():
            avg_duration = sum(durations) / len(durations)
            if avg_duration > 5: # Threshold for bottleneck alert (e.g. 5 minutes)
                bottleneck_data.append({
                    'transition': key,
                    'avg_minutes': round(avg_duration, 1),
                    'count': len(durations)
                })

    context = {
        'active_page': 'reports',
        'active_subpage': 'progression',
        'events': events,
        'selected_event_id': int(event_id) if event_id else None,
        'paths': paths,
        'selected_path_id': int(path_id) if path_id else None,
        'funnel_data': funnel_data,
        'bottleneck_data': bottleneck_data,
    }
    return render(request, 'operations/reports/progression.html', context)

@login_required
def reports_compliance(request):
    event_id = request.GET.get('event_id')
    
    events = Event.objects.all().order_by('-created_at')
    if not event_id:
        active_event = Event.objects.filter(is_active=True).first()
        event_id = active_event.id if active_event else (events.first().id if events.exists() else None)
        
    # Get rejected or invalid checkins
    base_qs = CheckIn.objects.filter(
        Q(is_valid=False) | Q(is_approved=False)
    )
    if event_id:
        base_qs = base_qs.filter(checkpoint__path__event_id=event_id)
        
    total_errors = base_qs.count()
    recent_errors = base_qs.filter(timestamp__gte=timezone.now() - timedelta(days=1)).count()
    
    # Error distribution
    invalid_count = base_qs.filter(is_valid=False).count()
    rejected_count = base_qs.filter(is_valid=True, is_approved=False).count()
    
    distribution = [
        {'name': 'نامعتبر (سیستمی)', 'count': invalid_count, 'color': '#ef4444'}, # red-500
        {'name': 'رد شده (توسط کاربر)', 'count': rejected_count, 'color': '#f97316'}, # orange-500
    ]
    
    # Trend
    trend_data = base_qs.annotate(
        date=TruncDate('timestamp')
    ).values('date').annotate(count=Count('id')).order_by('-date')[:7]
    
    # Grid data
    auditor_logs = base_qs.select_related('person', 'checkpoint', 'user').order_by('-timestamp')[:50]
    
    context = {
        'active_page': 'reports',
        'active_subpage': 'compliance',
        'events': events,
        'selected_event_id': int(event_id) if event_id else None,
        'total_errors': total_errors,
        'recent_errors': recent_errors,
        'distribution': distribution,
        'trend_data': list(trend_data),
        'auditor_logs': auditor_logs,
    }
    return render(request, 'operations/reports/compliance.html', context)

from django.http import JsonResponse
from .services import CheckInFilterService

@login_required
def report_builder(request):
    events = Event.objects.all().order_by('-created_at')
    checkpoints = Checkpoint.objects.select_related('path__event').all()
    users = User.objects.filter(is_active=True)
    schemas = EventSchema.objects.filter(is_active=True).select_related('event')
    
    context = {
        'active_page': 'reports',
        'active_subpage': 'builder',
        'all_events': events,
        'all_checkpoints': checkpoints,
        'all_users': users,
        'all_schemas': schemas,
    }
    return render(request, 'operations/reports/builder.html', context)

@login_required
@require_GET
def api_report_aggregate(request):
    base_qs = CheckIn.objects.select_related(
        'person', 'checkpoint', 'checkpoint__path', 'checkpoint__path__event', 'user'
    )
    params = CheckInFilterService._extract_params(request)
    filtered_qs = CheckInFilterService._apply_filters(base_qs, params)
    
    field_type = request.GET.get('field_type', 'static')
    field_key = request.GET.get('field_key', '')
    
    total_count = filtered_qs.count()
    data = []
    
    if total_count > 0:
        if field_type == 'static':
            if field_key == 'checkpoint':
                agg = filtered_qs.values(name=F('checkpoint__name')).annotate(count=Count('id')).order_by('-count')
                data = list(agg)
            elif field_key == 'user':
                agg = filtered_qs.values(name=F('user__username')).annotate(count=Count('id')).order_by('-count')
                data = list(agg)
            elif field_key == 'event':
                agg = filtered_qs.values(name=F('checkpoint__path__event__name')).annotate(count=Count('id')).order_by('-count')
                data = list(agg)
            elif field_key == 'status':
                invalid = filtered_qs.filter(is_valid=False).count()
                approved = filtered_qs.filter(is_valid=True, is_approved=True).count()
                rejected = filtered_qs.filter(is_valid=True, is_approved=False, pending=False).count()
                pending = filtered_qs.filter(is_valid=True, pending=True).count()
                
                status_raw = [
                    {'name': 'پذیرفته شده', 'count': approved},
                    {'name': 'نامعتبر', 'count': invalid},
                    {'name': 'رد شده', 'count': rejected},
                    {'name': 'در انتظار', 'count': pending},
                ]
                data = [s for s in status_raw if s['count'] > 0]
        
        elif field_type == 'dynamic' and field_key.isdigit():
            schema_id = int(field_key)
            agg = filtered_qs.filter(data__event_schema_id=schema_id).values(name=F('data__value')).annotate(count=Count('id')).order_by('-count')
            for item in agg:
                if item['name'] is None or str(item['name']).strip() == '':
                    item['name'] = 'نامشخص'
                elif isinstance(item['name'], bool):
                    item['name'] = 'بله' if item['name'] else 'خیر'
                data.append(item)
                
        # Calculate percentages
        for d in data:
            d['name'] = d.get('name') or 'نامشخص'
            d['percentage'] = round((d['count'] / total_count) * 100, 1)
            
    return JsonResponse({
        'total': total_count,
        'data': data
    })
