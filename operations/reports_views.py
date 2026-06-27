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

@login_required
def reports_demographics(request):
    event_id = request.GET.get('event_id')
    schema_id = request.GET.get('schema_id')
    
    events = Event.objects.all().order_by('-created_at')
    if not event_id:
        active_event = Event.objects.filter(is_active=True).first()
        event_id = active_event.id if active_event else (events.first().id if events.exists() else None)
        
    schemas = EventSchema.objects.filter(event_id=event_id, is_active=True).order_by('column_name') if event_id else []
    
    if not schema_id and schemas.exists():
        schema_id = schemas.first().id
        
    selected_schema = EventSchema.objects.filter(id=schema_id).first() if schema_id else None
    
    aggregation_data = []
    total_records = 0
    
    if selected_schema and event_id:
        source = selected_schema.metadata_source
        key = selected_schema.metadata_key
        
        if source == 'm':
            # Query Person.metadata
            # Get participants of this event
            persons = Person.objects.filter(events__id=event_id)
            total_records = persons.count()
            
            # Group by JSON key
            agg = persons.annotate(
                field_value=KeyTextTransform(key, 'metadata')
            ).values('field_value').annotate(count=Count('id')).order_by('-count')
            
            for item in agg:
                val = item['field_value'] or 'نامشخص'
                aggregation_data.append({
                    'value': val,
                    'count': item['count'],
                    'percentage': round((item['count'] / total_records * 100) if total_records > 0 else 0, 1)
                })
                
        elif source == 'pem':
            # Query PersonEventMetadata
            pems = PersonEventMetadata.objects.filter(event_id=event_id)
            total_records = pems.count()
            
            agg = pems.annotate(
                field_value=KeyTextTransform(key, 'data')
            ).values('field_value').annotate(count=Count('id')).order_by('-count')
            
            for item in agg:
                val = item['field_value'] or 'نامشخص'
                aggregation_data.append({
                    'value': val,
                    'count': item['count'],
                    'percentage': round((item['count'] / total_records * 100) if total_records > 0 else 0, 1)
                })
        else:
            # Maybe query CheckInData if it's meant to be collected at a checkpoint
            checkin_data = CheckInData.objects.filter(event_schema_id=schema_id, check_in__is_valid=True)
            total_records = checkin_data.count()
            
            # Since value is a primitive, we group directly
            agg = checkin_data.values('value').annotate(count=Count('id')).order_by('-count')
            
            for item in agg:
                val = item['value']
                if val is None or str(val).strip() == '':
                    val = 'نامشخص'
                elif isinstance(val, bool):
                    val = 'بله' if val else 'خیر'
                aggregation_data.append({
                    'value': val,
                    'count': item['count'],
                    'percentage': round((item['count'] / total_records * 100) if total_records > 0 else 0, 1)
                })

    context = {
        'active_page': 'reports',
        'active_subpage': 'demographics',
        'events': events,
        'selected_event_id': int(event_id) if event_id else None,
        'schemas': schemas,
        'selected_schema_id': int(schema_id) if schema_id else None,
        'aggregation_data': aggregation_data,
        'total_records': total_records,
    }
    return render(request, 'operations/reports/demographics.html', context)
