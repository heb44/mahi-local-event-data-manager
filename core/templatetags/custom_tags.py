from django import template
import datetime

register = template.Library()

@register.filter
def concat(value, arg):
    return value + arg

@register.filter
def lookup(d, key):
    return d.get(key, "")


@register.filter
def get_schema_data(schema, person):
    return schema.get_data(person)

@register.filter(name='get_type')
def get_type(value):
    return type(value)


@register.simple_tag
def has_active_event():
    from events.models import Event
    return Event.objects.filter(is_active=True).exists()


@register.simple_tag
def get_active_event():
    from events.models import Event
    return Event.objects.filter(is_active=True).first()


@register.simple_tag
def get_persons_table_config():
    return {
        'bulk_actions': [
            {'value': 'delete', 'label': 'حذف'}
        ],
        'order_fields': [
            {'value': 'id', 'label': 'شناسه'},
            {'value': 'name', 'label': 'نام'},
            {'value': 'last_name', 'label': 'نام خانوادگی'},
            {'value': 'birth_date', 'label': 'تاریخ تولد'}
        ],
        'search_fields_config': [
            {'id': 'Name', 'value': 'name', 'label': 'جستجو در نام'},
            {'id': 'LastName', 'value': 'last_name', 'label': 'جستجو در نام خانوادگی'},
            {'id': 'Phone', 'value': 'phone_number', 'label': 'جستجو در شماره تلفن'}
        ]
    }


@register.simple_tag
def get_users_table_config():
    return {
        'bulk_actions': [
            {'value': 'activate', 'label': 'فعال کردن'},
            {'value': 'deactivate', 'label': 'غیرفعال کردن'},
            {'value': 'delete', 'label': 'حذف (غیر فعال)', 'disabled': True}
        ],
        'order_fields': [
            {'value': 'username', 'label': 'نام کاربری'},
            {'value': 'last_name', 'label': 'نام و نام خانوادگی'}
        ],
        'search_fields_config': [
            {'id': 'Username', 'value': 'username', 'label': 'جستجو در نام کاربری'},
            {'id': 'LastName', 'value': 'last_name', 'label': 'جستجو در نام و نام خانوادگی'}
        ]
    }


@register.simple_tag
def get_participants_table_config():
    return {
        'bulk_actions': [
            {'value': 'delete', 'label': 'حذف شرکت کننده'}
        ],
        'order_fields': [
            {'value': 'id', 'label': 'شناسه'},
            {'value': 'name', 'label': 'نام'},
            {'value': 'last_name', 'label': 'نام خانوادگی'},
            {'value': 'birth_date', 'label': 'تاریخ تولد'}
        ],
        'search_fields_config': [
            {'id': 'Name', 'value': 'name', 'label': 'جستجو در نام'},
            {'id': 'LastName', 'value': 'last_name', 'label': 'جستجو در نام خانوادگی'},
            {'id': 'Phone', 'value': 'phone_number', 'label': 'جستجو در شماره تلفن'}
        ]
    }


@register.simple_tag
def get_add_participant_table_config():
    return {
        'bulk_actions': [
            {'value': 'add', 'label': 'افزودن به رویداد'}
        ],
        'order_fields': [
            {'value': 'id', 'label': 'شناسه'},
            {'value': 'name', 'label': 'نام'},
            {'value': 'last_name', 'label': 'نام خانوادگی'},
            {'value': 'birth_date', 'label': 'تاریخ تولد'}
        ],
        'search_fields_config': [
            {'id': 'Name', 'value': 'name', 'label': 'جستجو در نام'},
            {'id': 'LastName', 'value': 'last_name', 'label': 'جستجو در نام خانوادگی'},
            {'id': 'Phone', 'value': 'phone_number', 'label': 'جستجو در شماره تلفن'}
        ]
    }


@register.simple_tag
def get_checkins_table_config():
    return {
        'bulk_actions': [],
        'order_fields': [
            {'value': 'id', 'label': 'شناسه'},
            {'value': 'timestamp', 'label': 'زمان ثبت'}
        ],
        'search_fields_config': [
            {'id': 'Name', 'value': 'name', 'label': 'جستجو در نام'},
            {'id': 'LastName', 'value': 'last_name', 'label': 'جستجو در نام خانوادگی'}
        ]
    }


@register.simple_tag
def get_checkin_page_table_config():
    return {
        'bulk_actions': [],
        'order_fields': [
            {'value': 'id', 'label': 'شناسه'},
            {'value': 'name', 'label': 'نام'},
            {'value': 'last_name', 'label': 'نام خانوادگی'},
            {'value': 'birth_date', 'label': 'تاریخ تولد'}
        ],
        'search_fields_config': [
            {'id': 'Name', 'value': 'name', 'label': 'جستجو در نام'},
            {'id': 'LastName', 'value': 'last_name', 'label': 'جستجو در نام خانوادگی'},
            {'id': 'Phone', 'value': 'phone_number', 'label': 'جستجو در شماره تلفن'}
        ]
    }


