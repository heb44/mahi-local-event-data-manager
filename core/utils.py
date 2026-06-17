import jdatetime
from django.utils import timezone
from datetime import datetime, date
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)

class DateConverter:
    """Utility class for date conversions."""
    
    @staticmethod
    def convert_jalali_to_gregorian(jalali_date_str: str) -> Optional[date]:
        if not jalali_date_str:
            return None
        try:
            jalali_datetime = jdatetime.datetime.strptime(jalali_date_str, "%Y/%m/%d")
            return jalali_datetime.togregorian().date()
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    def timestamp_to_datetime(ts: Any) -> Optional[datetime]:
        if ts is None or str(ts).strip() == '':
            return None
        
        try:
            ts_str = str(ts).strip()
            if '.' in ts_str:
                ts_str = ts_str.split('.')[0]

            if len(ts_str) == 13:
                ts_seconds = int(ts_str) / 1000.0
            elif len(ts_str) == 10:
                ts_seconds = int(ts_str)
            else:
                return None
            
            return timezone.make_aware(datetime.fromtimestamp(ts_seconds))

        except (ValueError, TypeError) as e:
            logger.error(f"Could not convert timestamp '{ts}' to datetime: {e}")
            return None

def convert_jalali_to_gregorian(jalali_date_str: str) -> Optional[date]:
    return DateConverter.convert_jalali_to_gregorian(jalali_date_str)

def timestamp_to_datetime(ts: Any) -> Optional[datetime]:
    return DateConverter.timestamp_to_datetime(ts)
