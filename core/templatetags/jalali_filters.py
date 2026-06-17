from django import template
import jdatetime
import datetime
from django.utils import timezone

register = template.Library()


@register.filter(name='to_jalali')
def to_jalali(value, arg=None):
    """
    Convert a Gregorian date, datetime, or timestamp to a Jalali date string.
    """
    if not value:
        return ""

    try:
        is_just_date = False
        gregorian_dt = None

        if isinstance(value, datetime.date) and not isinstance(value, datetime.datetime):
            is_just_date = True
            gregorian_dt = datetime.datetime.combine(value, datetime.time.min)
        elif isinstance(value, datetime.datetime):
            gregorian_dt = value
        elif isinstance(value, (int, float)):
            gregorian_dt = datetime.datetime.fromtimestamp(value, tz=datetime.timezone.utc)
        else:
            return value

        aware_dt = None
        if timezone.is_aware(gregorian_dt):
            aware_dt = timezone.localtime(gregorian_dt)
        else:
            aware_dt = timezone.make_aware(gregorian_dt)

        jalali_dt = jdatetime.datetime.fromgregorian(datetime=aware_dt)
        
        format_str = arg
        if format_str is None:
            if is_just_date:
                format_str = '%Y/%m/%d'
            else:
                format_str = '%Y/%m/%d - %H:%M:%S'
                
        return jalali_dt.strftime(str(format_str))
        
    except Exception:
        return value


@register.filter
def to_persian_digits(value):

    if value is None:
        return ""
    
    english_to_persian = {
        '0': '۰', '1': '۱', '2': '۲', '3': '۳', '4': '۴',
        '5': '۵', '6': '۶', '7': '۷', '8': '۸', '9': '۹',
    }
    
    value_str = str(value)
    persian_str = ""
    for char in value_str:
        persian_str += english_to_persian.get(char, char)
        
    return persian_str

@register.filter(name='to_timestamp')
def to_timestamp(value):

    if isinstance(value, datetime.date):
        dt_object = datetime.datetime.combine(value, datetime.time.min)
        return int(dt_object.timestamp())
        
    elif isinstance(value, datetime.datetime):
        return int(value.timestamp())
        
    return ""
