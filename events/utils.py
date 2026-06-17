import jdatetime
from django.utils.dateparse import parse_date

DATA_TYPE_TEXT = 'text'
DATA_TYPE_NUMBER = 'number'
DATA_TYPE_DATE = 'date'
DATA_TYPE_BOOLEAN = 'boolean'



def validate_and_cast_value(data_type, value):
        if value is None:
            return (False, None)

        if data_type == DATA_TYPE_NUMBER:
            try:
                return (True, float(value))
            except (ValueError, TypeError):
                return (False, None)
        elif data_type == DATA_TYPE_BOOLEAN:
            str_value = str(value).lower()
            if str_value in ['true', '1']:
                return (True, True)
            if str_value in ['false', '0']:
                return (True, False)
            return (False, None)
        elif data_type == DATA_TYPE_DATE:
            str_value = str(value)
            gregorian_date = parse_date(str_value)
            if gregorian_date:
                return (True, gregorian_date)
            try:
                normalized_value = str_value.replace('/', '-')
                jalali_date = jdatetime.datetime.strptime(normalized_value, "%Y-%m-%d")
                return (True, jalali_date.togregorian().date())
            except (ValueError, TypeError):
                return (False, None)
        elif data_type == DATA_TYPE_TEXT:
            return (True, str(value))
        
        return (False, None)
