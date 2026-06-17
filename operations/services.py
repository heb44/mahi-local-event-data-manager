from datetime import date
from typing import TypedDict

from django.core.paginator import Page, Paginator
from django.db import transaction
from django.db.models import Prefetch, Q, QuerySet
from django.http import HttpRequest

from accounts.models import User
from core.utils import timestamp_to_datetime
from events.models import Checkpoint, CheckpointSchema, Event, EventSchema, PersonEventMetadata
from people.models import Person

from .forms import CheckInPerformForm
from .models import CheckIn, CheckInData

DEFAULT_CHECKIN_PAGE_SIZE = 20

VALID_CHECKIN_ORDER_FIELDS = {
    'id': 'id',
    'person': 'person__last_name',
    'event': 'checkpoint__path__event__name',
    'checkpoint': 'checkpoint__name',
    'user': 'user__username',
    'timestamp': 'timestamp',
    'is_valid': 'is_valid',
    'is_approved': 'is_approved',
}


MessageList = list[tuple[str, str]]
SchemaValue = str | float | bool | date | None


class CheckInFilterParams(TypedDict):
    search_query: str
    search_fields_raw: str
    search_fields: list[str]
    data_key: str
    data_value: str
    selected_event_id: str
    selected_cp_ids: list[str]
    order_by: str
    direction: str
    selected_user_id: str
    selected_status: str
    start_date_str: str
    end_date_str: str


class CheckInListContext(TypedDict):
    page_obj: Page
    paginator: Paginator
    search_query: str
    search_fields: str
    search_fields_list: list[str]
    data_key: str
    data_value: str
    order_by: str
    direction: str
    selected_event_id: str
    selected_cp_ids: list[str]
    selected_user_id: str
    start_date: str
    end_date: str
    selected_status: str


class NextAllowedCheckpointsResult(TypedDict):
    status: str
    allowed_ids: list[int]
    details: list[Checkpoint] | None


class CheckpointSchemaData(TypedDict):
    sch: CheckpointSchema
    data: SchemaValue
    source: str
    msg: str


class CheckInSearchContext(TypedDict):
    person: Person
    checkpoint: Checkpoint
    latest_checkins: QuerySet
    cp_schemas: list[CheckpointSchemaData]
    ci: CheckIn
    is_valid: bool
    msgs: MessageList


class CheckInSearchResult(TypedDict, total=False):
    ok: bool
    msgs: MessageList
    context: CheckInSearchContext


class CheckInPerformResult(TypedDict):
    ok: bool
    msgs: MessageList
    latest_checkins: QuerySet


def prefetch_checkin_data_for_persons(
    persons_qs: QuerySet | list[Person],
    event: Event,
    user: User,
    extra_columns: QuerySet | list[EventSchema] | None = None,
) -> list[Person]:
    persons_list = list(persons_qs)
    if not persons_list:
        return persons_list

    if extra_columns is None:
        extra_columns = EventSchema.objects.with_user_permissions(event, user)

    schemas_to_prefetch = list(extra_columns)
    if not schemas_to_prefetch:
        for person in persons_list:
            person.prefetched_data = {}
        return persons_list

    person_ids = [person.id for person in persons_list]
    schema_ids = [schema.id for schema in schemas_to_prefetch]

    checkin_data_qs = CheckInData.objects.filter(
        check_in__person_id__in=person_ids,
        event_schema_id__in=schema_ids,
    ).select_related('event_schema', 'check_in').order_by('check_in__person_id', 'event_schema_id', '-created_at')

    data_map: dict[int, dict[int, SchemaValue]] = {}
    for data_item in checkin_data_qs:
        person_id = data_item.check_in.person_id
        schema_id = data_item.event_schema_id
        if person_id not in data_map:
            data_map[person_id] = {}
        if schema_id in data_map[person_id]:
            continue
        data_map[person_id][schema_id] = data_item.get_value()

    for person in persons_list:
        person.prefetched_data = data_map.get(person.id, {})

    return persons_list


class CheckInFilterService:
    @staticmethod
    def filter_sort_paginate(
        request: HttpRequest,
        base_queryset: QuerySet,
        page_size: int = DEFAULT_CHECKIN_PAGE_SIZE,
    ) -> CheckInListContext:
        params = CheckInFilterService._extract_params(request)
        queryset = CheckInFilterService._apply_filters(base_queryset, params)
        queryset = CheckInFilterService._apply_ordering(queryset, params)

        paginator = Paginator(queryset, page_size)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)

        return {
            'page_obj': page_obj,
            'paginator': paginator,
            'search_query': params['search_query'],
            'search_fields': params['search_fields_raw'],
            'search_fields_list': params['search_fields'],
            'data_key': params['data_key'],
            'data_value': params['data_value'],
            'order_by': params['order_by'],
            'direction': params['direction'],
            'selected_event_id': params['selected_event_id'],
            'selected_cp_ids': params['selected_cp_ids'],
            'selected_user_id': params['selected_user_id'],
            'start_date': params['start_date_str'],
            'end_date': params['end_date_str'],
            'selected_status': params['selected_status'],
        }

    @staticmethod
    def _extract_params(request: HttpRequest) -> CheckInFilterParams:
        search_fields_raw = request.GET.get('sf', '').strip()
        return {
            'search_query': request.GET.get('q', '').strip(),
            'search_fields_raw': search_fields_raw,
            'search_fields': search_fields_raw.split(',') if search_fields_raw else [],
            'data_key': request.GET.get('dk', '').strip(),
            'data_value': request.GET.get('dv', '').strip(),
            'selected_event_id': request.GET.get('event_id', '').strip(),
            'selected_cp_ids': request.GET.getlist('cp_ids'),
            'order_by': request.GET.get('ob', '-timestamp'),
            'direction': request.GET.get('dir', 'desc'),
            'selected_user_id': request.GET.get('user_id', '').strip(),
            'selected_status': request.GET.get('status', '').strip(),
            'start_date_str': request.GET.get('start_date', '').strip(),
            'end_date_str': request.GET.get('end_date', '').strip(),
        }

    @staticmethod
    def _apply_filters(queryset: QuerySet, params: CheckInFilterParams) -> QuerySet:
        filters = Q()
        if params['search_query'] and params['search_fields']:
            text_filter = Q()
            if 'person' in params['search_fields']:
                text_filter |= Q(person__name__icontains=params['search_query']) | Q(
                    person__last_name__icontains=params['search_query']
                )
            if 'user' in params['search_fields']:
                text_filter |= Q(user__username__icontains=params['search_query'])
            if 'description' in params['search_fields']:
                text_filter |= Q(description__icontains=params['search_query'])
            filters &= text_filter

        if params['selected_event_id'].isdigit():
            filters &= Q(checkpoint__path__event_id=int(params['selected_event_id']))
        if params['selected_cp_ids']:
            filters &= Q(checkpoint_id__in=params['selected_cp_ids'])
        if params['selected_user_id'].isdigit():
            filters &= Q(user_id=int(params['selected_user_id']))

        start_dt = timestamp_to_datetime(params['start_date_str']) if params['start_date_str'] else None
        end_dt = timestamp_to_datetime(params['end_date_str']) if params['end_date_str'] else None
        if start_dt:
            filters &= Q(timestamp__gte=start_dt)
        if end_dt:
            filters &= Q(timestamp__lte=end_dt)

        status_map = {
            'valid': Q(is_valid=True),
            'invalid': Q(is_valid=False),
            'pending': Q(is_valid=True, pending=True),
            'approved': Q(is_valid=True, is_approved=True),
            'rejected': Q(is_valid=True, is_approved=False, pending=False),
        }
        filters &= status_map.get(params['selected_status'], Q())

        queryset = queryset.filter(filters)

        if 'data' in params['search_fields'] and params['data_key'] and params['data_value']:
            data_q = Q(data__event_schema__column_name__iexact=params['data_key']) & (
                Q(data__text_value__icontains=params['data_value'])
                | Q(data__num_value__icontains=params['data_value'])
            )
            queryset = queryset.filter(data_q).distinct()

        return queryset

    @staticmethod
    def _apply_ordering(queryset: QuerySet, params: CheckInFilterParams) -> QuerySet:
        field = VALID_CHECKIN_ORDER_FIELDS.get(params['order_by'].lstrip('-'))
        if field:
            if params['direction'] == 'desc':
                field = f'-{field}'
            return queryset.order_by(field)
        return queryset.order_by('-timestamp')


class CheckpointService:
    @staticmethod
    def find_next_allowed_checkpoints(cp_id: int, person_id: int) -> NextAllowedCheckpointsResult:
        try:
            person = Person.objects.get(id=person_id)
            current_checkpoint = Checkpoint.objects.select_related('path').get(
                id=cp_id,
                is_active=True,
                path__is_active=True,
            )
        except (Person.DoesNotExist, Checkpoint.DoesNotExist):
            return {'status': 'INVALID_INPUT', 'allowed_ids': [], 'details': None}

        path = current_checkpoint.path
        path_checkpoints = list(path.checkpoints.filter(is_active=True).order_by('order'))
        completed_ids = set(
            CheckIn.objects.filter(person=person, checkpoint__path=path, pending=False).values_list(
                'checkpoint_id',
                flat=True,
            )
        )
        uncompleted_mandatory = [
            checkpoint for checkpoint in path_checkpoints if checkpoint.is_mandatory and checkpoint.id not in completed_ids
        ]
        if uncompleted_mandatory:
            return {
                'status': 'MANDATORY_PENDING',
                'allowed_ids': [checkpoint.id for checkpoint in uncompleted_mandatory],
                'details': uncompleted_mandatory,
            }

        if not path.enforce_checkpoint_order:
            return {
                'status': 'FREEMODE_AVAILABLE',
                'allowed_ids': [checkpoint.id for checkpoint in path_checkpoints],
                'details': None,
            }

        last_check_in = CheckIn.objects.filter(person=person, checkpoint__path=path, pending=False).order_by(
            '-timestamp'
        ).first()
        if not last_check_in:
            if not path_checkpoints:
                return {'status': 'EMPTY_PATH', 'allowed_ids': [], 'details': None}
            first_order = path_checkpoints[0].order
            return {
                'status': 'NEW_USER',
                'allowed_ids': [checkpoint.id for checkpoint in path_checkpoints if checkpoint.order == first_order],
                'details': None,
            }

        sorted_unique_orders = sorted({checkpoint.order for checkpoint in path_checkpoints})
        last_order = last_check_in.checkpoint.order

        try:
            current_index = sorted_unique_orders.index(last_order)
            next_order = sorted_unique_orders[current_index + 1] if current_index < len(sorted_unique_orders) - 1 else None
        except ValueError:
            next_order = sorted_unique_orders[0] if sorted_unique_orders else None

        allowed_orders = {last_order}
        if next_order is not None:
            allowed_orders.add(next_order)

        return {
            'status': 'NORMAL_ORDER',
            'allowed_ids': [checkpoint.id for checkpoint in path_checkpoints if checkpoint.order in allowed_orders],
            'details': None,
        }


class CheckInValidationService:
    @staticmethod
    def check_path_and_checkpoint_rules(checkpoint: Checkpoint, person: Person, user: User) -> MessageList:
        messages: MessageList = []
        has_checked = CheckIn.objects.filter(checkpoint=checkpoint, person=person, pending=False).exists()
        if has_checked and not checkpoint.path.allow_duplicate_checkin and not checkpoint.allow_duplicate_checkin:
            messages.append(('error', 'ثبت تکراری چک‌این مجاز نیست.'))

        if checkpoint.path.enforce_checkpoint_order:
            result = CheckpointService.find_next_allowed_checkpoints(checkpoint.id, person.id)
            if checkpoint.id not in result['allowed_ids']:
                if result['status'] == 'MANDATORY_PENDING':
                    names = ', '.join([pending_checkpoint.name for pending_checkpoint in result['details']])
                    messages.append(('error', f'ابتدا باید چک‌پوینت‌های اجباری زیر تکمیل شوند: {names}'))
                else:
                    messages.append(('error', 'ترتیب مجاز چک‌پوینت‌ها رعایت نشده است.'))

        if not any(level == 'error' for level, _ in messages):
            last_operator_checkin = CheckIn.objects.filter(user=user, checkpoint=checkpoint, pending=False).order_by(
                '-timestamp'
            ).first()
            if last_operator_checkin and last_operator_checkin.person == person:
                messages.append(('warn', 'توجه: این شخص قبلاً توسط شما در این چک‌پوینت ثبت شده است.'))

        return messages


class CheckInWorkflowService:
    @staticmethod
    def search(person_id: int, checkpoint_id: int, user: User) -> CheckInSearchResult:
        checkpoint = Checkpoint.objects.select_related('path__event').get(id=checkpoint_id, is_active=True)
        event = checkpoint.path.event
        if not event.is_active:
            return {'ok': False, 'msgs': [('error', 'رویداد فعال نیست.')]}

        person = Person.objects.prefetch_related(
            Prefetch('pems', queryset=PersonEventMetadata.objects.filter(event=event), to_attr='event_pems')
        ).get(id=person_id, events=event)

        messages = CheckInValidationService.check_path_and_checkpoint_rules(checkpoint, person, user)
        is_valid = not any(level == 'error' for level, _ in messages)

        with transaction.atomic():
            CheckIn.objects.filter(user=user, pending=True, is_valid=True).delete()
            check_in = CheckIn.objects.create(
                user=user,
                checkpoint=checkpoint,
                person=person,
                is_valid=is_valid,
                is_approved=False,
                pending=True,
            )

        checkpoint_schemas = checkpoint.schemas.filter(event_schema__is_active=True, can_view=True).select_related(
            'event_schema'
        ).order_by('-event_schema__data_type', 'event_schema__column_name')

        persons_with_data = prefetch_checkin_data_for_persons([person], event, user)
        person_with_data = persons_with_data[0] if persons_with_data else person

        checkpoint_schema_data: list[CheckpointSchemaData] = []
        for checkpoint_schema in checkpoint_schemas:
            data, source, message = checkpoint_schema.event_schema.get_data(person_with_data)
            checkpoint_schema_data.append(
                {
                    'sch': checkpoint_schema,
                    'data': data,
                    'source': source,
                    'msg': message,
                }
            )

        latest_checkins = CheckIn.objects.filter(checkpoint=checkpoint, user=user, pending=False).select_related('person').order_by(
            '-timestamp'
        )[:3]

        if is_valid:
            messages.append(('success', f'چک‌این برای «{person}» مجاز است.'))

        return {
            'ok': True,
            'context': {
                'person': person,
                'checkpoint': checkpoint,
                'latest_checkins': latest_checkins,
                'cp_schemas': checkpoint_schema_data,
                'ci': check_in,
                'is_valid': is_valid,
                'msgs': messages,
            },
        }

    @staticmethod
    def perform(ci: CheckIn, user: User, form: 'CheckInPerformForm') -> CheckInPerformResult:
        person = ci.person
        event = ci.checkpoint.path.event
        schema_values = form.cleaned_data['schema_values']
        action = form.cleaned_data['action']
        description = form.cleaned_data['description']

        schemas_with_permissions: dict[str, EventSchema] = {}
        if schema_values:
            schemas_with_permissions = {
                str(schema.id): schema
                for schema in EventSchema.objects.with_user_permissions(event, user).filter(id__in=schema_values.keys())
            }

        person_list_with_data = prefetch_checkin_data_for_persons([person], event, user)
        if person_list_with_data:
            person = person_list_with_data[0]

        current_values: dict[str, SchemaValue] = {}
        for schema_id, schema in schemas_with_permissions.items():
            value, _, _ = schema.get_data(person)
            current_values[schema_id] = value

        data_to_create: list[CheckInData] = []
        validation_errors: list[str] = []

        for schema_id, submitted_value in schema_values.items():
            event_schema = schemas_with_permissions.get(schema_id)
            if not event_schema:
                continue

            current_value = current_values.get(schema_id)
            data_type = event_schema.data_type
            if data_type == 'boolean':
                value_has_changed = (current_value if current_value is not None else False) != submitted_value
            elif data_type == 'text':
                value_has_changed = (current_value or '') != (submitted_value or '')
            else:
                value_has_changed = current_value != submitted_value

            if not value_has_changed:
                continue

            is_already_filled = current_value is not None and str(current_value) != ''
            can_proceed = (event_schema.can_fill and not is_already_filled) or (
                event_schema.can_edit and is_already_filled
            )
            if not can_proceed:
                validation_errors.append(f'شما مجوز ثبت یا ویرایش فیلد «{event_schema.column_name}» را ندارید.')
                continue

            checkin_data = CheckInData(check_in=ci, event_schema=event_schema)
            if data_type == 'boolean':
                checkin_data.bool_value = submitted_value
            elif data_type == 'text':
                checkin_data.text_value = submitted_value
            elif data_type == 'date':
                checkin_data.date_value = submitted_value
            elif data_type == 'number':
                checkin_data.num_value = submitted_value
            data_to_create.append(checkin_data)

        if validation_errors:
            return {'ok': False, 'msgs': [('error', error) for error in validation_errors]}

        with transaction.atomic():
            ci.is_approved = action == 'approve'
            ci.description = description
            ci.pending = False
            ci.save()
            if data_to_create:
                CheckInData.objects.bulk_create(data_to_create)

        status_text = 'تأیید شد' if ci.is_approved else 'رد شد'
        latest_checkins = CheckIn.objects.filter(checkpoint=ci.checkpoint, user=user, pending=False).select_related('person').order_by(
            '-timestamp'
        )[:3]
        return {
            'ok': True,
            'msgs': [('success', f'چک‌این «{ci.person}» با موفقیت ثبت شد و {status_text}.')],
            'latest_checkins': latest_checkins,
        }


def filter_sort_paginate_checkins(
    request: HttpRequest,
    queryset: QuerySet,
    page_size: int = DEFAULT_CHECKIN_PAGE_SIZE,
) -> CheckInListContext:
    return CheckInFilterService.filter_sort_paginate(request, queryset, page_size)


def check_path_and_checkpoint_rules(checkpoint: Checkpoint, person: Person, user: User) -> MessageList:
    return CheckInValidationService.check_path_and_checkpoint_rules(checkpoint, person, user)
